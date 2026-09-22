"""Admin-only Q&A knowledge-base CRUD — /api/chat/qa-pairs.

Every write keeps the invariant ``len(embeddings) == 1 + len(question_variants)``
(index 0 = canonical question, 1..N = variants) and drops the in-memory match
cache so the next ask reloads from the DB.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.qa_pair import QAPair
from app.schemas.chat import (
    ActivateEmbeddingModelRequest,
    EmbeddingModelListResponse,
    EmbeddingModelOptionResponse,
    QAPairCreate,
    QAPairPage,
    QAPairResponse,
    QAPairUpdate,
    RebuildResult,
)
from app.services import embedding_models, embedding_service, model_selection

router = APIRouter(prefix="/api/chat", tags=["chat-admin"])


def _to_response(pair: QAPair) -> QAPairResponse:
    variants = list(pair.question_variants or [])
    return QAPairResponse(
        id=pair.id,
        question=pair.question,
        question_variants=variants,
        answer=pair.answer,
        category=pair.category,
        is_active=pair.is_active,
        has_embeddings=bool(pair.embeddings),
        embedding_model=pair.embedding_model,
        needs_rebuild=pair.embedding_model != embedding_service.active_model_name(),
        variant_count=len(variants),
        created_at=pair.created_at,
        updated_at=pair.updated_at,
    )


async def _load_pair_or_404(pair_id: uuid.UUID, db: AsyncSession) -> QAPair:
    result = await db.execute(select(QAPair).where(QAPair.id == pair_id))
    pair = result.scalar_one_or_none()
    if pair is None:
        raise HTTPException(status_code=404, detail=f"问答 '{pair_id}' 不存在")
    return pair


def _sync_embeddings(pair: QAPair) -> None:
    """(Re)compute embeddings for [question, *variants] and enforce alignment."""
    texts = [pair.question, *pair.question_variants]
    pair.embeddings = embedding_service.compute_embeddings(texts)
    # Stamp the encoder so a later model switch is detectable per row.
    pair.embedding_model = embedding_service.active_model_name()
    if len(pair.embeddings) != 1 + len(pair.question_variants):
        # Defensive: a misaligned batch must never be persisted.
        raise HTTPException(status_code=500, detail="向量数量与问法数量不一致")


@router.get("/qa-pairs", response_model=QAPairPage)
async def list_qa_pairs(
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=200, description="每页数量"),
    category: str | None = Query(None, description="按分类筛选"),
    db: AsyncSession = Depends(get_db),
):
    """List Q&A pairs (paginated, incl. inactive; optional category filter)."""
    # Reconcile first so the per-row ``needs_rebuild`` flag is judged against the
    # encoder the knowledge base actually uses, not the env default.
    await model_selection.reconcile_active_model(db)
    stmt = select(QAPair)
    if category:
        stmt = stmt.where(QAPair.category == category)
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                stmt.order_by(QAPair.created_at.desc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    return QAPairPage(items=[_to_response(r) for r in rows], total=total, page=page, size=size)


@router.get("/categories", response_model=list[str])
async def list_categories(db: AsyncSession = Depends(get_db)):
    """Distinct non-empty categories, for the admin filter/datalist."""
    rows = (
        (await db.execute(select(QAPair.category).where(QAPair.category.isnot(None)).distinct()))
        .scalars()
        .all()
    )
    return sorted({r for r in rows if r})


@router.post("/qa-pairs", response_model=QAPairResponse, status_code=201)
async def create_qa_pair(
    body: QAPairCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a Q&A pair; embeddings for the question + every variant are computed on write."""
    # Write with the encoder the rest of the knowledge base already uses.
    await model_selection.reconcile_active_model(db)
    pair = QAPair(
        question=body.question,
        question_variants=body.question_variants,
        answer=body.answer,
        category=(body.category.strip() if body.category else None) or None,
        is_active=body.is_active,
    )
    _sync_embeddings(pair)
    db.add(pair)
    await db.flush()
    await db.refresh(pair)
    embedding_service.invalidate_qa_cache()
    return _to_response(pair)


