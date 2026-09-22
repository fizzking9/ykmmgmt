"""Integration tests for the admin Q&A CRUD API — /api/chat/qa-pairs.

A deterministic embedding provider is injected so these run without torch /
model download while still exercising the real write path (alignment invariant,
cache invalidation, soft delete, rebuild).
"""

import asyncio
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.qa_pair import QAPair
from app.services import embedding_service
from main import app
from tests.conftest import anonymous_cookies, auth_cookies

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")

_created_ids: list[str] = []


def _fake_provider(texts: list[str]) -> list[list[float]]:
    """Fixed 8-d vector per text → guarantees len(embeddings) == len(texts)."""
    return [[float(i + 1) for i in range(8)] for _ in texts]


@pytest.fixture(autouse=True)
def _provider_and_cleanup():
    embedding_service.set_provider(_fake_provider)
    yield
    embedding_service.set_provider(None)
    embedding_service.invalidate_qa_cache()
    if _created_ids:
        asyncio.run(_delete_created(list(_created_ids)))
        _created_ids.clear()


async def _delete_created(ids: list[str]) -> None:
    eng = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(eng)() as session:
            await session.execute(delete(QAPair).where(QAPair.id.in_([uuid.UUID(i) for i in ids])))
            await session.commit()
    finally:
        await eng.dispose()


def _client(cookies: dict[str, str] | None = None) -> AsyncClient:
    transport = ASGITransport(app=app)
    if cookies is not None:
        return AsyncClient(transport=transport, base_url="http://test", cookies=cookies)
    return AsyncClient(transport=transport, base_url="http://test")


async def _create(client: AsyncClient, **payload) -> dict:
    payload.setdefault("question", f"问题_{uuid.uuid4().hex[:8]}？")
    payload.setdefault("answer", "答案")
    resp = await client.post("/api/chat/qa-pairs", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    _created_ids.append(data["id"])
    return data


async def _embeddings_len(pair_id: str) -> int:
    async with async_session_factory() as session:
        row = (
            await session.execute(select(QAPair.embeddings).where(QAPair.id == uuid.UUID(pair_id)))
        ).scalar_one()
    return 0 if row is None else len(row)


# ── Create ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_with_variants_aligns_embeddings():
    async with _client() as client:
        data = await _create(
            client,
            question_variants=["怎么上传？", "从哪导入？"],
            category="测试导入",
        )
        assert data["variant_count"] == 2
        assert data["has_embeddings"] is True
        # invariant: embeddings length == 1 canonical + 2 variants
        assert await _embeddings_len(data["id"]) == 3


@pytest.mark.asyncio
async def test_create_blank_variants_are_dropped():
    async with _client() as client:
        data = await _create(client, question_variants=["  ", "有效问法", ""])
        assert data["question_variants"] == ["有效问法"]
        assert await _embeddings_len(data["id"]) == 2  # canonical + 1 surviving variant


@pytest.mark.asyncio
async def test_create_empty_question_rejected():
    async with _client() as client:
        resp = await client.post("/api/chat/qa-pairs", json={"question": "   ", "answer": "a"})
        assert resp.status_code == 422


# ── List / filter / categories ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_pagination_and_category_filter():
    async with _client() as client:
        cat = f"cat_{uuid.uuid4().hex[:6]}"
        for _ in range(3):
            await _create(client, category=cat)
        resp = await client.get("/api/chat/qa-pairs", params={"category": cat, "size": 2})
        assert resp.status_code == 200
        page = resp.json()
        assert page["total"] == 3
        assert len(page["items"]) == 2
        assert all(i["category"] == cat for i in page["items"])


@pytest.mark.asyncio
async def test_categories_endpoint_lists_distinct():
    async with _client() as client:
        cat = f"cats_{uuid.uuid4().hex[:6]}"
        await _create(client, category=cat)
        resp = await client.get("/api/chat/categories")
        assert resp.status_code == 200
        assert cat in resp.json()


# ── Update ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_recomputes_on_variant_change():
    async with _client() as client:
        data = await _create(client, question_variants=["v1"])
        assert await _embeddings_len(data["id"]) == 2

        resp = await client.put(
            f"/api/chat/qa-pairs/{data['id']}", json={"question_variants": ["v1", "v2", "v3"]}
        )
        assert resp.status_code == 200
        assert resp.json()["variant_count"] == 3
        assert await _embeddings_len(data["id"]) == 4  # recomputed + aligned

        # removing all variants realigns to 1
        resp = await client.put(f"/api/chat/qa-pairs/{data['id']}", json={"question_variants": []})
        assert resp.json()["variant_count"] == 0
        assert await _embeddings_len(data["id"]) == 1


@pytest.mark.asyncio
async def test_update_answer_only_keeps_embeddings():
    embedding_service.set_qa_cache([])  # warm so we can assert it is dropped
    async with _client() as client:
        data = await _create(client, question_variants=["v1"])
        resp = await client.put(f"/api/chat/qa-pairs/{data['id']}", json={"answer": "新答案"})
        assert resp.status_code == 200
        assert resp.json()["answer"] == "新答案"
        assert await _embeddings_len(data["id"]) == 2


@pytest.mark.asyncio
async def test_update_missing_returns_404():
    async with _client() as client:
        resp = await client.put(f"/api/chat/qa-pairs/{uuid.uuid4()}", json={"answer": "x"})
        assert resp.status_code == 404


# ── Soft delete ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_soft_marks_inactive():
    async with _client() as client:
        cat = f"del_{uuid.uuid4().hex[:6]}"
        data = await _create(client, category=cat)
        resp = await client.delete(f"/api/chat/qa-pairs/{data['id']}")
        assert resp.status_code == 204

        listed = await client.get("/api/chat/qa-pairs", params={"category": cat})
        items = listed.json()["items"]
        assert len(items) == 1 and items[0]["is_active"] is False


# ── Rebuild ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_rebuild_recomputes_all():
    async with _client() as client:
        await _create(client, question_variants=["a", "b"])
        resp = await client.post("/api/chat/qa-pairs/rebuild-embeddings")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rebuilt"] >= 1
        assert body["model_name"] == settings.embedding_model_name


# ── Access control ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_non_admin_forbidden():
    async with _client(cookies=auth_cookies("user")) as client:
        assert (await client.get("/api/chat/qa-pairs")).status_code == 403
        assert (await client.post("/api/chat/qa-pairs", json={"question": "q", "answer": "a"})).status_code == 403


@pytest.mark.asyncio
async def test_unauthenticated_unauthorized():
    async with _client(cookies=anonymous_cookies()) as client:
        assert (await client.get("/api/chat/qa-pairs")).status_code == 401
