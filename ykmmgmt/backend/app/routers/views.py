"""View CRUD endpoints — POST/GET/PUT /api/views, POST /api/views/preview."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.view import View
from app.schemas.view import (
    PreviewRequest,
    PreviewResponse,
    ViewConfig,
    ViewCreate,
    ViewDataResponse,
    ViewListResponse,
    ViewResponse,
    ViewUpdate,
)
from app.services.schema_validator import get_registered_model, get_registered_tables
from app.services.view_sql_builder import SQLBuildError, ViewSQLBuilder

router = APIRouter(prefix="/api", tags=["views"])


def _get_model_registry() -> dict:
    """Build a {table_name: model_class} dict from registered tables."""
    registry: dict = {}
    for name in get_registered_tables():
        model = get_registered_model(name)
        if model is not None:
            registry[name] = model
    return registry


def _build_sql_from_config(config: ViewConfig, *, apply_limit: bool = True) -> tuple[str, dict]:
    """Generate parameterized SQL from a ViewConfig.

    Validates table/column references against the model registry.
    """
    builder = ViewSQLBuilder(config, _get_model_registry())
    return builder.build(apply_limit=apply_limit)


def _view_to_response(view: View) -> ViewResponse:
    """Convert an ORM View instance to a ViewResponse Pydantic model."""
    return ViewResponse(
        id=view.id,
        name=view.name,
        description=view.description,
        config_json=ViewConfig.model_validate(view.config_json),
        generated_sql=view.generated_sql,
        created_at=view.created_at,
        updated_at=view.updated_at,
    )


# ── CRUD Endpoints ──────────────────────────────────────────────────────────


@router.get("/views", response_model=list[ViewListResponse])
async def list_views(db: AsyncSession = Depends(get_db)):
    """List all saved views (summary only — no SQL or config)."""
    stmt = select(View).order_by(View.created_at.desc())
    result = await db.execute(stmt)
    views = result.scalars().all()
    return [ViewListResponse.model_validate(v) for v in views]


@router.get("/views/{view_id}", response_model=ViewResponse)
async def get_view(view_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single view by ID, including config and generated SQL."""
    stmt = select(View).where(View.id == view_id)
    result = await db.execute(stmt)
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=404, detail=f"视图 '{view_id}' 不存在")
    return _view_to_response(view)


@router.post("/views", response_model=ViewResponse, status_code=201)
async def create_view(body: ViewCreate, db: AsyncSession = Depends(get_db)):
    """Create a new view.

    Validates the config against the actual table schema, generates
    parameterized SQL, and stores both config and SQL.
    """
    try:
        sql, params = _build_sql_from_config(body.config_json)
    except SQLBuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Validate generated SQL with EXPLAIN
    try:
        await db.execute(text(f"EXPLAIN {sql}"), params)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"SQL 验证失败: {e}",
        ) from e

    view = View(
        name=body.name,
        description=body.description,
        config_json=body.config_json.model_dump(),
        generated_sql=sql,
    )
    db.add(view)
    try:
        await db.flush()
    except Exception as e:
        if "uq_views_name" in str(e) or "unique" in str(e).lower():
            raise HTTPException(
                status_code=409,
                detail=f"视图名称 '{body.name}' 已存在",
            ) from e
        raise
    await db.refresh(view)
    return _view_to_response(view)


@router.put("/views/{view_id}", response_model=ViewResponse)
async def update_view(
    view_id: uuid.UUID,
    body: ViewUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update an existing view.

    If config_json is provided, SQL is regenerated and validated.
    If only name/description changed, SQL is left unchanged.
    """
    stmt = select(View).where(View.id == view_id)
    result = await db.execute(stmt)
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=404, detail=f"视图 '{view_id}' 不存在")

    if body.name is not None:
        view.name = body.name
    if body.description is not None:
        view.description = body.description

    if body.config_json is not None:
        try:
            sql, params = _build_sql_from_config(body.config_json)
        except SQLBuildError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e

        # Validate with EXPLAIN
        try:
            await db.execute(text(f"EXPLAIN {sql}"), params)
        except Exception as e:
            raise HTTPException(
                status_code=422,
                detail=f"SQL 验证失败: {e}",
            ) from e

        view.config_json = body.config_json.model_dump()
        view.generated_sql = sql

    await db.flush()
    await db.refresh(view)
    return _view_to_response(view)


@router.delete("/views/{view_id}", status_code=204)
async def delete_view(view_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Permanently delete a view."""
    stmt = select(View).where(View.id == view_id)
    result = await db.execute(stmt)
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=404, detail=f"视图 '{view_id}' 不存在")
    await db.delete(view)
    await db.flush()


