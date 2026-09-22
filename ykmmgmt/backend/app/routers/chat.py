"""Chat runtime API — semantic ask + per-user session management (authenticated).

The active-pair embeddings are served from the embedding-service cache, warmed
on first ask from the DB and invalidated by every admin CRUD write (see
chat_admin). Every ask is logged with its top match so near-threshold misses can
be reviewed (tuning loop, plan Group 8).
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.chat_message import ROLE_ASSISTANT, ROLE_USER, ChatMessage
from app.models.chat_session import ChatSession
from app.models.qa_pair import QAPair
from app.models.user import User
from app.schemas.chat import (
    AskRequest,
    AskResponse,
    ChatMessagePage,
    ChatMessageResponse,
    SessionResponse,
)
from app.services import embedding_service, model_selection, time_window
from app.services.embedding_service import QACacheEntry

logger = logging.getLogger("ykmmgmt.chat")

router = APIRouter(prefix="/api/chat", tags=["chat"])

FALLBACK_ANSWER = (
    "抱歉，我暂时没有找到与您问题匹配的答案。\n\n"
    "您可以尝试：\n"
    "- 换一种更具体的问法\n"
    "- 点击下方推荐问题快速提问"
)


# ── Cache / matching helpers ────────────────────────────────────────────────


async def _matchable_entries(db: AsyncSession) -> list[QACacheEntry]:
    """Return cached active-pair entries, warming from the DB on a cold cache.

    While cold, the encoder is reconciled with what the rows say embedded them and
    any pair whose vectors belong to a different encoder is skipped — cosine
    across two encoders is meaningless, so stale rows must fall back rather than
    answer from a wrong match.
    """
    cached = embedding_service.get_qa_cache()
    if cached is not None:
        return cached
    await model_selection.reconcile_active_model(db)
    active = embedding_service.active_model_name()
    rows = (
        (await db.execute(select(QAPair).where(QAPair.is_active.is_(True)))).scalars().all()
    )
    stale = 0
    entries: list[QACacheEntry] = []
    for r in rows:
        if r.embedding_model != active:
            stale += 1
            continue
        entries.append(
            QACacheEntry(
                id=str(r.id),
                question=r.question,
                category=r.category,
                embeddings=[list(vec) for vec in (r.embeddings or [])],
                answer=r.answer,
            )
        )
    if stale:
        logger.warning(
            "chat_kb_stale skipped=%d active_model=%s —— 这些问答的向量属于其他模型，需在问答管理页重建全部向量",
            stale,
            active,
        )
    embedding_service.set_qa_cache(entries)
    return entries


def _log_ask(
    query: str, top, threshold: float, matched: bool, window_rejected: bool = False
) -> None:
    """Structured ask log incl. near-threshold misses (Group 8 refinement loop)."""
    if top is None:
        logger.info("chat_ask result=no_candidates query=%r", query[:200])
        return
    record = {
        "query": query[:200],
        "top_match_qa_id": top.pair_id,
        "top_similarity": round(top.score, 4),
        "matched_variant_index": top.variant_index,
        "above_threshold": top.score >= threshold,
        "window_guard_rejected": window_rejected,
    }
    near_lo = threshold - settings.chat_log_near_threshold_window
    if window_rejected:
        # Score was accepted; the calendar window was not. Logged separately so the
        # review loop can tell "needs a new pair for that period" from "needs a variant".
        logger.warning("chat_ask_window_guard %s", record)
    elif matched:
        logger.info("chat_ask %s", record)
    elif top.score >= near_lo:
        logger.warning("chat_ask_near_miss %s", record)
    else:
        logger.info("chat_ask_miss %s", record)


# ── Ask ─────────────────────────────────────────────────────────────────────


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Match the message against the Q&A knowledge base and record the exchange."""
    if body.session_id is not None:
        session = await _owned_session(body.session_id, user, db)
    else:
        session = ChatSession(user_id=user.id)
        db.add(session)
        await db.flush()
        await db.refresh(session)

    # Reconcile + load the KB first: the encoder that scores this message must be
    # the one the stored vectors were built with.
    entries = await _matchable_entries(db)
    query_embedding = embedding_service.encode_query(body.message)
    threshold = settings.chat_similarity_threshold
    best = embedding_service.find_best_match(query_embedding, entries, threshold)
    top = embedding_service.peek_best_match(query_embedding, entries)

    # A clear score is not yet an answer: no encoder we benchmarked can tell 上周 from
    # 本周, and each pair reports for exactly one period. Contradicting windows fall
    # back rather than serve the neighbouring period's numbers.
    window_rejected = best is not None and time_window.windows_conflict(body.message, best.question)
    if window_rejected:
        best = None

    db.add(ChatMessage(session_id=session.id, role=ROLE_USER, content=body.message))

    if best is not None:
        entry = next(e for e in entries if e.id == best.pair_id)
        answer = entry.answer
        db.add(
            ChatMessage(
                session_id=session.id,
                role=ROLE_ASSISTANT,
                content=answer,
                matched_qa_id=uuid.UUID(best.pair_id),
                matched_variant_index=best.variant_index,
                similarity_score=best.score,
            )
        )
    else:
        answer = FALLBACK_ANSWER
        db.add(ChatMessage(session_id=session.id, role=ROLE_ASSISTANT, content=answer))

    session.last_active_at = datetime.now(UTC)
    await db.flush()

    _log_ask(body.message, top, threshold, best is not None, window_rejected)

    return AskResponse(
        answer=answer,
        session_id=session.id,
        matched_question=best.question if best else None,
        matched_variant_index=best.variant_index if best else None,
        similarity_score=round(best.score, 4) if best else None,
        matched=best is not None,
    )


