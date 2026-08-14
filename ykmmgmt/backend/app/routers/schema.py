"""Schema Manager endpoints — /api/schema.

Table inspection, column-type listing, table creation (manual + CSV
inference), comprehensive column editing, and table deletion — all backed
by auto-generated Alembic migrations and a runtime model registry.
"""

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import engine, get_db
from app.services import schema_manager as sm
from app.services import schema_validator
from app.services.parsers import parse_file

router = APIRouter(prefix="/api/schema", tags=["schema"])


# ── Pydantic request schemas ────────────────────────────────────────────────


class ColumnDefinition(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type: str
    length: int | None = Field(None, ge=1, le=4000)
    nullable: bool = True
    unique: bool = False
    primary_key: bool = False
    foreign_key: str | None = Field(None, max_length=200, description="外键引用，格式 '表名.列名'")
    label: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=500, description="列描述（可选）")
    default: str | None = Field(None, max_length=200, description="默认值（可选）")


class CreateTableRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str | None = Field(None, max_length=200)
    columns: list[ColumnDefinition] = Field(..., min_length=1)
    upsert_key: list[str] | None = Field(None, description="Upsert 键列名组合（可选，默认主键）")
    dedup_enabled: bool = Field(True, description="无键表是否启用完全重复去重")


class ModifyColumnRequest(BaseModel):
    """Comprehensive column edit — only the provided fields are changed."""

    name: str | None = Field(None, min_length=1, max_length=100, description="新列名（重命名）")
    type: str | None = None
    length: int | None = Field(None, ge=1, le=4000)
    nullable: bool | None = None
    unique: bool | None = None
    label: str | None = Field(None, max_length=200, description="中文标签")
    description: str | None = Field(None, max_length=500, description="列描述，传空串清除")
    default: str | None = Field(None, max_length=200, description="默认值，传空串清除")
    foreign_key: str | None = Field(None, max_length=200, description="外键 '表名.列名'，传空串移除")


class TableSettingsRequest(BaseModel):
    """Table-level settings edit — only the provided fields are changed."""

    name: str | None = Field(None, min_length=1, max_length=100, description="新英文表名")
    display_name: str | None = Field(None, max_length=200, description="新中文显示名")
    upsert_key: list[str] | None = Field(None, description="Upsert 键列名组合；传空列表清除（回退主键/无键）")
    dedup_enabled: bool | None = Field(None, description="无键表是否启用完全重复去重")


# ── Helpers ─────────────────────────────────────────────────────────────────


def _raise_error(err: sm.SchemaManagerError) -> HTTPException:
    return HTTPException(status_code=err.status_code, detail=err.message)


def _get_editable_model(name: str) -> Any:
    """Return the model for an editable (dynamic) table, or raise 403/404."""
    if name in sm.READ_ONLY_TABLES:
        raise HTTPException(
            status_code=403,
            detail=f"'{name}' 是预置业务表，仅可查看，不允许编辑或删除",
        )
    model = schema_validator.get_registered_model(name)
    if model is None or name not in sm.get_dynamic_table_names():
        raise HTTPException(status_code=404, detail=f"数据表 '{name}' 不存在或不可编辑")
    return model


def _column_def_dict(col: ColumnDefinition) -> dict[str, Any]:
    # A primary key is inherently NOT NULL and unique — normalize the flags
    # so conflicting client input can never weaken the PK constraint.
    pk = col.primary_key
    return {
        "name": col.name,
        "type": col.type,
        "length": col.length,
        "nullable": False if pk else col.nullable,
        "unique": False if pk else col.unique,
        "primary_key": pk,
        "foreign_key": (col.foreign_key or "").strip() or None,
        "label": col.label or col.name,
        "description": (col.description or "").strip() or None,
        "default": None if pk else (col.default or "").strip() or None,
    }