@router.put("/qa-pairs/{pair_id}", response_model=QAPairResponse)
async def update_qa_pair(
    pair_id: uuid.UUID,
    body: QAPairUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a Q&A pair; recompute embeddings when the question/variants changed."""
    pair = await _load_pair_or_404(pair_id, db)
    await model_selection.reconcile_active_model(db)

    question_changed = False
    variants_changed = False

    if body.question is not None and body.question != pair.question:
        pair.question = body.question
        question_changed = True
    if body.question_variants is not None and body.question_variants != list(pair.question_variants or []):
        pair.question_variants = body.question_variants
        variants_changed = True
    if body.answer is not None:
        pair.answer = body.answer
    if body.category is not None:
        pair.category = body.category.strip() or None
    if body.is_active is not None:
        pair.is_active = body.is_active

    if question_changed or variants_changed or not pair.embeddings:
        _sync_embeddings(pair)

    await db.flush()
    await db.refresh(pair)
    embedding_service.invalidate_qa_cache()
    return _to_response(pair)


@router.post("/qa-pairs/rebuild-embeddings", response_model=RebuildResult)
async def rebuild_embeddings(db: AsyncSession = Depends(get_db)):
    """Recompute embeddings for every pair (all + active/inactive) after a model change."""
    rows = (await db.execute(select(QAPair))).scalars().all()
    for pair in rows:
        _sync_embeddings(pair)
    await db.flush()
    embedding_service.invalidate_qa_cache()
    return RebuildResult(rebuilt=len(rows), model_name=embedding_service.active_model_name())


@router.get("/embedding-models", response_model=EmbeddingModelListResponse)
async def list_embedding_models(db: AsyncSession = Depends(get_db)):
    """Candidate encoders, the one in effect, and how many rows need a rebuild."""
    active = await model_selection.reconcile_active_model(db)
    option = embedding_models.option_for(active)
    return EmbeddingModelListResponse(
        items=[
            EmbeddingModelOptionResponse(name=o.name, label=o.label, dims=o.dims, note=o.note)
            for o in embedding_models.EMBEDDING_MODEL_OPTIONS
        ],
        active_model=active,
        active_label=option.label if option else active,
        threshold=settings.chat_similarity_threshold,
        needs_rebuild=await model_selection.count_needing_rebuild(db),
    )


@router.post("/embedding-models/activate", response_model=RebuildResult)
async def activate_embedding_model(
    body: ActivateEmbeddingModelRequest,
    db: AsyncSession = Depends(get_db),
):
    """Switch encoder *and* rebuild every vector — one action, never half done.

    Vectors from two encoders are not comparable, so a switch without a rebuild
    would silently degrade (or break) matching; the rebuild happens in the same
    transaction and rolls back if the new weights cannot be loaded.
    """
    option = embedding_models.find_option(body.model_name.strip())
    if option is None:
        raise HTTPException(status_code=400, detail=f"不是候选向量模型：{body.model_name}")

    previous = embedding_service.active_model_name()
    embedding_service.set_active_model(option.name)
    rows = (await db.execute(select(QAPair))).scalars().all()
    try:
        for pair in rows:
            _sync_embeddings(pair)
    except Exception as e:  # missing weights / encoder failure → undo the switch
        embedding_service.set_active_model(previous)
        embedding_service.invalidate_qa_cache()
        raise HTTPException(
            status_code=400,
            detail=f"切换向量模型失败（请确认模型权重已预置到服务器）：{e}",
        ) from e
    await db.flush()
    embedding_service.invalidate_qa_cache()
    return RebuildResult(rebuilt=len(rows), model_name=option.name)


@router.delete("/qa-pairs/{pair_id}", status_code=204)
async def delete_qa_pair(
    pair_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Soft delete: mark inactive so existing messages keep their FK target."""
    pair = await _load_pair_or_404(pair_id, db)
    pair.is_active = False
    await db.flush()
    embedding_service.invalidate_qa_cache()
    return None
