"""Tests for admin-selectable embedding encoders (encoder switch + rebuild).

A deterministic fake provider stands in for the encoder, so these exercise the
real write path (stamp / switch / reconcile / stale filtering) without torch.
Every test snapshots ``qa_pairs`` and restores it afterwards: activating an
encoder rebuilds *all* rows, which must not leave the dev knowledge base holding
fake vectors.
"""

import asyncio
import hashlib
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.qa_pair import QAPair
from app.routers.chat import _matchable_entries
from app.services import embedding_models, embedding_service, model_selection
from app.services.embedding_service import QACacheEntry
from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")

_created_ids: list[str] = []
_SWITCH_TARGET = "BAAI/bge-small-zh-v1.5"


def _provider(texts: list[str]) -> list[list[float]]:
    """Sparse but *distinct* vector per text — stale/matching logic needs variety."""
    out = []
    for t in texts:
        vec = [0.0] * 32
        bucket = int(hashlib.blake2b(t.encode("utf-8"), digest_size=4).hexdigest(), 16) % 32
        vec[bucket] = 1.0
        out.append(vec)
    return out


def _client(cookies: dict[str, str] | None = None) -> AsyncClient:
    transport = ASGITransport(app=app)
    if cookies is not None:
        return AsyncClient(transport=transport, base_url="http://test", cookies=cookies)
    return AsyncClient(transport=transport, base_url="http://test")


async def _snapshot() -> list[dict]:
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            rows = (await session.execute(select(QAPair))).scalars().all()
            return [
                {"id": r.id, "embeddings": r.embeddings, "embedding_model": r.embedding_model} for r in rows
            ]
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def _isolated_encoder():
    """Fake encoder for the test, knowledge base restored to its exact prior state."""
    before = asyncio.run(_snapshot())
    embedding_service.set_provider(_provider)
    embedding_service.reset_active_model()
    yield
    embedding_service.set_provider(None)
    embedding_service.reset_active_model()
    embedding_service.invalidate_qa_cache()
    if _created_ids:
        asyncio.run(_delete_created(list(_created_ids)))
        _created_ids.clear()
    asyncio.run(_restore_snapshot(before))


async def _delete_created(ids: list[str]) -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(QAPair).where(QAPair.id.in_([uuid.UUID(i) for i in ids])))
            await session.commit()
    finally:
        await engine.dispose()


async def _restore_snapshot(snapshot: list[dict]) -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            for row in snapshot:
                pair = (
                    await session.execute(select(QAPair).where(QAPair.id == row["id"]))
                ).scalar_one_or_none()
                if pair is not None:
                    pair.embeddings = row["embeddings"]
                    pair.embedding_model = row["embedding_model"]
            await session.commit()
    finally:
        await engine.dispose()