async def _save_column_meta(db: AsyncSession, table: str, columns: list[dict[str, Any]]) -> None:
    """Persist description/default metadata for columns that carry them."""
    for col in columns:
        if col.get("description") or col.get("default"):
            await sm.upsert_column_meta(db, table, col["name"], col.get("description"), col.get("default"))


async def _resync(db: AsyncSession) -> None:
    """Rebuild the in-memory dynamic models from the live database."""
    await sm.resync_dynamic_models(await db.connection())


# ── Inspection & type system ────────────────────────────────────────────────


@router.get("/tables")
async def list_schema_tables(db: AsyncSession = Depends(get_db)):
    """List every table with names, counts, and read-only flags."""
    return await sm.list_tables_info(db)


@router.get("/column-types")
async def list_column_types():
    """Return the supported column types that drive the frontend picker."""
    return sm.column_type_list()


@router.get("/fk-options")
async def get_fk_options():
    """Tables + FK-eligible columns (PK/unique) that drive the FK dropdowns."""
    return sm.fk_options()


@router.get("/tables/{name}")
async def get_schema_table(name: str, db: AsyncSession = Depends(get_db)):
    """Full column detail plus a small sample of rows."""
    try:
        return await sm.table_detail(db, name)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e


@router.get("/tables/{name}/dependencies")
async def get_table_dependencies(
    name: str,
    column: str | None = Query(None, description="仅检查对该列的引用"),
    db: AsyncSession = Depends(get_db),
):
    """Saved views/visualizations that reference the table (or one column)."""
    if schema_validator.get_registered_model(name) is None:
        raise HTTPException(status_code=404, detail=f"数据表 '{name}' 不存在")
    return await sm.find_dependencies(db, name, column)


# ── Table creation ──────────────────────────────────────────────────────────


@router.post("/tables", status_code=201)
async def create_table(body: CreateTableRequest, db: AsyncSession = Depends(get_db)):
    """Create a new table: validate, generate + run a migration, register it."""
    try:
        sm.validate_identifier(body.name, "表", sm.RESERVED_TABLE_NAMES)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e

    # Collision check: runtime registry + live database
    if schema_validator.get_registered_model(body.name) is not None:
        raise HTTPException(status_code=409, detail=f"数据表 '{body.name}' 已存在")
    conn = await db.connection()
    exists = await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).has_table(body.name))
    if exists:
        raise HTTPException(status_code=409, detail=f"数据表 '{body.name}' 已存在")

    columns = [_column_def_dict(c) for c in body.columns]
    try:
        sm.validate_column_definitions(columns)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e

    display_name = (body.display_name or "").strip() or body.name

    # ── Ingestion settings: upsert key + dedup toggle ───────────────
    col_names = [c["name"] for c in columns]
    pk_cols = [c["name"] for c in columns if c["primary_key"]]
    upsert_key = [c for c in (body.upsert_key or []) if c]
    if upsert_key:
        unknown = [c for c in upsert_key if c not in col_names]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Upsert 键列不存在：{'、'.join(unknown)}")
        if len(set(upsert_key)) != len(upsert_key):
            raise HTTPException(status_code=400, detail="Upsert 键列重复")
    effective_key = upsert_key or pk_cols
    has_unique_col = any(c["unique"] for c in columns if not c["primary_key"])
    if not body.dedup_enabled and (pk_cols or upsert_key or has_unique_col):
        raise HTTPException(
            status_code=400,
            detail="只有当表没有主键、唯一列和 Upsert 键时才允许关闭去重",
        )
    # Keyless table with dedup enabled gets the content_hash mechanism
    add_content_hash = bool(body.dedup_enabled) and not effective_key

    migration_path = sm.write_migration(
        f"create_table_{body.name}",
        sm.create_table_ops(
            body.name,
            columns,
            display_name,
            upsert_key=effective_key,
            add_content_hash=add_content_hash,
        ),
        sm.drop_table_ops(body.name),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    # Store settings BEFORE the resync so the rebuilt model picks them up
    await sm.save_table_meta(db, body.name, effective_key, body.dedup_enabled)
    await _resync(db)
    await _save_column_meta(db, body.name, columns)

    try:
        return await sm.table_detail(db, body.name)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e


@router.post("/infer-from-csv")
async def infer_from_csv(file: UploadFile = File(...)):
    """Infer a proposed schema from an uploaded CSV. Does NOT create a table."""
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".csv", ".xlsx"):
        raise HTTPException(
            status_code=415,
            detail=f"不支持的文件格式 '{suffix}'。仅支持 .csv 和 .xlsx",
        )

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        try:
            df, raw_headers = parse_file(tmp_path)
        except ValueError as e:
            raise HTTPException(status_code=415, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"文件解析失败: {e}") from e

        if not raw_headers:
            raise HTTPException(status_code=422, detail="文件没有表头，无法推断结构")

        proposed = sm.infer_schema(df, raw_headers)
    finally:
        tmp_path.unlink(missing_ok=True)

    # Fill the full editable field set so the wizard renders every control;
    # the Chinese label comes from the file header (auto-filled).
    for col in proposed:
        col.setdefault("primary_key", False)
        col.setdefault("foreign_key", None)
        col.setdefault("description", None)
        col.setdefault("default", None)

    stem = Path(file.filename or "").stem.strip().lower()
    suggested = stem if stem and sm.IDENTIFIER_RE.match(stem) else "new_table"

    return {
        "columns": proposed,
        "row_count": len(df),
        "suggested_table_name": suggested,
    }