@router.get("/views/{view_id}/data", response_model=ViewDataResponse)
async def get_view_data(
    view_id: uuid.UUID,
    page: int = 1,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Execute the view's stored SQL and return paginated results.

    Pass ``size=0`` to return **all** rows (no pagination).
    """
    stmt = select(View).where(View.id == view_id)
    result = await db.execute(stmt)
    view = result.scalar_one_or_none()
    if view is None:
        raise HTTPException(status_code=404, detail=f"视图 '{view_id}' 不存在")

    if not view.generated_sql:
        raise HTTPException(status_code=400, detail="该视图没有存储的 SQL")

    # Regenerate SQL + params from stored config so that parameterized
    # filters (date ranges, operator values) have matching bind values.
    config = ViewConfig.model_validate(view.config_json)
    try:
        sql, params = _build_sql_from_config(config, apply_limit=True)
    except SQLBuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    fetch_all = size == 0
    config_limit = config.limit

    if not fetch_all:
        # Clamp size to max 100, and respect user's config limit as a cap
        size = max(1, min(size, 100))
        page = max(1, page)
        if config_limit and config_limit > 0:
            size = min(size, config_limit)

    # ── Count total rows (uncapped) ───────────────────────────────────
    count_sql = f"SELECT COUNT(*) AS cnt FROM ({sql}) AS _sub"
    try:
        cnt_result = await db.execute(text(count_sql), params)
        actual_total = cnt_result.scalar_one()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"查询执行失败: {e}",
        ) from e

    # Apply config limit as a hard cap on both total count and returned rows.
    # Wrap the base SQL in a subquery with LIMIT so that pagination
    # (OFFSET/LIMIT applied below) operates within the user's row budget.
    if config_limit and config_limit > 0:
        total = min(actual_total, config_limit)
        sql = f"SELECT * FROM ({sql}) AS _capped LIMIT {config_limit}"
    else:
        total = actual_total

    # ── Execute query (paginated or full) ──────────────────────────────
    if fetch_all:
        exec_sql = sql
    else:
        offset = (page - 1) * size
        exec_sql = f"SELECT * FROM ({sql}) AS _paged LIMIT {size} OFFSET {offset}"

    try:
        data_result = await db.execute(text(exec_sql), params)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"查询执行失败: {e}",
        ) from e

    columns = list(data_result.keys())

    # Serialize rows
    import datetime as dt

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

    return ViewDataResponse(
        rows=rows,
        total=total,
        page=1 if fetch_all else page,
        size=total if fetch_all else size,
        columns=columns,
    )


# ── Preview Endpoint ────────────────────────────────────────────────────────


@router.post("/views/preview", response_model=PreviewResponse)
async def preview_view(body: PreviewRequest, db: AsyncSession = Depends(get_db)):
    """Generate SQL from config and execute with LIMIT 20.

    Does NOT store anything — purely transient preview.
    """
    config = body.config_json

    try:
        sql, params = _build_sql_from_config(config, apply_limit=True)
    except SQLBuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Apply preview LIMIT: use user's limit (capped at 20) or default 20
    user_limit = config.limit
    if user_limit and user_limit > 0:
        preview_limit = min(user_limit, 20)
    else:
        preview_limit = 20
    preview_sql = f"{sql}\nLIMIT {preview_limit}"
    try:
        result = await db.execute(text(preview_sql), params)
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"查询执行失败: {e}",
        ) from e

    # Get column names from the result
    columns = list(result.keys())

    # Serialize rows
    import datetime as dt

    rows: list[dict] = []
    for row in result.mappings().all():
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

    return PreviewResponse(sql=sql, rows=rows, columns=columns)