async def _create(client: AsyncClient, **payload) -> dict:
    payload.setdefault("question", f"问题_{uuid.uuid4().hex[:8]}？")
    payload.setdefault("answer", "答案")
    resp = await client.post("/api/chat/qa-pairs", json=payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    _created_ids.append(data["id"])
    return data


async def _stored_model(pair_id: str) -> str | None:
    async with async_session_factory() as session:
        return (
            await session.execute(select(QAPair.embedding_model).where(QAPair.id == uuid.UUID(pair_id)))
        ).scalar_one()


# ── Registry + listing ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_embedding_models_endpoint_lists_options():
    async with _client() as client:
        resp = await client.get("/api/chat/embedding-models")
        assert resp.status_code == 200
        data = resp.json()

    assert data["items"], "候选模型列表不能为空"
    # 生效模型要么在候选列表里，要么是 .env 默认值（知识库尚无向量时）
    assert data["active_model"] in {o["name"] for o in data["items"]} or data[
        "active_model"
    ] == settings.embedding_model_name
    assert data["threshold"] == settings.chat_similarity_threshold
    for option in data["items"]:
        assert option["dims"] > 0
        assert any("\u4e00" <= ch <= "\u9fff" for ch in option["label"]), option["label"]
        # 每个候选都必须可被 activate 接受
        assert embedding_models.find_option(option["name"]) is not None


@pytest.mark.asyncio
async def test_create_stamps_active_encoder():
    async with _client() as client:
        data = await _create(client, question="上传文件支持哪些格式？")
    assert data["embedding_model"] == embedding_service.active_model_name()
    assert data["needs_rebuild"] is False
    assert await _stored_model(data["id"]) == embedding_service.active_model_name()


# ── Activate (switch + rebuild) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activate_rejects_unknown_encoder():
    async with _client() as client:
        resp = await client.post("/api/chat/embedding-models/activate", json={"model_name": "不存在的模型"})
        assert resp.status_code == 400
    assert embedding_service.active_model_name() == settings.embedding_model_name


@pytest.mark.asyncio
async def test_activate_switches_encoder_and_rebuilds_every_pair():
    async with _client() as client:
        mine = await _create(client, question="切换模型后向量会重算吗？")

        resp = await client.post("/api/chat/embedding-models/activate", json={"model_name": _SWITCH_TARGET})
        assert resp.status_code == 200, resp.text
        assert resp.json()["model_name"] == _SWITCH_TARGET
        assert resp.json()["rebuilt"] >= 1

        assert await _stored_model(mine["id"]) == _SWITCH_TARGET
        assert embedding_service.active_model_name() == _SWITCH_TARGET

        listed = (await client.get("/api/chat/embedding-models")).json()
        assert listed["active_model"] == _SWITCH_TARGET
        # Switch always rebuilds, so nothing may be left waiting for one.
        assert listed["needs_rebuild"] == 0


# ── Stale vectors must never be matched ─────────────────────────────────────


@pytest.mark.asyncio
async def test_pair_from_other_encoder_is_excluded_from_matching():
    async with _client() as client:
        mine = await _create(client, question="这条会被跳过吗？")

    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine)() as session:
            pair = (
                await session.execute(select(QAPair).where(QAPair.id == uuid.UUID(mine["id"])))
            ).scalar_one()
            pair.embedding_model = "some-other-encoder"
            await session.commit()
        embedding_service.invalidate_qa_cache()

        async with async_sessionmaker(engine)() as session:
            entries = await _matchable_entries(session)
    finally:
        await engine.dispose()

    assert mine["id"] not in {e.id for e in entries}
    embedding_service.invalidate_qa_cache()


@pytest.mark.asyncio
async def test_dominant_model_chooses_the_majority_encoder():
    assert model_selection.dominant_model({}) is None
    assert model_selection.dominant_model({"a": 2, "b": 5}) == "b"
    # 同票数按名称排序 → 多进程结果一致
    assert model_selection.dominant_model({"z-enc": 3, "a-enc": 3}) == "z-enc"


@pytest.mark.asyncio
async def test_stored_model_counts_reads_per_row_encoder_stamps():
    engine = create_async_engine(settings.database_url)
    ids: list[uuid.UUID] = []
    # Both stamps must be real registry encoders: reconcile only ever adopts a
    # stamp it can load, so a fake id here would assert nothing about the vote.
    minority = "BAAI/bge-base-zh-v1.5"
    try:
        async with async_sessionmaker(engine)() as session:
            for model in (_SWITCH_TARGET, _SWITCH_TARGET, minority):
                pair = QAPair(
                    question=f"多数派_{uuid.uuid4().hex[:6]}？",
                    question_variants=[],
                    answer="答案",
                    embeddings=[[0.0] * 4],
                    embedding_model=model,
                    is_active=True,
                )
                session.add(pair)
                await session.flush()
                ids.append(pair.id)
            await session.commit()

        async with async_sessionmaker(engine)() as session:
            counts = await model_selection.stored_model_counts(session)
            # reconcile 后置不变式：生效模型 = 库内可加载戳记的多数派（无记录时保持默认）
            active = await model_selection.reconcile_active_model(session)

        assert counts.get(_SWITCH_TARGET) == 2 and counts.get(minority) == 1
        expected = model_selection.dominant_model(model_selection.loadable_counts(counts))
        assert active == (expected or settings.embedding_model_name)
    finally:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(QAPair).where(QAPair.id.in_(ids)))
            await session.commit()
        await engine.dispose()
        embedding_service.reset_active_model()


