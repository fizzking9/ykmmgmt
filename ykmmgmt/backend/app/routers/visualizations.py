"""Visualization CRUD endpoints — /api/visualizations."""

import datetime as dt
import re
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
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


Granularity = Literal["year", "quarter", "month", "week", "day"]
AggFunction = Literal["SUM", "COUNT", "AVG", "MIN", "MAX"]


def _parse_iso_datetime(value: str, label: str) -> dt.datetime:
    """Parse an ISO date or datetime string; raise 422 (Chinese) on failure."""
    try:
        return dt.datetime.fromisoformat(value)
    except ValueError:
        pass
    try:
        return dt.datetime.combine(dt.date.fromisoformat(value), dt.time.min)
    except ValueError as e:
        raise HTTPException(
            status_code=422,
            detail=f"{label}格式无效: '{value}'，请使用 ISO 日期格式（如 2026-01-01）",
        ) from e


async def _apply_time_profile(
    db: AsyncSession,
    base_sql: str,
    params: dict,
    date_column: str,
    start: str | None,
    end: str | None,
    granularity: Granularity | None,
    agg: AggFunction | None,
) -> tuple[str, dict]:
    """Wrap the base query with a parameterized date filter.

    Values stay bound — never interpolated. Granularity re-bucketing is
    applied as post-processing in ``_rebucket_rows`` (views may mix column
    types, which SQL-level SUM() cannot handle generically).
    """
    if not re.fullmatch(r"\w+", date_column):
        raise HTTPException(status_code=422, detail=f"无效的时间列名: '{date_column}'")
    quoted = f'"{date_column}"'

    merged = dict(params)
    where_parts: list[str] = []
    if start:
        merged["tp_start"] = _parse_iso_datetime(start, "起始时间")
        where_parts.append(f"{quoted} >= :tp_start")
    if end:
        merged["tp_end"] = _parse_iso_datetime(end, "结束时间")
        where_parts.append(f"{quoted} <= :tp_end")

    sql = base_sql
    if where_parts:
        sql = f"SELECT * FROM ({sql}) AS _tf WHERE {' AND '.join(where_parts)}"

    return sql, merged


def _bucket_key(value: object, granularity: Granularity) -> dt.datetime | None:
    """Truncate a date/datetime (or ISO string) to the requested bucket."""
    d: dt.datetime | dt.date | None
    if isinstance(value, dt.datetime):
        d = value
    elif isinstance(value, dt.date):
        d = value
    elif isinstance(value, str):
        try:
            d = dt.datetime.fromisoformat(value)
        except ValueError:
            try:
                d = dt.date.fromisoformat(value)
            except ValueError:
                return None
    else:
        return None
    if granularity == "year":
        return dt.datetime(d.year, 1, 1)
    if granularity == "quarter":
        quarter_month = ((d.month - 1) // 3) * 3 + 1
        return dt.datetime(d.year, quarter_month, 1)
    if granularity == "month":
        return dt.datetime(d.year, d.month, 1)
    if granularity == "week":
        # ISO week — bucket starts on Monday
        return dt.datetime(d.year, d.month, d.day) - dt.timedelta(days=d.weekday())
    return dt.datetime(d.year, d.month, d.day)


def _rebucket_rows(
    rows: list[dict],
    date_column: str,
    granularity: Granularity,
    agg: AggFunction,
) -> tuple[list[str], list[dict]]:
    """Group rows into time buckets and aggregate numeric columns client-side.

    Non-numeric columns are skipped (e.g. text categories) — SQL-level
    SUM() would fail on mixed-type view output. Rows with an unparseable
    date form no meaningful bucket and are dropped.
    """
    buckets: dict[dt.datetime, list[dict]] = {}
    value_cols: list[str] = []
    for row in rows:
        if date_column not in row:
            raise HTTPException(
                status_code=422,
                detail=f"时间列 '{date_column}' 不在视图输出列中",
            )
        key = _bucket_key(row[date_column], granularity)
        if key is None:
            continue
        buckets.setdefault(key, []).append(row)
        if not value_cols:
            value_cols = [c for c in row.keys() if c != date_column]

    result_rows: list[dict] = []
    for key in sorted(buckets):
        group = buckets[key]
        out: dict = {date_column: key.isoformat()}
        for col in value_cols:
            numbers: list[float] = []
            non_null = 0
            for row in group:
                val = row.get(col)
                if val is None:
                    continue
                non_null += 1
                try:
                    numbers.append(float(val))
                except (TypeError, ValueError):
                    continue
            if agg == "COUNT":
                out[col] = non_null
            elif numbers:
                if agg == "SUM":
                    out[col] = sum(numbers)
                elif agg == "AVG":
                    out[col] = sum(numbers) / len(numbers)
                elif agg == "MIN":
                    out[col] = min(numbers)
                else:  # MAX
                    out[col] = max(numbers)
            # columns without any numeric value are omitted from the bucket
        result_rows.append(out)

    kept_cols = [date_column]
    for col in value_cols:
        if any(col in r for r in result_rows):
            kept_cols.append(col)
    return kept_cols, result_rows


@router.get("/visualizations/{viz_id}/data", response_model=VisualizationDataResponse)
async def get_visualization_data(
    viz_id: uuid.UUID,
    start: str | None = Query(None, description="时间筛选起始（ISO 日期），仅当可视化配置了时间列时生效"),
    end: str | None = Query(None, description="时间筛选结束（ISO 日期），仅当可视化配置了时间列时生效"),
    granularity: Granularity | None = Query(None, description="时间粒度重分桶：year/quarter/month/week/day"),
    agg: AggFunction | None = Query(None, description="重分桶聚合函数：SUM/COUNT/AVG/MIN/MAX"),
    db: AsyncSession = Depends(get_db),
):
    """Execute the associated view's SQL and return full result set for charting.

    Optional time-profile params (``start``/``end``/``granularity``/``agg``)
    apply only when the visualization's ``config_json.date_column`` is set;
    otherwise they are ignored.
    """
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

    # Apply optional time-profile overrides (date filter / re-bucketing).
    # Only active when the visualization declares a date_column profile.
    date_column = viz.config_json.get("date_column")
    time_active = bool(date_column) and bool(start or end or granularity or agg)
    if time_active:
        sql, params = await _apply_time_profile(db, sql, params, date_column, start, end, granularity, agg)

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

    # Granularity re-bucketing runs as post-processing so mixed-type view
    # output (text columns etc.) does not break SQL aggregation.
    if time_active and granularity:
        columns, rows = _rebucket_rows(rows, date_column, granularity, agg or "SUM")

    return VisualizationDataResponse(
        columns=columns,
        rows=rows,
        chart_type=viz.chart_type,
        config_json=viz.config_json,
    )
