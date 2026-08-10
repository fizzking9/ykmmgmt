"""Visualization CRUD endpoints — /api/visualizations."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.view import View
from app.models.visualization import Visualization
from app.routers.views import _build_sql_from_config
from app.schemas.view import ViewConfig
from app.schemas.visualization import (
    VisualizationCreate,
    VisualizationDataResponse,
    VisualizationListResponse,
    VisualizationResponse,
    VisualizationUpdate,
    validate_config_keys,
)
from app.services.view_sql_builder import SQLBuildError

router = APIRouter(prefix="/api", tags=["visualizations"])


def _viz_to_response(viz: Visualization) -> VisualizationResponse:
    """Convert ORM instance to response model."""
    return VisualizationResponse(
        id=viz.id,
        name=viz.name,
        view_id=viz.view_id,
        chart_type=viz.chart_type,
        config_json=viz.config_json,
        created_at=viz.created_at,
        updated_at=viz.updated_at,
    )


async def _validate_view_exists(view_id: uuid.UUID, db: AsyncSession) -> None:
    """Raise 422 if the referenced view does not exist."""
    stmt = select(View.id).where(View.id == view_id)
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=422, detail=f"视图 '{view_id}' 不存在")


def _validate_chart_config(chart_type: str, config_json: dict) -> None:
    """Raise 422 if required config keys are missing for the chart type."""
    missing = validate_config_keys(chart_type, config_json)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"图表类型 '{chart_type}' 缺少必需的配置项: {', '.join(missing)}",
        )


# ── CRUD Endpoints ──────────────────────────────────────────────────────────


@router.get("/visualizations", response_model=list[VisualizationListResponse])
async def list_visualizations(db: AsyncSession = Depends(get_db)):
    """List all saved visualizations (summary)."""
    stmt = select(Visualization).order_by(Visualization.created_at.desc())
    result = await db.execute(stmt)
    viz_list = result.scalars().all()
    return [VisualizationListResponse.model_validate(v) for v in viz_list]


@router.get("/visualizations/{viz_id}", response_model=VisualizationResponse)
async def get_visualization(viz_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single visualization by ID (full detail)."""
    stmt = select(Visualization).where(Visualization.id == viz_id)
    result = await db.execute(stmt)
    viz = result.scalar_one_or_none()
    if viz is None:
        raise HTTPException(status_code=404, detail=f"可视化 '{viz_id}' 不存在")
    return _viz_to_response(viz)


@router.post("/visualizations", response_model=VisualizationResponse, status_code=201)
async def create_visualization(body: VisualizationCreate, db: AsyncSession = Depends(get_db)):
    """Create a new visualization."""
    await _validate_view_exists(body.view_id, db)
    _validate_chart_config(body.chart_type, body.config_json)

    viz = Visualization(
        name=body.name,
        view_id=body.view_id,
        chart_type=body.chart_type,
        config_json=body.config_json,
    )
    db.add(viz)
    try:
        await db.flush()
    except Exception as e:
        if "uq_visualizations_name" in str(e) or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"可视化名称 '{body.name}' 已存在",
            ) from e
        raise
    await db.refresh(viz)
    return _viz_to_response(viz)


@router.put("/visualizations/{viz_id}", response_model=VisualizationResponse)
async def update_visualization(
    viz_id: uuid.UUID,
    body: VisualizationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing visualization."""
    stmt = select(Visualization).where(Visualization.id == viz_id)
    result = await db.execute(stmt)
    viz = result.scalar_one_or_none()
    if viz is None:
        raise HTTPException(status_code=404, detail=f"可视化 '{viz_id}' 不存在")

    # Determine effective values for validation
    effective_view_id = body.view_id if body.view_id is not None else viz.view_id
    effective_chart_type = body.chart_type if body.chart_type is not None else viz.chart_type
    effective_config = body.config_json if body.config_json is not None else viz.config_json

    await _validate_view_exists(effective_view_id, db)
    _validate_chart_config(effective_chart_type, effective_config)

    if body.name is not None:
        viz.name = body.name
    if body.view_id is not None:
        viz.view_id = body.view_id
    if body.chart_type is not None:
        viz.chart_type = body.chart_type
    if body.config_json is not None:
        viz.config_json = body.config_json

    await db.flush()
    await db.refresh(viz)
    return _viz_to_response(viz)


@router.delete("/visualizations/{viz_id}", status_code=204)
async def delete_visualization(viz_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a visualization."""
    stmt = select(Visualization).where(Visualization.id == viz_id)
    result = await db.execute(stmt)
    viz = result.scalar_one_or_none()
    if viz is None:
        raise HTTPException(status_code=404, detail=f"可视化 '{viz_id}' 不存在")
    await db.delete(viz)
    await db.flush()


# ── Data Endpoint ───────────────────────────────────────────────────────────


@router.get("/visualizations/{viz_id}/data", response_model=VisualizationDataResponse)
async def get_visualization_data(viz_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Execute the associated view's SQL and return full result set for charting."""
    stmt = select(Visualization).where(Visualization.id == viz_id)
    result = await db.execute(stmt)
    viz = result.scalar_one_or_none()
    if viz is None:
        raise HTTPException(status_code=404, detail=f"可视化 '{viz_id}' 不存在")

    # Fetch the associated view
    view_stmt = select(View).where(View.id == viz.view_id)
    view_result = await db.execute(view_stmt)
    view = view_result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=404, detail=f"关联视图 '{viz.view_id}' 不存在")

    if not view.generated_sql:
        raise HTTPException(status_code=400, detail="该视图没有存储的 SQL")

    # Regenerate SQL + params from the stored config so parameterized
    # filters (date ranges, operator values) have matching bind values —
    # executing the raw generated_sql without params fails on filtered views.
    config = ViewConfig.model_validate(view.config_json)
    try:
        sql, params = _build_sql_from_config(config, apply_limit=True)
    except SQLBuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Execute full query (no pagination)
    try:
        data_result = await db.execute(text(sql), params)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"查询执行失败: {e}",
        ) from e

    columns = list(data_result.keys())

    # Serialize rows
    rows: list[dict] = []
    for row in data_result.mappings().all():
        row_dict: dict = {}
        for key, val in row.items():
            if isinstance(val, dt.datetime):
                row_dict[key] = val.isoformat()
            elif isinstance(val, dt.date):
                row_dict[key] = val.isoformat()
            elif isinstance(val, uuid.UUID):
                row_dict[key] = str(val)
            else:
                row_dict[key] = val
        rows.append(row_dict)

    return VisualizationDataResponse(
        columns=columns,
        rows=rows,
        chart_type=viz.chart_type,
        config_json=viz.config_json,
    )
