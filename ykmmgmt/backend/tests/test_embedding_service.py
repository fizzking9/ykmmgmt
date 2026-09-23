"""Unit tests for the embedding + semantic-matching service.

These run with an injected deterministic provider so no torch / model download
is required — the heavy encoder is only touched when no provider is set.
"""

import pytest

from app.services import embedding_service as es


@pytest.fixture(autouse=True)
def _reset_service():
    """Restore the provider/cache seams around every test."""
    es.set_provider(None)
    es.invalidate_qa_cache()
    yield
    es.set_provider(None)
    es.invalidate_qa_cache()


def _fake_provider(texts: list[str]) -> list[list[float]]:
    """Deterministic 2-d embedder: [length, summed char codes]."""
    return [[float(len(t)), float(sum(ord(c) for c in t))] for t in texts]


# ── computation ───────────────────────────────────────────────────────────


def test_compute_embedding_returns_vector():
    es.set_provider(_fake_provider)
    vec = es.compute_embedding("abc")
    assert vec == [3.0, 294.0]  # ord('a')+ord('b')+ord('c') == 97+98+99


def test_compute_embeddings_batch_is_parallel_and_ordered():
    es.set_provider(_fake_provider)
    vecs = es.compute_embeddings(["a", "ab", "abc"])
    assert len(vecs) == 3
    assert vecs[0][0] == 1.0 and vecs[2][0] == 3.0  # lengths preserved, in order


def test_compute_embeddings_empty_returns_empty():
    es.set_provider(_fake_provider)
    assert es.compute_embeddings([]) == []


# ── similarity ────────────────────────────────────────────────────────────


def test_similarity_identical_is_one():
    assert es.compute_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_similarity_scaled_vector_is_one():
    # cosine is scale-invariant
    assert es.compute_similarity([1.0, 2.0], [2.0, 4.0]) == pytest.approx(1.0)


def test_similarity_orthogonal_is_zero():
    assert es.compute_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_similarity_opposite_is_negative_one():
    assert es.compute_similarity([1.0, 1.0], [-1.0, -1.0]) == pytest.approx(-1.0)


def test_similarity_zero_vector_returns_zero():
    assert es.compute_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_similarity_dimension_mismatch_raises():
    with pytest.raises(ValueError):
        es.compute_similarity([1.0, 2.0], [1.0])


def test_similarity_empty_vector_raises():
    with pytest.raises(ValueError):
        es.compute_similarity([], [1.0])


# ── cache ─────────────────────────────────────────────────────────────────


def test_cache_lifecycle():
    assert es.get_qa_cache() is None  # cold
    e = es.QACacheEntry(id="x", question="q", category=None, embeddings=[[1.0, 0.0]])
    es.set_qa_cache([e])
    cached = es.get_qa_cache()
    assert cached is not None and cached[0].id == "x"
    es.invalidate_qa_cache()
    assert es.get_qa_cache() is None


def test_set_provider_invalidates_cache():
    e = es.QACacheEntry(id="x", question="q", category=None, embeddings=[[1.0]])
    es.set_qa_cache([e])
    assert es.get_qa_cache() is not None
    es.set_provider(_fake_provider)  # switching encoders drops stale vectors
    assert es.get_qa_cache() is None


def test_warming_an_empty_kb_does_not_latch():
    """A cache warmed while the table was empty must count as cold.

    Otherwise rows that arrive without an API write -- a SQL import, load_qa_seed.py,
    a database restore -- stay invisible to the process forever. Production served the
    fallback answer to every question after being seeded this way.
    """
    es.set_qa_cache([])
    assert es.get_qa_cache() is None, "空缓存被当成有效，外部写入再也读不到"


def test_cache_goes_cold_after_the_ttl(monkeypatch):
    """Out-of-band edits must reach a running worker within the configured bound."""
    e = es.QACacheEntry(id="x", question="q", category=None, embeddings=[[1.0]])
    es.set_qa_cache([e])
    assert es.get_qa_cache() is not None
    ttl = es.settings.chat_kb_cache_ttl_seconds
    assert ttl > 0, "测试假设默认开启了过期"
    warmed = es._qa_cache_warmed_at
    monkeypatch.setattr(es, "_clock", lambda: warmed + ttl + 1)
    assert es.get_qa_cache() is None
    monkeypatch.setattr(es, "_clock", lambda: warmed + ttl / 2)
    assert es.get_qa_cache() is not None, "未过期就重读数据库了"


# ── matching ──────────────────────────────────────────────────────────────


def _entries() -> list[es.QACacheEntry]:
    return [
        # canonical + one variant
        es.QACacheEntry(id="p1", question="如何导入？", category="导入", embeddings=[[1.0, 0.0], [0.9, 0.1]]),
        es.QACacheEntry(id="p2", question="今天天气？", category=None, embeddings=[[0.0, 1.0]]),
    ]


def test_find_best_match_picks_global_max_variant_index():
    # query closest to p1's variant (index 1)
    m = es.find_best_match([0.8, 0.6], _entries(), threshold=0.5)
    assert m is not None
    assert m.pair_id == "p1"
    assert m.variant_index == 1
    assert m.question == "如何导入？"  # canonical label regardless of matched variant


def test_find_best_match_canonical_zero_index():
    m = es.find_best_match([1.0, 0.0], _entries(), threshold=0.5)
    assert m is not None and m.variant_index == 0 and m.pair_id == "p1"


def test_find_best_match_below_threshold_returns_none():
    # orthogonal to everything → best score ~0 < 0.5
    m = es.find_best_match([0.0, 0.0], _entries(), threshold=0.5)
    assert m is None


def test_find_best_match_empty_entries_returns_none():
    assert es.find_best_match([1.0, 0.0], [], threshold=0.5) is None


def test_peek_best_match_ignores_threshold():
    m = es.peek_best_match([0.9, 0.1], _entries())
    assert m is not None  # returns the argmax even at a tiny score