# ── Column add / drop / modify ──────────────────────────────────────────────


@router.post("/tables/{name}/columns", status_code=201)
async def add_column(
    name: str,
    body: ColumnDefinition,
    db: AsyncSession = Depends(get_db),
):
    """Add a column to a dynamic table via a generated migration."""
    _get_editable_model(name)
    if body.primary_key:
        raise HTTPException(status_code=400, detail="不支持向已有表添加主键列，主键只能在建表时指定")
    col = _column_def_dict(body)
    try:
        sm.validate_column_definitions([col])
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e

    model = schema_validator.get_registered_model(name)
    if body.name in model.__table__.columns:
        raise HTTPException(status_code=409, detail=f"列 '{body.name}' 已存在")

    migration_path = sm.write_migration(
        f"add_column_{name}_{body.name}",
        sm.add_column_ops(name, col),
        sm.drop_column_ops(name, col),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    await _resync(db)
    await _save_column_meta(db, name, [col])

    try:
        return await sm.table_detail(db, name)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e


@router.delete("/tables/{name}/columns/{column_name}")
async def drop_column(
    name: str,
    column_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Drop a column from a dynamic table via a generated migration."""
    _get_editable_model(name)
    model = schema_validator.get_registered_model(name)
    if column_name not in model.__table__.columns:
        raise HTTPException(status_code=404, detail=f"列 '{column_name}' 不存在")
    if column_name in ("id", "content_hash", "imported_at"):
        raise HTTPException(status_code=403, detail=f"系统列 '{column_name}' 不允许删除")

    col = next(c for c in sm.extract_column_definitions(model) if c["name"] == column_name)
    if col.get("primary_key"):
        raise HTTPException(status_code=403, detail=f"主键列 '{column_name}' 不允许删除")
    dependencies = await sm.find_dependencies(db, name, column_name)
    if dependencies["tables"]:
        refs = "、".join(f"{d['table']}.{d['column']}" for d in dependencies["tables"])
        raise HTTPException(
            status_code=409,
            detail=f"列 '{column_name}' 被以下外键引用，请先删除依赖列/表：{refs}",
        )

    migration_path = sm.write_migration(
        f"drop_column_{name}_{column_name}",
        sm.drop_column_ops(name, col),
        sm.add_column_ops(name, col),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    await _resync(db)
    await sm.delete_column_meta(db, name, column_name)
    return {"deleted_column": column_name, "dependencies": dependencies}


@router.put("/tables/{name}/columns/{column_name}")
async def modify_column(
    name: str,
    column_name: str,
    body: ModifyColumnRequest,
    db: AsyncSession = Depends(get_db),
):
    """Comprehensive column edit: rename, type, nullability, unique, label,
    description, default value, and foreign key — in one generated migration.

    Only fields present in the request payload are changed; empty strings
    clear label-dependent metadata (description/default/foreign key).
    """
    _get_editable_model(name)
    model = schema_validator.get_registered_model(name)
    if column_name not in model.__table__.columns:
        raise HTTPException(status_code=404, detail=f"列 '{column_name}' 不存在")
    if column_name in ("id", "content_hash", "imported_at"):
        raise HTTPException(status_code=403, detail=f"系统列 '{column_name}' 不允许修改")

    sent = body.model_fields_set
    old = next(c for c in sm.extract_column_definitions(model) if c["name"] == column_name)
    is_pk = bool(old.get("primary_key"))
    old_fk = (old.get("foreign_key") or "").strip()
    old_unique = bool(old.get("unique"))

    # ── Resolve the requested final state ──────────────────────────────
    new_name = column_name
    if "name" in sent and body.name and body.name.strip():
        new_name = body.name.strip()
        if new_name != column_name:
            try:
                sm.validate_identifier(new_name, "列", sm.RESERVED_COLUMN_NAMES)
            except sm.SchemaManagerError as e:
                raise _raise_error(e) from e
            if new_name in model.__table__.columns:
                raise HTTPException(status_code=409, detail=f"列 '{new_name}' 已存在")

    new_type = body.type if "type" in sent and body.type else old["type"]
    if new_type not in sm.COLUMN_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的列类型 '{new_type}'")
    if new_type != old["type"] and is_pk:
        raise HTTPException(status_code=400, detail="主键列的类型不允许修改")
    new_length = body.length if "length" in sent else old.get("length")

    if "nullable" in sent and body.nullable and is_pk:
        raise HTTPException(status_code=400, detail="主键列不允许为空，无法修改为可空")
    if "unique" in sent and body.unique and is_pk:
        raise HTTPException(status_code=400, detail="主键列已隐式唯一，无需设置唯一约束")

    # Final FK state: unchanged / set / removed
    fk_changed = False
    new_fk = old_fk
    if "foreign_key" in sent:
        candidate = (body.foreign_key or "").strip()
        if candidate != old_fk:
            fk_changed = True
            new_fk = candidate

    label_changed = "label" in sent and body.label is not None and body.label.strip() != old["label"]
    new_label = body.label.strip() if label_changed else old["label"]

    type_changed = new_type != old["type"] or (new_length or None) != (old.get("length") or None)
    nullable_changed = "nullable" in sent and body.nullable is not None and bool(body.nullable) != bool(old["nullable"])
    unique_changed = "unique" in sent and body.unique is not None and bool(body.unique) != old_unique
    final_unique = bool(body.unique) if unique_changed else old_unique
    default_changed = "default" in sent

    ddl_changed = any(
        [
            new_name != column_name,
            type_changed,
            nullable_changed,
            unique_changed,
            fk_changed,
            label_changed,
            default_changed,
        ]
    )
    if not ddl_changed:
        # Metadata-only edit (e.g. description) — no migration needed
        if "description" in sent:
            await sm.upsert_column_meta(db, name, column_name, description=(body.description or "").strip())
        return {"modified_column": column_name, "warning": None, "changed": True}

    # ── Validation ─────────────────────────────────────────────────────
    if default_changed:
        probe = {"name": new_name, "type": new_type, "default": (body.default or "").strip() or None}
        try:
            sm.validate_default_value(probe)
        except sm.SchemaManagerError as e:
            raise _raise_error(e) from e
    if fk_changed and new_fk:
        try:
            sm.validate_foreign_key(new_name, new_fk)
        except sm.SchemaManagerError as e:
            raise _raise_error(e) from e

    warning: str | None = None
    if type_changed and sm.is_lossy_cast(old["type"], new_type):
        warning = f"类型从 {old['type']} 改为 {new_type} 可能丢失或无法转换部分数据，请确认现有数据兼容后再继续"

    # ── Build migration ops (order: drop deps → change → rename → re-add) ─
    upgrade: list[str] = []
    downgrade: list[str] = []

    # FK must be dropped before type change / rename / removal
    if old_fk and (fk_changed or type_changed or new_name != column_name):
        upgrade.append(sm.drop_fk_ops(name, column_name))
        downgrade.append(sm.create_fk_ops(name, column_name, old_fk))

    # Unique constraint: drop on removal or rename (re-created under the
    # new column name afterwards)
    if old_unique and (not final_unique or new_name != column_name):
        upgrade.append(sm.drop_unique_ops(name, column_name))
        downgrade.append(sm.create_unique_ops(name, column_name))

    if type_changed:
        upgrade.append(
            sm.alter_column_ops(
                name,
                column_name,
                {"type": old["type"], "length": old.get("length"), "nullable": old["nullable"]},
                {"type": new_type, "length": new_length, "nullable": old["nullable"]},
            )
        )
        downgrade.append(
            sm.alter_column_ops(
                name,
                column_name,
                {"type": new_type, "length": new_length, "nullable": old["nullable"]},
                {"type": old["type"], "length": old.get("length"), "nullable": old["nullable"]},
            )
        )

    if nullable_changed:
        upgrade.append(sm.nullable_ops(name, column_name, bool(body.nullable)))
        downgrade.append(sm.nullable_ops(name, column_name, bool(old["nullable"])))

    if default_changed:
        probe = {"name": column_name, "type": new_type, "default": (body.default or "").strip() or None}
        upgrade.append(sm.set_default_ops(name, probe))
        downgrade.append(
            sm.set_default_ops(name, {"name": column_name, "type": old["type"], "default": old.get("default")})
        )

    if new_name != column_name:
        upgrade.append(sm.rename_column_ops(name, column_name, new_name))
        downgrade.append(sm.rename_column_ops(name, new_name, column_name))

    # Create the unique constraint on the (possibly renamed) column
    if final_unique and (not old_unique or new_name != column_name):
        upgrade.append(sm.create_unique_ops(name, new_name))
        downgrade.append(sm.drop_unique_ops(name, new_name))

    # Recreate / create FK on the (possibly renamed) column
    if new_fk and (fk_changed or type_changed or new_name != column_name):
        upgrade.append(sm.create_fk_ops(name, new_name, new_fk))
        if not fk_changed:
            downgrade.append(sm.drop_fk_ops(name, new_name))

    if label_changed:
        upgrade.append(sm.column_comment_ops(name, new_name, new_label))
        downgrade.append(sm.column_comment_ops(name, new_name, old["label"]))

    migration_path = sm.write_migration(
        f"alter_column_{name}_{column_name}",
        "\n".join(upgrade),
        "\n".join(reversed(downgrade)),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    # ── Metadata + registry refresh ────────────────────────────────────
    if new_name != column_name:
        await sm.rename_column_meta(db, name, column_name, new_name)
    if "description" in sent:
        await sm.upsert_column_meta(db, name, new_name, description=(body.description or "").strip())
    if default_changed:
        await sm.upsert_column_meta(db, name, new_name, default_value=(body.default or "").strip())

    await _resync(db)
    return {"modified_column": new_name, "warning": warning, "changed": True}


# ── Table settings (rename + display name + upsert key + dedup) ─────────


@router.put("/tables/{name}")
async def update_table_settings(
    name: str,
    body: TableSettingsRequest,
    db: AsyncSession = Depends(get_db),
):
    """Edit table-level settings: English name, Chinese display name,
    upsert key (single or composite), and the keyless-dedup toggle.

    The English name change is a physical ALTER TABLE ... RENAME and is
    blocked when saved views/visualizations embed the old name in their SQL
    (FK children are safe — PostgreSQL follows them by object id). The
    display name is stored as the table comment so it survives restarts.
    """
    _get_editable_model(name)
    sent = body.model_fields_set
    model = schema_validator.get_registered_model(name)

    new_name = name
    if "name" in sent and body.name and body.name.strip():
        new_name = body.name.strip()

    old_display = schema_validator.get_chinese_table_name(name)
    new_display = old_display
    if "display_name" in sent and body.display_name is not None and body.display_name.strip():
        new_display = body.display_name.strip()

    rename = new_name != name
    display_changed = new_display != old_display

    # ── Ingestion settings resolution ──────────────────────────────
    mapper = sa_inspect(model)
    pk_cols = [c.name for c in mapper.columns if c.primary_key and c.name not in ("id",)]
    col_names = [c.name for c in mapper.columns if c.name not in ("id", "imported_at", "content_hash")]
    old_settings = sm.get_table_settings(name) or {}
    old_key = list(old_settings.get("upsert_key") or [])
    old_dedup = bool(old_settings.get("dedup_enabled", True))
    old_had_hash = "content_hash" in model.__table__.columns
    old_had_uq = bool(old_key) and old_key != pk_cols

    new_key = old_key
    if "upsert_key" in sent:
        candidate = [c for c in (body.upsert_key or []) if c]
        unknown = [c for c in candidate if c not in col_names]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Upsert 键列不存在：{'、'.join(unknown)}")
        if len(set(candidate)) != len(candidate):
            raise HTTPException(status_code=400, detail="Upsert 键列重复")
        new_key = candidate or pk_cols
    new_dedup = body.dedup_enabled if "dedup_enabled" in sent and body.dedup_enabled is not None else old_dedup

    unique_cols = sm._unique_column_names(model)
    if not new_dedup and (pk_cols or new_key or unique_cols):
        raise HTTPException(
            status_code=400,
            detail="只有当表没有主键、唯一列和 Upsert 键时才允许关闭去重",
        )

    new_had_uq = bool(new_key) and new_key != pk_cols
    new_has_hash = bool(new_dedup) and not new_key
    key_changed = new_key != old_key
    dedup_changed = new_has_hash != old_had_hash
    settings_changed = key_changed or (new_dedup != old_dedup)

    if not rename and not display_changed and not settings_changed:
        return await sm.table_detail(db, name)

    if rename:
        try:
            sm.validate_identifier(new_name, "表", sm.RESERVED_TABLE_NAMES)
        except sm.SchemaManagerError as e:
            raise _raise_error(e) from e
        if schema_validator.get_registered_model(new_name) is not None:
            raise HTTPException(status_code=409, detail=f"数据表 '{new_name}' 已存在")
        conn = await db.connection()
        exists = await conn.run_sync(lambda sync_conn: sa_inspect(sync_conn).has_table(new_name))
        if exists:
            raise HTTPException(status_code=409, detail=f"数据表 '{new_name}' 已存在")

        dependencies = await sm.find_dependencies(db, name)
        if dependencies["views"] or dependencies["visualizations"]:
            refs = "、".join(item["name"] for item in dependencies["views"] + dependencies["visualizations"])
            raise HTTPException(
                status_code=409,
                detail={
                    "message": f"数据表 '{name}' 被以下视图/可视化引用，重命名会破坏它们：{refs}",
                    "dependencies": dependencies,
                },
            )

    # New upsert key must not collide with existing data. Runs on its own
    # short-lived connection: a SELECT on the request session would keep an
    # ACCESS SHARE lock on the table until commit, deadlocking the DDL
    # subprocess (which needs ACCESS EXCLUSIVE) in the migration below.
    if key_changed and new_had_uq:
        from sqlalchemy import func as sa_func

        key_col_objs = [model.__table__.columns[c] for c in new_key]
        dup_stmt = select(*key_col_objs).group_by(*key_col_objs).having(sa_func.count() > 1).limit(1)
        async with engine.connect() as check_conn:
            dup_row = (await check_conn.execute(dup_stmt)).first()
        if dup_row is not None:
            vals = "、".join(str(v) for v in dup_row)
            raise HTTPException(
                status_code=409,
                detail=f"现有数据在新 Upsert 键（{'、'.join(new_key)}）上存在重复：{vals}，请先清理数据",
            )

    upgrade: list[str] = []
    downgrade: list[str] = []
    # Constraint changes happen under the current table name (pre-rename)
    if key_changed and old_had_uq:
        upgrade.append(sm.drop_upsert_key_ops(name))
        downgrade.append(sm.create_upsert_key_ops(name, old_key))
    if dedup_changed and old_had_hash:
        upgrade.append(sm.drop_content_hash_ops(name))
        downgrade.append(sm.add_content_hash_ops(name))
    if key_changed and new_had_uq:
        upgrade.append(sm.create_upsert_key_ops(name, new_key))
        downgrade.append(sm.drop_upsert_key_ops(name))
    if dedup_changed and new_has_hash:
        upgrade.append(sm.add_content_hash_ops(name))
        downgrade.append(sm.drop_content_hash_ops(name))
    if rename:
        upgrade.append(sm.rename_table_ops(name, new_name))
        downgrade.append(sm.rename_table_ops(new_name, name))
    if display_changed:
        # The comment targets the table under its post-rename name
        upgrade.append(sm.table_comment_ops(new_name, new_display))
        downgrade.append(sm.table_comment_ops(new_name, old_display))

    migration_path = sm.write_migration(
        f"settings_table_{name}",
        "\n".join(upgrade),
        "\n".join(reversed(downgrade)),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    if rename:
        await sm.rename_table_meta(db, name, new_name)
    if settings_changed:
        await sm.save_table_meta(db, new_name, new_key, new_dedup)
    await _resync(db)

    try:
        return await sm.table_detail(db, new_name)
    except sm.SchemaManagerError as e:
        raise _raise_error(e) from e


# ── Table deletion ──────────────────────────────────────────────────────────


@router.delete("/tables/{name}")
async def delete_table(
    name: str,
    confirm: bool = Query(False, description="已确认依赖影响，强制删除"),
    db: AsyncSession = Depends(get_db),
):
    """Drop a dynamic table. Returns 409 with dependencies unless confirmed.

    FK references from other tables always block deletion — drop the
    dependent tables first. Views/visualizations only require confirmation.
    """
    _get_editable_model(name)
    model = schema_validator.get_registered_model(name)
    dependencies = await sm.find_dependencies(db, name)

    if dependencies["tables"]:
        refs = "、".join(d["table"] for d in dependencies["tables"])
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"数据表 '{name}' 被以下数据表通过外键引用，请先删除依赖表：{refs}",
                "dependencies": dependencies,
            },
        )

    has_deps = bool(dependencies["views"] or dependencies["visualizations"])
    if has_deps and not confirm:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"数据表 '{name}' 被以下视图/可视化引用，请确认后重试",
                "dependencies": dependencies,
            },
        )

    definitions = sm.extract_column_definitions(model)
    display_name = schema_validator.get_chinese_table_name(name)
    settings = sm.get_table_settings(name) or {}
    has_hash = "content_hash" in model.__table__.columns
    migration_path = sm.write_migration(
        f"drop_table_{name}",
        sm.drop_table_ops(name),
        sm.create_table_ops(
            name,
            definitions,
            display_name,
            upsert_key=settings.get("upsert_key") or None,
            add_content_hash=has_hash,
        ),
    )
    try:
        await sm.run_alembic_upgrade()
    except sm.SchemaManagerError as e:
        migration_path.unlink(missing_ok=True)
        raise _raise_error(e) from e

    sm.unregister_dynamic_table(name)
    await sm.delete_column_meta(db, name)
    await sm.delete_table_meta(db, name)
    return {"deleted": name, "dependencies": dependencies}