@pytest.mark.asyncio
async def test_unloadable_stamp_is_never_adopted_as_the_active_encoder():
    """A knowledge base of retired/hand-edited stamps must not hijack the encoder.

    Majority-of-one is the dangerous case: with every row stamped by an id that
    cannot be loaded, adopting the "majority" would point the runtime at a model
    that fails to load and make every question fall back. Those rows are instead
    reported as 待重建 while the configured encoder keeps serving.
    """
    assert model_selection.loadable_counts({"ghost-encoder": 9, _SWITCH_TARGET: 1}) == {_SWITCH_TARGET: 1}
    assert model_selection.loadable_counts({}) == {}

    engine = create_async_engine(settings.database_url)
    ids: list[uuid.UUID] = []
    try:
        async with async_sessionmaker(engine)() as session:
            for _ in range(3):  # an outright majority of unloadable stamps
                pair = QAPair(
                    question=f"无法加载_{uuid.uuid4().hex[:6]}？",
                    question_variants=[],
                    answer="答案",
                    embeddings=[[0.0] * 4],
                    embedding_model="totally-unknown-encoder",
                    is_active=True,
                )
                session.add(pair)
                await session.flush()
                ids.append(pair.id)
            await session.commit()

        async with async_sessionmaker(engine)() as session:
            active = await model_selection.reconcile_active_model(session)
            needing = await model_selection.count_needing_rebuild(session)
    finally:
        async with async_sessionmaker(engine)() as session:
            await session.execute(delete(QAPair).where(QAPair.id.in_(ids)))
            await session.commit()
        await engine.dispose()
        embedding_service.reset_active_model()

    assert active != "totally-unknown-encoder"
    assert embedding_models.option_for(active) is not None, "reconcile adopted an unloadable encoder"
    assert needing >= 3, "the foreign-stamped rows should be surfaced as 待重建"


# ── Query-side instruction ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_mismatched_vector_dimensions_are_skipped_not_fatal():
    """A leftover vector from another encoder must degrade to fallback, not 500."""
    query = [1.0] + [0.0] * 7
    entries = [
        QACacheEntry(
            id="stale", question="旧模型写入", category=None, embeddings=[[0.0] * 4, [1.0] + [0.0] * 3], answer="旧"
        ),
        QACacheEntry(id="fresh", question="当前模型写入", category=None, embeddings=[query], answer="新"),
    ]
    result = embedding_service.find_best_match(query, entries, threshold=0.5)
    assert result is not None
    assert result.pair_id == "fresh"


@pytest.mark.asyncio
async def test_query_instruction_applies_to_queries_only(monkeypatch):
    seen: list[list[str]] = []

    def provider(texts: list[str]) -> list[list[float]]:
        seen.append(list(texts))
        return [[0.1] * 4 for _ in texts]

    option = embedding_models.EmbeddingModelOption(
        name="test-instructed",
        label="测试模型",
        dims=4,
        note="仅用于测试",
        query_prefix="Instruct: ",
    )
    monkeypatch.setattr(embedding_models, "EMBEDDING_MODEL_OPTIONS", [option])
    embedding_service.set_provider(provider)
    embedding_service.set_active_model("test-instructed")

    embedding_service.encode_query("今天的接待量")
    embedding_service.compute_embeddings(["今天的接待量", "今日接待情况"])

    assert seen[0] == ["Instruct: 今天的接待量"]  # 查询侧带指令
    assert seen[1] == ["今天的接待量", "今日接待情况"]  # 知识库侧不带
