"""Integration tests for the chat runtime API — /api/chat/ask + sessions.

A deterministic *orthogonal* provider maps each unique string to its own basis
vector, so an exact-phrasing query scores cosine 1.0 (match) and any other
string scores 0.0 (fallback) — full match/fallback determinism without torch.
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.chat_session import ChatSession
from app.models.qa_pair import QAPair
from app.routers.chat import FALLBACK_ANSWER
from app.services import embedding_service
from main import app
from tests.conftest import anonymous_cookies, auth_cookies

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


@pytest.fixture(autouse=True)
def _env():
    _registry.clear()
    embedding_service.set_provider(_orth_provider)
    embedding_service.invalidate_qa_cache()
    yield
    embedding_service.set_provider(None)
    embedding_service.invalidate_qa_cache()
    asyncio.run(_cleanup())


async def _cleanup() -> None:
    eng = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(eng)() as session:
            if _created_sessions:
                await session.execute(
                    delete(ChatSession).where(
                        ChatSession.id.in_([uuid.UUID(s) for s in _created_sessions])
                    )
                )
            if _created_qa:
                await session.execute(
                    delete(QAPair).where(QAPair.id.in_([uuid.UUID(q) for q in _created_qa]))
                )
            await session.commit()
    finally:
        await eng.dispose()


def _client(cookies: dict[str, str] | None = None) -> AsyncClient:
    transport = ASGITransport(app=app)
    if cookies is not None:
        return AsyncClient(transport=transport, base_url="http://test", cookies=cookies)
    return AsyncClient(transport=transport, base_url="http://test")


async def _create_pair(
    client: AsyncClient, question: str, variants: list[str] | None = None, answer: str = "答案", **kw
) -> str:
    resp = await client.post(
        "/api/chat/qa-pairs",
        json={"question": question, "question_variants": variants or [], "answer": answer, **kw},
    )
    assert resp.status_code == 201, resp.text
    pair_id = resp.json()["id"]
    _created_qa.append(pair_id)
    return pair_id


# ── Ask: matching ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_matches_canonical_question():
    async with _client() as client:
        q = f"如何导入数据_{uuid.uuid4().hex[:6]}？"
        await _create_pair(client, q, answer="点击数据导入")
        resp = await client.post("/api/chat/ask", json={"message": q})
        assert resp.status_code == 200
        body = resp.json()
        assert body["matched"] is True
        assert body["matched_question"] == q
        assert body["matched_variant_index"] == 0
        assert body["similarity_score"] == pytest.approx(1.0)
        assert body["answer"] == "点击数据导入"
        assert body["session_id"]
        _created_sessions.append(body["session_id"])


@pytest.mark.asyncio
async def test_ask_matches_a_variant_not_the_canonical():
    async with _client() as client:
        canonical = f"标准问_{uuid.uuid4().hex[:6]}"
        variant = f"变体问_{uuid.uuid4().hex[:6]}"
        await _create_pair(client, canonical, variants=[variant], answer="同一答案")
        resp = await client.post("/api/chat/ask", json={"message": variant})
        body = resp.json()
        assert body["matched"] is True
        assert body["matched_variant_index"] == 1  # the variant fired
        assert body["matched_question"] == canonical  # canonical label returned
        _created_sessions.append(body["session_id"])


@pytest.mark.asyncio
async def test_ask_compound_variants_share_one_answer():
    async with _client() as client:
        c = f"总览_{uuid.uuid4().hex[:6]}"
        v1 = f"子问一_{uuid.uuid4().hex[:6]}"
        v2 = f"子问二_{uuid.uuid4().hex[:6]}"
        await _create_pair(client, c, variants=[v1, v2], answer="完整经营总览答案")
        answers = []
        for msg, idx in [(c, 0), (v1, 1), (v2, 2)]:
            body = (await client.post("/api/chat/ask", json={"message": msg})).json()
            assert body["matched"] is True
            assert body["answer"] == "完整经营总览答案"
            assert body["matched_variant_index"] == idx
            answers.append(body["answer"])
            _created_sessions.append(body["session_id"])
        assert len(set(answers)) == 1


@pytest.mark.asyncio
async def test_ask_fallback_when_no_match():
    async with _client() as client:
        await _create_pair(client, f"注册问题_{uuid.uuid4().hex[:6]}")
        resp = await client.post("/api/chat/ask", json={"message": "一个完全无关的随机问题"})
        body = resp.json()
        assert resp.status_code == 200
        assert body["matched"] is False
        assert body["answer"] == FALLBACK_ANSWER
        assert body["matched_question"] is None
        assert body["similarity_score"] is None
        _created_sessions.append(body["session_id"])


@pytest.mark.asyncio
async def test_ask_empty_message_rejected():
    async with _client() as client:
        resp = await client.post("/api/chat/ask", json={"message": "   "})
        assert resp.status_code == 422


# ── Sessions ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_session_lifecycle():
    async with _client() as client:
        created = await client.post("/api/chat/sessions")
        assert created.status_code == 201
        sid = created.json()["id"]
        _created_sessions.append(sid)

        listed = (await client.get("/api/chat/sessions")).json()
        assert any(s["id"] == sid for s in listed)

        empty = await client.get(f"/api/chat/sessions/{sid}/messages")
        assert empty.status_code == 200 and empty.json()["total"] == 0

        deleted = await client.delete(f"/api/chat/sessions/{sid}")
        assert deleted.status_code == 204
        after = (await client.get("/api/chat/sessions")).json()
        assert all(s["id"] != sid for s in after)


@pytest.mark.asyncio
async def test_ask_reuses_session_and_records_history():
    async with _client() as client:
        q = f"历史问题_{uuid.uuid4().hex[:6]}"
        pair_id = await _create_pair(client, q, answer="历史答案")
        sid = (await client.post("/api/chat/sessions")).json()["id"]
        _created_sessions.append(sid)

        body = (await client.post("/api/chat/ask", json={"message": q, "session_id": sid})).json()
        assert body["session_id"] == sid

        page = (await client.get(f"/api/chat/sessions/{sid}/messages")).json()
        assert page["total"] == 2  # one user + one assistant
        roles = [m["role"] for m in page["items"]]
        assert roles == ["user", "assistant"]
        assistant = page["items"][1]
        assert assistant["matched_qa_id"] == pair_id
        assert assistant["matched_variant_index"] == 0
        assert assistant["similarity_score"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_messages_pagination():
    async with _client() as client:
        await _create_pair(client, "分页问题", answer="A")
        sid = (await client.post("/api/chat/sessions")).json()["id"]
        _created_sessions.append(sid)
        for _ in range(3):
            await client.post("/api/chat/ask", json={"message": "分页问题", "session_id": sid})
        page = (await client.get(f"/api/chat/sessions/{sid}/messages", params={"size": 2})).json()
        assert page["total"] == 6  # 3 asks × (user + assistant)
        assert len(page["items"]) == 2


@pytest.mark.asyncio
async def test_session_is_private_to_its_owner():
    async with _client(cookies=auth_cookies("user")) as user_client:
        sid = (await user_client.post("/api/chat/sessions")).json()["id"]
        _created_sessions.append(sid)
    # Root must not see another user's session
    async with _client() as root_client:
        assert (await root_client.get(f"/api/chat/sessions/{sid}/messages")).status_code == 404
        assert (await root_client.delete(f"/api/chat/sessions/{sid}")).status_code == 404


@pytest.mark.asyncio
async def test_ask_requires_auth():
    async with _client(cookies=anonymous_cookies()) as client:
        resp = await client.post("/api/chat/ask", json={"message": "hi"})
        assert resp.status_code == 401
