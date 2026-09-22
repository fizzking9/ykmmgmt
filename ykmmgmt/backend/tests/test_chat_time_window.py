"""Time-window guard: a match may not answer for a different calendar period.

Root cause this defends: the encoders rank 「上周总共接待了多少条？」 next to
「本周总共接待了多少条？」 as near-duplicates (measured 0.876 in
tmp_export/embedding_model_benchmark.md), while each preset question reports for
exactly one window. Unit tests pin the extraction rules; the integration tests use
the deterministic orthogonal provider so the conflicting query scores an exact 1.0 —
proof the fallback comes from the guard, not from the threshold.
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from app.core.config import settings
from app.models.chat_session import ChatSession
from app.models.qa_pair import QAPair
from app.routers.chat import FALLBACK_ANSWER
from app.services import embedding_service, time_window
from main import app

# Shared engine connections are bound to the per-test event loop; without this the
# connections this module opens leak into the next module and fail on a closed loop.
pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")

_DIM = 128
_registry: dict[str, int] = {}
_created_qa: list[str] = []
_created_sessions: list[str] = []


def _orth_provider(texts: list[str]) -> list[list[float]]:
    vecs = []
    for t in texts:
        idx = _registry.setdefault(t, len(_registry))
        v = [0.0] * _DIM
        v[idx % _DIM] = 1.0
        vecs.append(v)
    return vecs


async def _delete_created_rows() -> None:
    """Own engine + explicit dispose: teardown runs after pytest-asyncio has closed
    its loop, so the shared pool's connections are unusable here."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    eng = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(eng, expire_on_commit=False)() as session:
            if _created_sessions:
                await session.execute(
                    delete(ChatSession).where(ChatSession.id.in_([uuid.UUID(s) for s in _created_sessions]))
                )
            if _created_qa:
                await session.execute(delete(QAPair).where(QAPair.id.in_([uuid.UUID(q) for q in _created_qa])))
            await session.commit()
    finally:
        await eng.dispose()
    _created_sessions.clear()
    _created_qa.clear()


@pytest.fixture(autouse=True)
def _fake_encoder():
    """Deterministic encoder for these tests, plus cleanup of the rows they write."""
    _registry.clear()
    embedding_service.set_provider(_orth_provider)
    embedding_service.invalidate_qa_cache()
    yield
    asyncio.run(_delete_created_rows())
    embedding_service.set_provider(None)
    embedding_service.invalidate_qa_cache()


# ── Extraction ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("今日经营总览如何？", {"today"}),
        ("上周总共接待了多少条？", {"last_week"}),
        ("上上周总共接待了多少条？", {"week_before_last"}),  # must not also read as last_week
        ("上周和本周对比一下", {"last_week", "this_week"}),
        ("这个月的投诉登记情况", {"this_month"}),
        ("投诉积压情况怎么样？", set()),  # no window named
        ("最近的接待数据", set()),  # vague recency is not a window
    ],
)
def test_window_extraction(text, expected):
    assert time_window.time_windows(text) == expected


def test_unknown_window_never_conflicts():
    """Either side naming no period keeps the previous behaviour — the guard only
    removes matches it can positively prove wrong."""
    assert time_window.windows_conflict("投诉登记情况怎么样？", "昨日投诉分析：三源登记/处理/积压如何？") is False
    assert time_window.windows_conflict("昨日投诉分析：三源登记/处理/积压如何？", "昨日投诉分析") is False


def test_different_periods_conflict_even_across_granularity():
    # Observed false fire: a 上周 question matching the 昨日 pair at 0.850.
    assert time_window.windows_conflict("上周的投诉登记情况怎么样？", "昨日投诉分析：三源登记/处理/积压如何？") is True
    assert time_window.windows_conflict("本周总共接待了多少条？", "今日经营总览如何？") is True


def test_same_period_does_not_conflict():
    same_day = ("昨天的投诉登记、处理和积压分别是多少？", "昨日投诉分析：三源登记/处理/积压如何？")
    assert time_window.windows_conflict(*same_day) is False


# ── End to end ────────────────────────────────────────────────────────────────


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _create_pair(question: str, variants: list[str], answer: str = "答案") -> str:
    async with _client() as client:
        resp = await client.post(
            "/api/chat/qa-pairs",
            json={"question": question, "question_variants": variants, "answer": answer},
        )
        assert resp.status_code == 201, resp.text
        pair_id = resp.json()["id"]
    _created_qa.append(pair_id)
    return pair_id


@pytest.mark.asyncio
async def test_conflicting_period_falls_back_even_at_a_perfect_score():
    """A variant may not contradict its pair's declared window: it scores 1.0 and is
    still refused, because serving this week's numbers for last week is a wrong answer."""
    token = uuid.uuid4().hex[:6]
    await _create_pair(f"本周接待量是多少_{token}？", [f"上周接待量是多少_{token}？"], answer="本周接待 128 条")
    async with _client() as client:
        resp = await client.post("/api/chat/ask", json={"message": f"上周接待量是多少_{token}？"})
        assert resp.status_code == 200
        body = resp.json()
        _created_sessions.append(body["session_id"])
        assert body["matched"] is False
        assert body["answer"] == FALLBACK_ANSWER


@pytest.mark.asyncio
async def test_matching_period_still_answers():
    token = uuid.uuid4().hex[:6]
    await _create_pair(f"今日经营总览_{token}如何？", [f"今天接待退款数据_{token}汇总"], answer="今日总览")
    async with _client() as client:
        resp = await client.post("/api/chat/ask", json={"message": f"今天接待退款数据_{token}汇总"})
        body = resp.json()
        _created_sessions.append(body["session_id"])
        assert body["matched"] is True
        assert body["similarity_score"] == pytest.approx(1.0)
        assert body["answer"] == "今日总览"
