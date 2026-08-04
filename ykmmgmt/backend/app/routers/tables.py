"""Data Browser endpoints — GET /api/tables, schema, and paginated data."""

import datetime as dt
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import Date, cast, func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.schema_validator import (
    TABLE_DISPLAY_NAMES,
    get_registered_model,
)

router = APIRouter(prefix="/api", tags=["tables"])

# ── Pydantic response schemas ──────────────────────────────────────────────


class TableInfo(BaseModel):
    name: str
    chinese_name: str


class ColumnInfo(BaseModel):
    name: str
    type: str
    label: str


class TableDataResponse(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    page: int
    size: int


# ── Internal helpers ────────────────────────────────────────────────────────

_HIDDEN_COLUMNS: set[str] = {"id", "imported_at", "content_hash"}


def _python_type_name(col: Any) -> str:
    """Return a human-friendly Python type name for a SQLAlchemy column."""
    try:
        return col.type.python_type.__name__
    except (AttributeError, NotImplementedError):
        return str(col.type)


def _is_datetime_column(col: Any) -> bool:
    """Check whether a column stores datetime values."""
    try:
        return issubclass(col.type.python_type, dt.datetime)
    except (AttributeError, TypeError):
        return False


def _serialize(value: Any) -> Any:
    """Convert non-JSON-serializable values (e.g. datetime) to strings."""
    if isinstance(value, dt.datetime):
        return value.isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return value


# ── Endpoints ───────────────────────────────────────────────────────────────


@router.get("/tables", response_model=list[TableInfo])
async def list_tables():
    """List business data tables with Chinese display names.

    Excludes internal tables (datasources, import_jobs, alembic_version).
    """
    return [
        TableInfo(name=name, chinese_name=chinese_name)
        for name, chinese_name in TABLE_DISPLAY_NAMES.items()
    ]


@router.get("/tables/{name}/schema", response_model=list[ColumnInfo])
async def get_table_schema(name: str):
    """Return column metadata for a given table.

    Each column includes the English name, Python type, and Chinese label
    (from the model's column comment). Internal-only columns (id,
    imported_at, content_hash) are excluded.
    """
    model = get_registered_model(name)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail=f"数据表 '{name}' 不存在",
        )

    mapper = inspect(model)
    columns: list[ColumnInfo] = []

    for col in mapper.columns:
        if col.name in _HIDDEN_COLUMNS:
            continue
        label = getattr(col, "comment", None) or col.name
        columns.append(
            ColumnInfo(
                name=col.name,
                type=_python_type_name(col),
                label=label,
            )
        )

    return columns


@router.get("/tables/{name}/data", response_model=TableDataResponse)
async def get_table_data(
    name: str,
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=200, description="每页数量"),
    datetime_col: str | None = Query(None, description="时间筛选项：列名"),
    start: str | None = Query(None, description="起始日期 (YYYY-MM-DD)"),
    end: str | None = Query(None, description="结束日期 (YYYY-MM-DD)"),
    filter_col: list[str] = Query(default_factory=list, description="列值筛选：列名（可重复）"),
    filter_value: list[str] = Query(default_factory=list, description="列值筛选：值（与 filter_col 位置对应）"),
    filter_mode: list[str] = Query(
        default_factory=list,
        description="列值筛选：模式 contains|exact（与 filter_col 位置对应）",
    ),
    sort_col: str | None = Query(None, description="排序列名"),
    sort_dir: str | None = Query(None, description="排序方向 asc|desc"),
    db: AsyncSession = Depends(get_db),
):
    """Return paginated rows from a business table.

    Supports optional date range filtering via query parameters
    ``datetime_col``, ``start``, and ``end``.  At least one of ``start``
    or ``end`` must be provided together with ``datetime_col`` to
    activate the filter.  Comparisons use the date portion only
    (time of day is ignored).  Both ends are inclusive.

    Column value filtering uses positional repeated params:
    ``filter_col[0]`` with ``filter_value[0]`` and ``filter_mode[0]``.
    Mode ``contains`` uses SQL LIKE %value%; ``exact`` uses =.

    Sorting uses ``sort_col`` + ``sort_dir`` (asc/desc, default asc).
    """
    model = get_registered_model(name)
    if model is None:
        raise HTTPException(
            status_code=404,
            detail=f"数据表 '{name}' 不存在",
        )

    mapper = inspect(model)
    visible_columns = [c.name for c in mapper.columns if c.name not in _HIDDEN_COLUMNS]

    # Base queries
    count_stmt = select(func.count()).select_from(model.__table__)
    data_stmt = select(model)

    # Apply date filter — supports start-only, end-only, or both
    if datetime_col and (start or end):
        col = model.__table__.columns.get(datetime_col)
        if col is not None and _is_datetime_column(col):
            date_col = cast(col, Date)
            if start:
                try:
                    start_date = dt.date.fromisoformat(start)
                except ValueError as err:
                    raise HTTPException(
                        status_code=422,
                        detail=f"起始日期格式无效: '{start}'。请使用 YYYY-MM-DD 格式。",
                    ) from err
                count_stmt = count_stmt.where(date_col >= start_date)
                data_stmt = data_stmt.where(date_col >= start_date)
            if end:
                try:
                    end_date = dt.date.fromisoformat(end)
                except ValueError as err:
                    raise HTTPException(
                        status_code=422,
                        detail=f"结束日期格式无效: '{end}'。请使用 YYYY-MM-DD 格式。",
                    ) from err
                count_stmt = count_stmt.where(date_col <= end_date)
                data_stmt = data_stmt.where(date_col <= end_date)

    # Apply column value filters — positional repeated params, AND combined
    if filter_col:
        for i, col_name in enumerate(filter_col):
            if col_name not in visible_columns:
                continue
            if i >= len(filter_value):
                continue
            value = filter_value[i].strip()
            if not value:
                continue
            mode = filter_mode[i] if i < len(filter_mode) else "contains"
            col = model.__table__.columns.get(col_name)
            if col is None:
                continue
            if mode == "exact":
                count_stmt = count_stmt.where(col == value)
                data_stmt = data_stmt.where(col == value)
            else:  # contains (default)
                count_stmt = count_stmt.where(col.like(f"%{value}%"))
                data_stmt = data_stmt.where(col.like(f"%{value}%"))

    # Apply sort
    if sort_col and sort_col in visible_columns:
        col = model.__table__.columns.get(sort_col)
        if col is not None:
            if sort_dir == "desc":
                data_stmt = data_stmt.order_by(col.desc())
            else:
                data_stmt = data_stmt.order_by(col.asc())

    # Total count
    total_result = await db.execute(count_stmt)
    total: int = total_result.scalar() or 0

    # Paginate
    offset = (page - 1) * size
    data_stmt = data_stmt.offset(offset).limit(size)
    result = await db.execute(data_stmt)
    model_rows = result.scalars().all()

    # Serialize rows, hiding internal columns
    rows: list[dict[str, Any]] = []
    for row in model_rows:
        row_dict: dict[str, Any] = {}
        for col_name in visible_columns:
            row_dict[col_name] = _serialize(getattr(row, col_name, None))
        rows.append(row_dict)

    return TableDataResponse(rows=rows, total=total, page=page, size=size)
