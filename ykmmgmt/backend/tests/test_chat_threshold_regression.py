"""Gate 10 — threshold regression guard.

Runs the frozen eval set through the real encoder and asserts the tuned
operating point still clears precision ≥ 0.95. A model or preprocessing change
that shifts similarity-score distributions fails this guard, forcing a re-tune
before merge. Skips (does not fail) when the encoder cannot be loaded — e.g. an
offline CI box without the model cached.
"""

import pytest

from scripts.tune_chat_threshold import MIN_PRECISION, ModelUnavailableError, run_eval


def test_chat_threshold_regression():
    # local_only=True → never triggers a slow network download from within the
    # suite; runs for real when the encoder is cached, skips instantly otherwise.
    try:
        result = run_eval(local_only=True)
    except ModelUnavailableError as e:
        pytest.skip(f"embedding model not cached locally, skipping regression guard: {e}")

    best = result["best"]
    assert best is not None, "no threshold met the precision floor — knowledge base drifted"
    assert best.precision >= MIN_PRECISION - 1e-9, (
        f"precision {best.precision:.3f} dropped below {MIN_PRECISION} at threshold {best.threshold:.2f}"
    )
    # Sanity: the operating point must still resolve real positives.
    assert best.recall > 0.0
    assert result["latency_p95_ms"] >= 0.0
