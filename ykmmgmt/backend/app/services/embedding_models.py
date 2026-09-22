"""Curated encoder registry for the chat semantic matcher.

The admin UI only offers what is listed here: every option was scored against
the frozen eval set by ``scripts/bench_embedding_models.py``, and switching to
one is only meaningful together with a rebuild of the stored vectors (vectors
from different encoders are not comparable).

Weights are *not* downloaded on demand by default — the encoder loads with
``local_files_only=True`` semantics in production, so a model must already be
present in the container's Hugging Face cache (pre-bake it in the image or
mount a shared ``HF_HOME``). ``EMBEDDING_MODEL_NAME`` in ``.env`` stays the
bootstrap default for a knowledge base that has no vectors yet.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmbeddingModelOption:
    """One selectable encoder.

    ``name`` is what gets persisted on every ``qa_pairs`` row and handed to
    ``SentenceTransformer``; ``label`` is the Chinese display name shown in the
    admin picker; ``note`` carries the trade-off an admin needs to read.
    """

    name: str
    label: str
    dims: int
    note: str
    # Some encoders expect an instruction on the query side only (asymmetric
    # retrieval). Applied to user messages, never to stored questions.
    query_prefix: str | None = None


# Ordered best-first by the benchmark (see tmp_export/embedding_model_benchmark.md).
# Notes carry the measured numbers so an admin can weigh quality against CPU cost:
# rank1 = threshold-free ranking accuracy, P≥0.95 召回 = usable recall under the
# project's "wrong answer is worse than a fallback" policy, p95 = query encode time.
EMBEDDING_MODEL_OPTIONS: list[EmbeddingModelOption] = [
    EmbeddingModelOption(
        name="paraphrase-multilingual-MiniLM-L12-v2",
        label="MiniLM-L12 v2（多语言·轻量）— 默认",
        dims=384,
        note="基准选择：rank1 0.90、可分性 0.83，唯一能在精确率≥0.95 下给出可用召回（0.43）的模型；"
        "p95 24ms、内存峰值 0.8GB。提召回请补相似问法，不是换模型。",
    ),
    EmbeddingModelOption(
        name="BAAI/bge-small-zh-v1.5",
        label="BGE small zh 1.5（中文·最轻）",
        dims=512,
        note="最快最小（p95 11ms、0.5GB）且中文专训，但分数整体压在 0.9 以上，"
        "阈值需推到 0.99 才安全（此时召回仅 0.17）。适合内存/CPU 严重受限时降级使用。",
    ),
    EmbeddingModelOption(
        name="jinaai/jina-embeddings-v5-text-small-text-matching",
        label="Jina v5 text-small 文本匹配（多语言·排序最强）",
        dims=1024,
        note="横评中纯排序最好（rank1 0.933），可分性与基线持平（0.822）；代价是 p95 225ms、"
        "内存峰值 4GB。许可 CC BY-NC 4.0（仅非商用可用）。切换后必须重新调阈值。",
    ),
    EmbeddingModelOption(
        name="BAAI/bge-base-zh-v1.5",
        label="BGE base zh 1.5（中文·均衡）",
        dims=768,
        note="rank1 0.90、可分性 0.76；分数标定同样偏高（可用阈值 0.99+）。"
        "仅发布 pytorch_model.bin，服务器需 torch>=2.6 才能加载。",
    ),
    EmbeddingModelOption(
        name="BAAI/bge-m3",
        label="BGE M3（多语言·长文本）",
        dims=1024,
        note="短问句上不占优（可分性 0.76）；它的价值在 8k+ 长上下文与混合检索。"
        "权重 2.3GB、p95 218ms，同样需 torch>=2.6 加载 .bin。",
    ),
    EmbeddingModelOption(
        name="Qwen/Qwen3-Embedding-0.6B",
        label="Qwen3-Embedding 0.6B（中文·Apache-2.0）",
        dims=1024,
        note="中文语义最强阵营里许可最友好（Apache-2.0，可商用）；本场景 rank1 0.867、可分性 0.72。"
        "p95 213ms、内存峰值 3.8GB；加检索指令反而变差，已按对称匹配不加。",
    ),
]


def find_option(name: str) -> EmbeddingModelOption | None:
    """Look up a registry entry by its encoder id."""
    return next((o for o in EMBEDDING_MODEL_OPTIONS if o.name == name), None)


def option_for(name: str) -> EmbeddingModelOption | None:
    """Registry entry for ``name`` — also accepts a local snapshot path holding it."""
    exact = find_option(name)
    if exact is not None:
        return exact
    # A mounted snapshot dir (…/Qwen3-Embedding-0.6B) is the same encoder.
    return next((o for o in EMBEDDING_MODEL_OPTIONS if o.name.rstrip("/").split("/")[-1] in name), None)
