"""Reconcile the runtime encoder with the vectors actually stored in the KB.

``qa_pairs.embeddings`` are only comparable to a query encoded the same way, and
every row records which encoder produced it. Chat reads and writes adopt the
majority model of the stored vectors, so a restart — whose default comes from
``EMBEDDING_MODEL_NAME`` — keeps serving the knowledge base it was embedded for
instead of scoring garbage against mismatched vectors.

Only stamps that name a loadable encoder are eligible. A row stamped with an id
that is not in the registry (a hand-edited row, an encoder that was later
retired) cannot be loaded at all, so it must never become the active encoder --
otherwise a knowledge base holding just such a row would flip the runtime onto a
model that fails to load, and every question would fall back. Those rows are
instead reported as 待重建 against whatever the configuration says.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa_pair import QAPair
from app.services import embedding_models, embedding_service


async def stored_model_counts(db: AsyncSession) -> dict[str, int]:
    """How many rows were embedded by each model (rows without vectors excluded)."""
    rows = (
        await db.execute(select(QAPair.embedding_model, func.count()).group_by(QAPair.embedding_model))
    ).all()
    return {model: count for model, count in rows if model}


def dominant_model(counts: dict[str, int]) -> str | None:
    """The model holding the most rows; ties break on the name so the choice is
    stable across processes."""
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def loadable_counts(counts: dict[str, int]) -> dict[str, int]:
    """Drop stamps that name no registry encoder (nor a snapshot of one).

    Split out of :func:`reconcile_active_model` so the exclusion rule is testable
    without a database and ``dominant_model`` stays a pure majority helper.
    """
    return {model: count for model, count in counts.items() if embedding_models.option_for(model)}


async def reconcile_active_model(db: AsyncSession) -> str:
    """Point the encoder at the model the knowledge base was built with.

    Majority vote among *loadable* stamps; when nothing loadable is stored, the
    configured default stands. Returns the now-active encoder id.
    """
    chosen = dominant_model(loadable_counts(await stored_model_counts(db)))
    if chosen is not None and chosen != embedding_service.active_model_name():
        embedding_service.set_active_model(chosen)
    return embedding_service.active_model_name()


async def count_needing_rebuild(db: AsyncSession) -> int:
    """Rows whose stored vectors do not belong to the active encoder."""
    active = embedding_service.active_model_name()
    return (
        await db.execute(
            select(func.count()).select_from(QAPair).where(
                QAPair.embedding_model.is_distinct_from(active)
            )
        )
    ).scalar_one()
