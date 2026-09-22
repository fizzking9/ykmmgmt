"""Offline tests for the tuning-script math (no embedding model required).

The sweep operates on precomputed top-match rows, so precision/recall/selection
logic is fully verifiable without loading sentence-transformers.
"""

from scripts.tune_chat_threshold import (
    TopMatch,
    choose_operating_point,
    metrics_at,
    misfires,
    sweep,
)


def _m(query, expected, pair_id, score):
    return TopMatch(query=query, expected=expected, pair_id=pair_id, score=score, latency_ms=1.0)


def _mixed():
    return [
        _m("p1", "a", "a", 0.90),  # positive correct, high
        _m("p2", "a", "a", 0.60),  # positive correct, low
        _m("p3", "a", "b", 0.80),  # positive wrong pair
        _m("n1", None, "a", 0.70),  # negative, mid score
        _m("n2", None, "b", 0.30),  # negative, low score
    ]


def test_metrics_at_high_threshold():
    m = metrics_at(0.75, _mixed())
    # p1 TP; p2 FN(below); p3 FN+FP(wrong); n1 TN(0.7<0.75); n2 TN
    assert (m.tp, m.fp, m.fn, m.tn) == (1, 1, 2, 2)
    assert m.precision == 0.5
    assert abs(m.recall - 1 / 3) < 1e-9
    assert m.fallback_accuracy == 1.0  # both negatives rejected at 0.75


def test_metrics_at_mid_threshold_counts_negative_false_positive():
    m = metrics_at(0.65, _mixed())
    # n1 (0.7) now accepted → FP; tp=1, fn=2, fp=2, tn=1
    assert (m.tp, m.fp, m.fn, m.tn) == (1, 2, 2, 1)
    assert m.precision == 1 / 3
    assert m.fallback_accuracy == 0.5


def test_sweep_covers_full_range():
    rows = sweep(_mixed())
    assert rows[0].threshold == 0.55
    assert rows[-1].threshold == 0.95
    assert len(rows) == 41  # 0.55..0.95 step 0.01 inclusive


def test_choose_operating_point_prefers_recall_under_precision_floor():
    clean = [
        _m("p1", "a", "a", 0.90),
        _m("p2", "a", "a", 0.88),
        _m("n1", None, "a", 0.30),
        _m("n2", None, "b", 0.20),
    ]
    best = choose_operating_point(sweep(clean))
    assert best is not None
    assert best.precision >= 0.95
    assert best.recall == 1.0
    assert best.tp == 2 and best.fp == 0


def test_choose_operating_point_degenerates_when_not_separable():
    # negative scores HIGHER than the positive → no threshold accepts the
    # positive at precision ≥ 0.95; only "accept nothing" clears the floor,
    # so the chosen operating point has zero recall.
    dirty = [
        _m("p1", "a", "a", 0.80),
        _m("n1", None, "a", 0.85),
    ]
    best = choose_operating_point(sweep(dirty))
    assert best is None or best.recall == 0.0


def test_misfires_lists_wrong_and_missed_and_false():
    best = metrics_at(0.75, _mixed())
    rows = misfires(best, _mixed())
    queries = {r[0] for r in rows}
    assert "p2" in queries  # positive below threshold (missed)
    assert "p3" in queries  # positive matched wrong pair
    assert "n1" not in queries  # correctly rejected at 0.75
