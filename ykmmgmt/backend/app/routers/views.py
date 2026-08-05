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


def _build_sql_from_config(config: ViewConfig) -> tuple[str, dict]:
    """Generate parameterized SQL from a ViewConfig.

    Validates table/column references against the model registry.
    """
    builder = ViewSQLBuilder(config, _get_model_registry())
    return builder.build()


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
    stmt = select(View).order_by(View.updated_at.desc())
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
    await db.flush()
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


# ── Preview Endpoint ────────────────────────────────────────────────────────


@router.post("/views/preview", response_model=PreviewResponse)
async def preview_view(body: PreviewRequest, db: AsyncSession = Depends(get_db)):
    """Generate SQL from config and execute with LIMIT 20.

    Does NOT store anything — purely transient preview.
    """
    config = body.config_json

    try:
        sql, params = _build_sql_from_config(config)
    except SQLBuildError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e

    # Add LIMIT and execute
    preview_sql = f"{sql}\nLIMIT 20"
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
