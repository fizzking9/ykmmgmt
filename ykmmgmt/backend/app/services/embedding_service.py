"""Embedding + semantic-matching service for the Q&A chat widget.

The sentence-transformers encoder is imported *lazily* (only when an embedding
is actually computed) so importing the app / running the server never loads
torch. A swappable provider lets unit tests inject a deterministic stand-in
without downloading any weights.

Cosine similarity is implemented directly on plain lists (numpy-free) so the
matching maths stays dependency-light and trivially testable.
"""

from __future__ import annotations

import logging
import math
import os
import sys
import time
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from app.core.config import settings
from app.services import embedding_models

logger = logging.getLogger("ykmmgmt.chat")

# A batch embedder: list of texts -> parallel list of embedding vectors.
EmbeddingProvider = Callable[[list[str]], list[list[float]]]

# ── Encoder provider seam ───────────────────────────────────────────────────
_model = None  # lazily-initialised SentenceTransformer singleton
_provider: EmbeddingProvider | None = None  # test override; None → default model
# Runtime encoder choice made by the admin (``None`` → follow EMBEDDING_MODEL_NAME).
_active_model_name: str | None = None


def active_model_name() -> str:
    """The encoder id currently in use — admin override first, then the env default."""
    return _active_model_name or settings.embedding_model_name


def set_active_model(name: str) -> None:
    """Switch the encoder at runtime.

    Drops the loaded weights and the match cache: vectors from another encoder
    are not comparable, so nothing may keep serving them after a switch.
    """
    global _model, _active_model_name
    if name == _active_model_name:
        return
    _model = None
    _active_model_name = name
    invalidate_qa_cache()


def active_query_prefix() -> str:
    """Instruction the active encoder wants on the *query* side ("" when none)."""
    option = embedding_models.option_for(active_model_name())
    return (option.query_prefix if option else None) or ""


def reset_active_model() -> None:
    """Drop the runtime override so the encoder follows ``EMBEDDING_MODEL_NAME`` again."""
    global _model, _active_model_name
    _model = None
    _active_model_name = None
    invalidate_qa_cache()


def set_provider(provider: EmbeddingProvider | None) -> None:
    """Install a custom batch embedder (used by tests) or reset to the model.

    Resetting invalidates the embedding cache so stale vectors from a previous
    provider are never matched against.
    """
    global _provider
    _provider = provider
    invalidate_qa_cache()


def _get_default_model(local_files_only: bool | None = None):
    """Lazy-load the SentenceTransformer singleton for the active model.

    ``local_files_only`` defaults to the configured policy — offline unless
    ``YKM_EMBEDDING_ALLOW_DOWNLOAD`` is set — because a cache miss on a network
    where huggingface.co is unreachable costs five backing-off retries and stalls
    whatever request triggered the load. Callers that deliberately want to fetch
    (a tuning script warming up a fresh model) pass the flag explicitly.
    """
    global _model
    if _model is None:
        name = active_model_name()
        if local_files_only is None:
            local_files_only = not settings.embedding_allow_download

        # ``local_files_only=True`` alone is NOT enough in this stack: sentence-transformers
        # still issues a HEAD request for its module config, which times out for minutes
        # behind a blocked network instead of falling back to the cache. HF_HUB_OFFLINE is
        # the switch that demonstrably suppresses it, and huggingface_hub reads it when the
        # module is first imported — so set it *before* the heavy import below, and patch
        # the resolved constant too for processes that already imported it.
        if local_files_only:
            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            hub_constants = sys.modules.get("huggingface_hub.constants")
            if hub_constants is not None:
                # Written after import, when the env var is already too late for the
                # resolved constant; the attribute exists only at runtime, hence ignore.
                hub_constants.HF_HUB_OFFLINE = True  # type: ignore[attr-defined]

        # Heavy import kept inside the function — torch loads only on first use.
        from sentence_transformers import SentenceTransformer

        logger.info("Loading embedding model: %s (local_files_only=%s)", name, local_files_only)
        try:
            _model = SentenceTransformer(name, local_files_only=local_files_only)
        except Exception as e:
            if not local_files_only:
                raise
            raise RuntimeError(
                f"向量模型 {name} 未预置到本机，且已禁止在线下载：请先将权重预置到服务器"
                f"（镜像构建时下载），或设置 YKM_EMBEDDING_ALLOW_DOWNLOAD=true 后重启。"
                f"({type(e).__name__}: {e})"
            ) from e
    return _model


def warmup(local_files_only: bool | None = None) -> int:
    """Load the encoder now; return its vector dimension.

    ``local_files_only=True`` fails fast when the weights are not already cached
    (no network stalls) — used by the regression guard to skip cleanly on offline
    runners. ``None`` follows the configured policy.
    """
    return int(_get_default_model(local_files_only=local_files_only).get_sentence_embedding_dimension())


