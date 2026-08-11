"""Dashboard CRUD endpoints — /api/dashboards."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.dashboard import Dashboard
from app.models.view import View
from app.models.visualization import Visualization
from app.schemas.dashboard import (
    DashboardCreate,
    DashboardListResponse,
    DashboardResponse,
    DashboardTile,
    DashboardUpdate,
)

router = APIRouter(prefix="/api", tags=["dashboards"])


def _dashboard_to_response(dash: Dashboard) -> DashboardResponse:
    """Convert ORM instance to response model."""
    return DashboardResponse(
        id=dash.id,
        name=dash.name,
        description=dash.description,
        layout_json=list(dash.layout_json or []),
        created_at=dash.created_at,
        updated_at=dash.updated_at,
    )


def _dashboard_to_list_response(dash: Dashboard) -> DashboardListResponse:
    """Convert ORM instance to list summary response model."""
    return DashboardListResponse(
        id=dash.id,
        name=dash.name,
        description=dash.description,
        tile_count=len(dash.layout_json or []),
        created_at=dash.created_at,
        updated_at=dash.updated_at,
    )


async def _validate_tile_references(tiles: list[DashboardTile], db: AsyncSession) -> None:
    """Raise 422 if any referenced visualization/view does not exist."""
    viz_ids = {t.visualization_id for t in tiles if t.visualization_id is not None}
    if viz_ids:
        stmt = select(Visualization.id).where(Visualization.id.in_(viz_ids))
        result = await db.execute(stmt)
        found = set(result.scalars().all())
        missing = sorted(str(v) for v in viz_ids - found)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"布局引用了不存在的可视化: {', '.join(missing)}",
            )

    view_ids: set[uuid.UUID] = set()
    for tile in tiles:
        if tile.tile_type == "kpi_card" and tile.config:
            raw_view_id = tile.config.get("view_id")
            if raw_view_id is not None:
                try:
                    view_ids.add(uuid.UUID(str(raw_view_id)))
                except ValueError:
                    raise HTTPException(
                        status_code=422,
                        detail=f"KPI 瓦片的视图ID无效: '{raw_view_id}'",
                    ) from None
    if view_ids:
        stmt = select(View.id).where(View.id.in_(view_ids))
        result = await db.execute(stmt)
        found = set(result.scalars().all())
        missing = sorted(str(v) for v in view_ids - found)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"KPI 瓦片引用了不存在的视图: {', '.join(missing)}",
            )


# ── CRUD Endpoints ──────────────────────────────────────────────────────────


async def _check_name_conflict(
    name: str, db: AsyncSession, *, exclude_id: uuid.UUID | None = None
) -> None:
    """Raise 409 if another dashboard already uses this name.

    Pre-checked via SELECT (instead of catching the flush failure) so the
    session is never left in a pending-rollback state.
    """
    stmt = select(Dashboard.id).where(Dashboard.name == name)
    if exclude_id is not None:
        stmt = stmt.where(Dashboard.id != exclude_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail=f"仪表盘名称 '{name}' 已存在")


@router.get("/dashboards", response_model=list[DashboardListResponse])
async def list_dashboards(db: AsyncSession = Depends(get_db)):
    """List all dashboards (summary)."""
    stmt = select(Dashboard).order_by(Dashboard.created_at.desc())
    result = await db.execute(stmt)
    dashboards = result.scalars().all()
    return [_dashboard_to_list_response(d) for d in dashboards]


@router.get("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def get_dashboard(dashboard_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single dashboard by ID (full detail incl. layout_json)."""
    stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
    result = await db.execute(stmt)
    dash = result.scalar_one_or_none()
    if dash is None:
        raise HTTPException(status_code=404, detail=f"仪表盘 '{dashboard_id}' 不存在")
    return _dashboard_to_response(dash)


@router.post("/dashboards", response_model=DashboardResponse, status_code=201)
async def create_dashboard(body: DashboardCreate, db: AsyncSession = Depends(get_db)):
    """Create a new dashboard."""
    await _check_name_conflict(body.name, db)
    await _validate_tile_references(body.layout_json, db)

    dash = Dashboard(
        name=body.name,
        description=body.description,
        layout_json=[t.model_dump(mode="json") for t in body.layout_json],
    )
    db.add(dash)
    try:
        await db.flush()
    except Exception as e:
        # Safety net for a concurrent insert racing the pre-check above
        await db.rollback()
        if "uq_dashboards_name" in str(e) or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"仪表盘名称 '{body.name}' 已存在",
            ) from e
        raise
    await db.refresh(dash)
    return _dashboard_to_response(dash)


@router.put("/dashboards/{dashboard_id}", response_model=DashboardResponse)
async def update_dashboard(
    dashboard_id: uuid.UUID,
    body: DashboardUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing dashboard's name/description/layout."""
    stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
    result = await db.execute(stmt)
    dash = result.scalar_one_or_none()
    if dash is None:
        raise HTTPException(status_code=404, detail=f"仪表盘 '{dashboard_id}' 不存在")

    if body.name is not None and body.name != dash.name:
        await _check_name_conflict(body.name, db, exclude_id=dash.id)

    if body.layout_json is not None:
        await _validate_tile_references(body.layout_json, db)
        dash.layout_json = [t.model_dump(mode="json") for t in body.layout_json]
    if body.name is not None:
        dash.name = body.name
    if body.description is not None:
        dash.description = body.description

    try:
        await db.flush()
    except Exception as e:
        # Safety net for a concurrent rename racing the pre-check above
        await db.rollback()
        if "uq_dashboards_name" in str(e) or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"仪表盘名称 '{dash.name}' 已存在",
            ) from e
        raise
    await db.refresh(dash)
    return _dashboard_to_response(dash)


@router.delete("/dashboards/{dashboard_id}", status_code=204)
async def delete_dashboard(dashboard_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a dashboard."""
    stmt = select(Dashboard).where(Dashboard.id == dashboard_id)
    result = await db.execute(stmt)
    dash = result.scalar_one_or_none()
    if dash is None:
        raise HTTPException(status_code=404, detail=f"仪表盘 '{dashboard_id}' 不存在")
    await db.delete(dash)
    await db.flush()