# ── Sessions ────────────────────────────────────────────────────────────────


@router.get("/suggestions", response_model=list[str])
async def suggestions(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sample canonical questions from active pairs, for the widget's empty state."""
    rows = (
        (
            await db.execute(
                select(QAPair.question)
                .where(QAPair.is_active.is_(True))
                .order_by(QAPair.created_at.desc())
                .limit(6)
            )
        )
        .scalars()
        .all()
    )
    return list(rows)


async def _owned_session(session_id: uuid.UUID, user: User, db: AsyncSession) -> ChatSession:
    result = await db.execute(select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    # 404 (not 403) so a foreign session's existence is not leaked
    if session is None or session.user_id != user.id:
        raise HTTPException(status_code=404, detail=f"会话 '{session_id}' 不存在")
    return session


def _session_response(session: ChatSession) -> SessionResponse:
    return SessionResponse(
        id=session.id, created_at=session.created_at, last_active_at=session.last_active_at
    )


def _message_response(msg: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=msg.id,
        role=msg.role,
        content=msg.content,
        matched_qa_id=msg.matched_qa_id,
        matched_variant_index=msg.matched_variant_index,
        similarity_score=msg.similarity_score,
        created_at=msg.created_at,
    )


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = ChatSession(user_id=user.id)
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return _session_response(session)


@router.get("/sessions", response_model=list[SessionResponse])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = (
        (
            await db.execute(
                select(ChatSession)
                .where(ChatSession.user_id == user.id)
                .order_by(ChatSession.last_active_at.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_session_response(r) for r in rows]


@router.get("/sessions/{session_id}/messages", response_model=ChatMessagePage)
async def session_messages(
    session_id: uuid.UUID,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(50, ge=1, le=200, description="每页数量"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Chronological message history for the current user's session."""
    await _owned_session(session_id, user, db)
    base = select(ChatMessage).where(ChatMessage.session_id == session_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one()
    rows = (
        (
            await db.execute(
                base.order_by(ChatMessage.created_at.asc()).offset((page - 1) * size).limit(size)
            )
        )
        .scalars()
        .all()
    )
    return ChatMessagePage(items=[_message_response(r) for r in rows], total=total, page=page, size=size)


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a session; its messages are removed by the FK ON DELETE CASCADE."""
    session = await _owned_session(session_id, user, db)
    await db.delete(session)
    await db.flush()
    return None