def _encode_batch(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    if _provider is not None:
        return _provider(texts)
    model = _get_default_model()
    # normalize_embeddings=True → unit vectors, so cosine == dot product.
    vectors = model.encode(texts, normalize_embeddings=True)
    return [[float(x) for x in vec] for vec in vectors]


# ── Public computation API ──────────────────────────────────────────────────


def compute_embedding(text: str) -> list[float]:
    """Return a single embedding vector for ``text``."""
    return _encode_batch([text])[0]


def compute_embeddings(texts: Sequence[str]) -> list[list[float]]:
    """Batch-compute embeddings for ``texts`` (canonical question + variants)."""
    return _encode_batch(list(texts))


def encode_query(text: str) -> list[float]:
    """Embed a *user message*, prefixed with the active model's query instruction.

    Instruction-aware encoders (BGE, Qwen3) are trained with an asymmetric
    prompt on the query side only; stored questions stay unprefixed.
    """
    return _encode_batch([active_query_prefix() + text])[0]


def compute_similarity(emb1: Sequence[float], emb2: Sequence[float]) -> float:
    """Cosine similarity of two equal-length, non-empty vectors in [-1, 1]."""
    if not emb1 or not emb2:
        raise ValueError("相似度计算要求两个非空向量")
    if len(emb1) != len(emb2):
        raise ValueError(f"向量维度不一致: {len(emb1)} != {len(emb2)}")
    dot = sum(a * b for a, b in zip(emb1, emb2, strict=True))
    norm1 = math.sqrt(sum(a * a for a in emb1))
    norm2 = math.sqrt(sum(b * b for b in emb2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ── Q&A embedding cache ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class QACacheEntry:
    """One active Q&A pair's matchable data, held in memory between CRUD ops."""

    id: str
    question: str
    category: str | None
    embeddings: list[list[float]]
    answer: str = ""


_qa_cache: dict[str, QACacheEntry] | None = None
_qa_cache_warmed_at: float = 0.0

# Bound here so tests can move the clock instead of patching the stdlib module.
_clock = time.monotonic


def get_qa_cache() -> list[QACacheEntry] | None:
    """Cached entries, or ``None`` when the caller must reload from the DB.

    Cold means three things, not one:
      * never warmed, or dropped by :func:`invalidate_qa_cache`;
      * warmed **empty**. An empty knowledge base must not latch, otherwise content
        that arrives without an API write -- a SQL import, ``load_qa_seed.py``, a
        database restore -- stays invisible to the process for its whole lifetime.
        A seeded production host did exactly that and answered every question with
        the fallback until it was restarted;
      * older than ``chat_kb_cache_ttl_seconds``, which bounds how long any
        out-of-band edit takes to reach a running worker.
    """
    if _qa_cache is None or not _qa_cache:
        return None
    ttl = settings.chat_kb_cache_ttl_seconds
    if ttl > 0 and (_clock() - _qa_cache_warmed_at) > ttl:
        return None
    return list(_qa_cache.values())


def set_qa_cache(entries: Iterable[QACacheEntry]) -> None:
    global _qa_cache, _qa_cache_warmed_at
    entries = list(entries)
    _qa_cache = {e.id: e for e in entries}
    _qa_cache_warmed_at = _clock()


def invalidate_qa_cache() -> None:
    """Drop the whole cache so the next ask reloads active pairs from the DB.

    Called after every Q&A CRUD write (create/update/delete/rebuild).
    """
    global _qa_cache, _qa_cache_warmed_at
    _qa_cache = None
    _qa_cache_warmed_at = 0.0


# ── Matching ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class MatchResult:
    pair_id: str
    question: str  # canonical phrasing — the stable label shown in the UI
    variant_index: int  # 0 = canonical question, k>=1 = the k-th variant
    score: float


def find_best_match(
    query_embedding: Sequence[float],
    entries: Iterable[QACacheEntry],
    threshold: float | None = None,
) -> MatchResult | None:
    """Global argmax of cosine similarity over every (pair, embedding).

    The single best phrasing across *all* pairs wins; a match is returned only
    when its score clears ``threshold`` (defaults to the configured value).
    """
    if threshold is None:
        threshold = settings.chat_similarity_threshold

    best: MatchResult | None = None
    for entry in entries:
        for idx, emb in enumerate(entry.embeddings):
            if not emb or len(emb) != len(query_embedding):
                # Vectors from another encoder are not comparable: skip them (and
                # let the caller fall back) instead of failing the whole request.
                continue
            score = compute_similarity(query_embedding, emb)
            if best is None or score > best.score:
                best = MatchResult(entry.id, entry.question, idx, score)

    if best is not None and best.score >= threshold:
        return best
    return None


def peek_best_match(
    query_embedding: Sequence[float],
    entries: Iterable[QACacheEntry],
) -> MatchResult | None:
    """Best (pair, variant, score) ignoring the threshold — for near-miss logging."""
    return find_best_match(query_embedding, entries, threshold=float("-inf"))
