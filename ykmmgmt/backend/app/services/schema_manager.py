"""Database schema management service.

Inspects live tables, defines the column-type system, builds dynamic
SQLAlchemy models at runtime, generates + applies Alembic migrations,
and scans saved views/visualizations for table/column dependencies.
"""

import asyncio
import datetime as dt
import json
import os
import re
import subprocess
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import pandas as pd
from alembic.config import Config as AlembicConfig
from alembic.script import ScriptDirectory
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
    select,
)
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import Base, engine
from app.models.column_meta import ColumnMeta
from app.models.table_meta import TableMeta
from app.models.view import View
from app.models.visualization import Visualization
from app.services import schema_validator

BACKEND_DIR = Path(__file__).resolve().parents[2]

# Runtime-generated migrations live OUTSIDE the backend directory on
# purpose: `uvicorn --reload` watches the backend tree, and writing a
# migration into alembic/versions mid-request would trigger a reload that
# kills the in-flight request (client sees a 500 before the table exists).
RUNTIME_MIGRATIONS_DIR = BACKEND_DIR.parent / "runtime_migrations"
STATIC_MIGRATIONS_DIR = BACKEND_DIR / "alembic" / "versions"
# Ensure it exists before any alembic command scans version_locations
RUNTIME_MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)

# The three pre-existing business tables are inspection-only
READ_ONLY_TABLES: frozenset[str] = frozenset({"refund_orders", "service_refund_work_orders", "wallet_withdrawals"})

IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]*$")
INT_RE = re.compile(r"^-?\d+$")

RESERVED_TABLE_NAMES: frozenset[str] = (
    frozenset(
        {
            "alembic_version",
            "datasources",
            "import_jobs",
            "views",
            "visualizations",
            "dashboards",
        }
    )
    | READ_ONLY_TABLES
)

RESERVED_COLUMN_NAMES: frozenset[str] = frozenset({"id", "content_hash", "imported_at", "created_at"})

SQL_KEYWORDS: frozenset[str] = frozenset(
    {
        "user",
        "order",
        "group",
        "table",
        "select",
        "where",
        "from",
        "index",
        "primary",
        "column",
        "check",
        "default",
        "grant",
        "limit",
        "offset",
    }
)

# Columns hidden from data previews (internal bookkeeping)
_HIDDEN_COLUMNS: set[str] = {"id", "imported_at", "content_hash"}


class SchemaManagerError(Exception):
    """Schema management error with an HTTP-friendly status code."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ── Column type system ──────────────────────────────────────────────────────

COLUMN_TYPES: dict[str, dict[str, Any]] = {
    "String": {"label": "字符串", "has_length": True, "default_length": 255},
    "Text": {"label": "长文本", "has_length": False},
    "Integer": {"label": "整数", "has_length": False},
    "BigInteger": {"label": "大整数", "has_length": False},
    "Numeric": {"label": "小数", "has_length": False},
    "Boolean": {"label": "布尔", "has_length": False},
    "DateTime": {"label": "日期时间", "has_length": False},
    "Date": {"label": "日期", "has_length": False},
    "JSON": {"label": "JSON", "has_length": False},
}

# Casts considered safe (no data loss). Anything else produces a warning.
SAFE_CASTS: dict[str, set[str]] = {
    "String": {"String", "Text"},
    "Text": {"Text"},
    "Integer": {"Integer", "BigInteger", "Numeric", "String", "Text"},
    "BigInteger": {"BigInteger", "Numeric", "String", "Text"},
    "Numeric": {"Numeric", "String", "Text"},
    "Boolean": {"Boolean", "String", "Text"},
    "DateTime": {"DateTime", "String", "Text"},
    "Date": {"Date", "DateTime", "String", "Text"},
    "JSON": {"JSON", "Text"},
}

_PG_CAST: dict[str, str] = {
    "String": "varchar",
    "Text": "text",
    "Integer": "integer",
    "BigInteger": "bigint",
    "Numeric": "numeric(12,2)",
    "Boolean": "boolean",
    "DateTime": "timestamp",
    "Date": "date",
    "JSON": "json",
}

_DATE_FORMATS = ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d")


def column_type_list() -> list[dict[str, Any]]:
    """Return the supported column types for the frontend picker."""
    return [
        {
            "key": key,
            "label": meta["label"],
            "has_length": meta["has_length"],
            "default_length": meta.get("default_length"),
        }
        for key, meta in COLUMN_TYPES.items()
    ]


def build_sa_type(type_key: str, length: int | None = None) -> Any:
    """Build a SQLAlchemy type instance from a picker key."""
    if type_key == "String":
        return String(length or 255)
    if type_key == "Text":
        return Text()
    if type_key == "Integer":
        return Integer()
    if type_key == "BigInteger":
        return BigInteger()
    if type_key == "Numeric":
        return Numeric(12, 2)
    if type_key == "Boolean":
        return Boolean()
    if type_key == "DateTime":
        return DateTime()
    if type_key == "Date":
        return Date()
    if type_key == "JSON":
        return _json_type()
    raise SchemaManagerError(f"不支持的列类型 '{type_key}'")


def _json_type() -> Any:
    from sqlalchemy.dialects.postgresql import JSON

    return JSON()


def _type_ddl(type_key: str, length: int | None = None) -> str:
    """DDL source fragment (used inside generated migration files)."""
    if type_key == "String":
        return f"sa.String(length={length or 255})"
    if type_key == "Text":
        return "sa.Text()"
    if type_key == "Integer":
        return "sa.Integer()"
    if type_key == "BigInteger":
        return "sa.BigInteger()"
    if type_key == "Numeric":
        return "sa.Numeric(precision=12, scale=2)"
    if type_key == "Boolean":
        return "sa.Boolean()"
    if type_key == "DateTime":
        return "sa.DateTime()"
    if type_key == "Date":
        return "sa.Date()"
    if type_key == "JSON":
        return "postgresql.JSON()"
    raise SchemaManagerError(f"不支持的列类型 '{type_key}'")


def _sa_type_to_key(sa_type: Any) -> tuple[str, int | None]:
    """Map a SQLAlchemy column type back to a picker key + length."""
    type_module = type(sa_type).__module__
    type_name = type(sa_type).__name__
    if type_module.startswith("sqlalchemy.dialects") and type_name in ("JSON", "JSONB"):
        return "JSON", None
    if isinstance(sa_type, String):
        return "String", sa_type.length
    if isinstance(sa_type, Text):
        return "Text", None
    if isinstance(sa_type, Integer) and not isinstance(sa_type, BigInteger):
        return "Integer", None
    if isinstance(sa_type, BigInteger):
        return "BigInteger", None
    if isinstance(sa_type, Numeric):
        return "Numeric", None
    if isinstance(sa_type, Boolean):
        return "Boolean", None
    if isinstance(sa_type, DateTime):
        return "DateTime", None
    if isinstance(sa_type, Date):
        return "Date", None
    return "Text", None


def is_lossy_cast(old_key: str, new_key: str) -> bool:
    """Whether changing a column from old_key to new_key may lose data."""
    if old_key == new_key:
        return False
    return new_key not in SAFE_CASTS.get(old_key, set())


_NUMERIC_DEFAULT_RE = re.compile(r"^-?\d+(\.\d+)?$")
_DATE_DEFAULT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATETIME_DEFAULT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def validate_default_value(col: dict[str, Any]) -> None:
    """Raise if the user-provided default value is invalid for the column type."""
    value = col.get("default")
    if value is None or str(value).strip() == "":
        return
    value = str(value).strip()
    type_key = col["type"]
    if type_key in ("Integer", "BigInteger") and not INT_RE.match(value):
        raise SchemaManagerError(f"列 '{col['name']}' 的默认值 '{value}' 不是有效的整数")
    if type_key == "Numeric" and not _NUMERIC_DEFAULT_RE.match(value):
        raise SchemaManagerError(f"列 '{col['name']}' 的默认值 '{value}' 不是有效的数字")
    if type_key == "Boolean" and value.lower() not in ("true", "false"):
        raise SchemaManagerError(f"列 '{col['name']}' 的默认值必须是 true 或 false")
    if type_key == "Date" and not _DATE_DEFAULT_RE.match(value):
        raise SchemaManagerError(f"列 '{col['name']}' 的默认值格式应为 YYYY-MM-DD")
    if type_key == "DateTime" and not _DATETIME_DEFAULT_RE.match(value):
        raise SchemaManagerError(f"列 '{col['name']}' 的默认值格式应为 YYYY-MM-DD HH:MM:SS")
    if type_key == "JSON":
        try:
            json.loads(value)
        except ValueError as e:
            raise SchemaManagerError(f"列 '{col['name']}' 的默认值不是合法 JSON: {e}") from e


def default_server_default_sql(col: dict[str, Any]) -> str | None:
    """sa.text(...) DDL source for a column's default value, or None."""
    value = col.get("default")
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    type_key = col["type"]
    if type_key in ("Integer", "BigInteger", "Numeric"):
        return f"sa.text('{value}')"
    if type_key == "Boolean":
        return f"sa.text('{value.lower()}')"
    escaped = value.replace("'", "''")
    if type_key == "Date":
        return f"sa.text(\"'{escaped}'::date\")"
    if type_key == "DateTime":
        return f"sa.text(\"'{escaped.replace('T', ' ')}'::timestamp\")"
    if type_key == "JSON":
        return f"sa.text(\"'{escaped}'::json\")"
    return f"sa.text(\"'{escaped}'\")"


# ── Identifier validation ───────────────────────────────────────────────────


def validate_identifier(name: str, kind: str, reserved: frozenset[str]) -> None:
    """Raise SchemaManagerError if a table/column name is unsafe."""
    if not name or not IDENTIFIER_RE.match(name):
        raise SchemaManagerError(f"{kind}名称 '{name}' 无效：仅允许小写字母、数字和下划线，且以字母开头")
    if name in SQL_KEYWORDS:
        raise SchemaManagerError(f"{kind}名称 '{name}' 是 SQL 保留字，请更换")
    if name in reserved:
        raise SchemaManagerError(f"{kind}名称 '{name}' 为系统保留名称，请更换")


def validate_column_definitions(columns: list[dict[str, Any]]) -> None:
    """Validate a list of column definition dicts (incl. PK/FK flags)."""
    if not columns:
        raise SchemaManagerError("至少需要一个列定义")
    seen: set[str] = set()
    pk_cols = [c["name"] for c in columns if c.get("primary_key")]
    if len(pk_cols) > 1:
        raise SchemaManagerError(f"只能有一个主键列，当前标记了: {'、'.join(pk_cols)}")
    for col in columns:
        name = col["name"]
        validate_identifier(name, "列", RESERVED_COLUMN_NAMES)
        if name in seen:
            raise SchemaManagerError(f"列名 '{name}' 重复")
        seen.add(name)
        if col["type"] not in COLUMN_TYPES:
            raise SchemaManagerError(f"不支持的列类型 '{col['type']}'")
        if col["type"] == "String" and col.get("length") is not None:
            if not 1 <= int(col["length"]) <= 4000:
                raise SchemaManagerError(f"列 '{name}' 的长度必须在 1–4000 之间")
        validate_default_value(col)
        fk = (col.get("foreign_key") or "").strip()
        if fk:
            validate_foreign_key(name, fk)


FK_REF_RE = re.compile(r"^([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)$")


def validate_foreign_key(column_name: str, fk_ref: str) -> tuple[str, str]:
    """Validate a 'table.column' foreign-key reference; returns (table, column)."""
    m = FK_REF_RE.match(fk_ref)
    if not m:
        raise SchemaManagerError(f"列 '{column_name}' 的外键 '{fk_ref}' 格式无效，请使用 '表名.列名'")
    target_table, target_col = m.group(1), m.group(2)
    target_model = schema_validator.get_registered_model(target_table)
    if target_model is None:
        raise SchemaManagerError(f"外键目标表 '{target_table}' 不存在")
    target_column = target_model.__table__.columns.get(target_col)
    if target_column is None:
        raise SchemaManagerError(f"外键目标列 '{target_table}.{target_col}' 不存在")
    is_unique_target = (
        target_column.primary_key
        or target_column.unique
        or any(
            isinstance(con, UniqueConstraint) and [c.name for c in con.columns] == [target_col]
            for con in target_model.__table__.constraints
        )
    )
    if not is_unique_target:
        raise SchemaManagerError(f"外键目标列 '{target_table}.{target_col}' 必须是主键或唯一列")
    return target_table, target_col


def find_fk_dependencies(table_name: str, column_name: str | None = None) -> list[dict[str, str]]:
    """Dynamic tables whose foreign keys reference the given table/column."""
    deps: list[dict[str, str]] = []
    for other_name, model in _DYNAMIC_TABLES.items():
        if other_name == table_name:
            continue
        for fk in model.__table__.foreign_keys:
            if fk.column.table.name != table_name:
                continue
            if column_name is not None and fk.column.name != column_name:
                continue
            deps.append(
                {
                    "table": other_name,
                    "column": fk.parent.name,
                    "references": f"{table_name}.{fk.column.name}",
                }
            )
    return deps


# ── Runtime dynamic model registry ──────────────────────────────────────────

_DYNAMIC_TABLES: dict[str, type] = {}

# Per-table ingestion settings (effective upsert key + dedup toggle).
# Populated at creation and on restore; mirrored into the table_meta table.
_TABLE_SETTINGS: dict[str, dict[str, Any]] = {}


def get_table_settings(table_name: str) -> dict[str, Any] | None:
    return _TABLE_SETTINGS.get(table_name)


def set_table_settings(table_name: str, upsert_key: list[str], dedup_enabled: bool) -> None:
    _TABLE_SETTINGS[table_name] = {"upsert_key": list(upsert_key), "dedup_enabled": bool(dedup_enabled)}


def pop_table_settings(table_name: str) -> dict[str, Any] | None:
    return _TABLE_SETTINGS.pop(table_name, None)


def get_dynamic_table_names() -> list[str]:
    return list(_DYNAMIC_TABLES.keys())


def build_dynamic_model(
    table_name: str,
    columns: list[dict[str, Any]],
    upsert_key: list[str] | None = None,
    dedup_enabled: bool = True,
    add_content_hash: bool = False,
) -> type:
    """Construct a SQLAlchemy model class at runtime from column definitions.

    If one column is flagged primary_key it becomes the table's PK and no
    surrogate ``id`` column is generated; otherwise an auto-increment ``id``
    is added. ``default`` entries become server defaults.

    Ingestion settings: an explicit ``upsert_key`` (single or composite)
    becomes a unique constraint named ``uq_{table}_key`` (unless it equals
    the PK, which is already unique). A keyless table with ``dedup_enabled``
    gets a ``content_hash`` bookkeeping column with a unique constraint so
    identical re-uploads are skipped.
    """
    has_user_pk = any(col.get("primary_key") for col in columns)
    pk_cols = [col["name"] for col in columns if col.get("primary_key")]
    sa_cols: list[Any] = []
    if not has_user_pk:
        sa_cols.append(Column("id", Integer, primary_key=True, autoincrement=True, comment="主键ID"))
    constraints: list[Any] = []
    for col in columns:
        extra: list[Any] = []
        fk = (col.get("foreign_key") or "").strip()
        if fk:
            extra.append(ForeignKey(fk))
        default_value = (col.get("default") or "").strip() if isinstance(col.get("default"), str) else None
        server_default = col.get("_server_default_clause")
        if server_default is None and default_value:
            server_default = build_default_clause(col)
        sa_cols.append(
            Column(
                col["name"],
                build_sa_type(col["type"], col.get("length")),
                *extra,
                primary_key=bool(col.get("primary_key")),
                # User PK values come from the data (e.g. CSV imports) — never
                # auto-generate them, or imports would silently lose the key
                autoincrement=False if col.get("primary_key") else None,
                nullable=False if col.get("primary_key") else col.get("nullable", True),
                server_default=server_default,
                comment=col.get("label") or col["name"],
            )
        )
        if col.get("unique") and not col.get("primary_key"):
            constraints.append(UniqueConstraint(col["name"], name=f"uq_{table_name}_{col['name']}"))
        if fk:
            target_table, target_col = fk.split(".", 1)
            constraints.append(
                ForeignKeyConstraint(
                    [col["name"]],
                    [f"{target_table}.{target_col}"],
                    name=f"fk_{table_name}_{col['name']}",
                )
            )
    # Explicit upsert key — the PK already provides uniqueness for itself
    if upsert_key and list(upsert_key) != pk_cols:
        constraints.append(UniqueConstraint(*upsert_key, name=f"uq_{table_name}_key"))
    # Keyless dedup: hash of the business content, unique per table
    if add_content_hash:
        sa_cols.append(Column("content_hash", String(64), nullable=True, comment="内容哈希"))
        constraints.append(UniqueConstraint("content_hash", name=f"uq_{table_name}_content_hash"))
    sa_cols.append(Column("imported_at", DateTime, server_default=func.now(), comment="导入时间"))

    table = Table(table_name, Base.metadata, *sa_cols, *constraints)
    cls_name = "Dyn" + "".join(part.capitalize() for part in table_name.split("_")) + "_" + uuid.uuid4().hex[:6]
    return type(
        cls_name,
        (Base,),
        {
            "__table__": table,
            "__upsert_key__": list(upsert_key or pk_cols),
            "__dedup_enabled__": bool(dedup_enabled),
        },
    )


def build_default_clause(col: dict[str, Any]) -> Any:
    """SQLAlchemy server-default clause for a user-provided default, or None."""
    from sqlalchemy import text as sa_text

    value = col.get("default")
    if value is None or str(value).strip() == "":
        return None
    value = str(value).strip()
    type_key = col["type"]
    if type_key in ("Integer", "BigInteger", "Numeric"):
        return sa_text(value)
    if type_key == "Boolean":
        return sa_text(value.lower())
    if type_key == "Date":
        return sa_text(f"'{value}'::date")
    if type_key == "DateTime":
        return sa_text(f"'{value.replace('T', ' ')}'::timestamp")
    if type_key == "JSON":
        return sa_text(f"'{value}'::json")
    escaped = value.replace("'", "''")
    return sa_text(f"'{escaped}'")


def register_dynamic_table(table_name: str, display_name: str, model: type) -> None:
    """Register a dynamic table so it is visible to all features at runtime."""
    schema_validator.register_model(table_name, model)
    schema_validator.set_table_display_name(table_name, display_name)
    _DYNAMIC_TABLES[table_name] = model


def unregister_dynamic_table(table_name: str) -> None:
    """Remove a dynamic table from every registry."""
    model = _DYNAMIC_TABLES.pop(table_name, None)
    schema_validator.unregister_model(table_name)
    schema_validator.remove_table_display_name(table_name)
    _TABLE_SETTINGS.pop(table_name, None)
    if model is not None:
        Base.metadata.remove(model.__table__)


def extract_column_definitions(model: type) -> list[dict[str, Any]]:
    """Read business column definitions back from a model (for rebuild/drop).

    Includes a user-defined primary key column; only the surrogate ``id``
    bookkeeping column is skipped.
    """
    mapper = sa_inspect(model)
    unique_cols = {
        next(iter(con.columns)).name
        for con in model.__table__.constraints
        if isinstance(con, UniqueConstraint)
        and len(con.columns) == 1
        and next(iter(con.columns)).name not in _HIDDEN_COLUMNS
    }
    fk_refs: dict[str, str] = {}
    for fk in model.__table__.foreign_keys:
        fk_refs[fk.parent.name] = f"{fk.column.table.name}.{fk.column.name}"
    definitions: list[dict[str, Any]] = []
    for col in mapper.columns:
        if col.name in _HIDDEN_COLUMNS or (col.primary_key and col.name == "id"):
            continue
        type_key, length = _sa_type_to_key(col.type)
        definitions.append(
            {
                "name": col.name,
                "type": type_key,
                "length": length,
                "nullable": col.nullable,
                "unique": col.name in unique_cols,
                "primary_key": col.primary_key,
                "foreign_key": fk_refs.get(col.name),
                "label": getattr(col, "comment", None) or col.name,
                "default": _server_default_str(col),
                # Preserve an existing DB default verbatim when rebuilding
                "_server_default_clause": col.server_default,
            }
        )
    return definitions


def _server_default_str(col: Any) -> str | None:
    """Best-effort user-readable form of a reflected server default."""
    sd = col.server_default
    if sd is None:
        return None
    arg = getattr(sd, "arg", None)
    raw = getattr(arg, "text", None) or str(arg)
    raw = raw.strip()
    # Unwrap common PG renderings: 'val'::type / now() etc.
    m = re.match(r"^'(.*)'::[a-z_ ]+$", raw, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.match(r"^'(.*)'$", raw)
    if m:
        return m.group(1)
    return raw


def replace_dynamic_model(table_name: str, definitions: list[dict[str, Any]]) -> None:
    """Replace a dynamic model with one built from the given (post-change) columns."""
    display_name = schema_validator.TABLE_DISPLAY_NAMES.get(table_name, table_name)
    unregister_dynamic_table(table_name)
    new_model = build_dynamic_model(table_name, definitions)
    register_dynamic_table(table_name, display_name, new_model)


def rebuild_dynamic_model(table_name: str) -> None:
    """Rebuild a dynamic model from its current in-memory column definitions."""
    model = _DYNAMIC_TABLES.get(table_name)
    if model is None:
        return
    replace_dynamic_model(table_name, extract_column_definitions(model))


async def restore_dynamic_tables(conn: Any) -> int:
    """Re-register Schema-Manager-created tables after a server restart.

    Dynamic tables are recognized by their content_hash + imported_at
    bookkeeping columns; the Chinese display name is read from the
    PostgreSQL table comment. Handles FK ordering with retry passes.
    """
    from sqlalchemy import MetaData

    static_names = set(Base.metadata.tables.keys()) | {"alembic_version"}
    meta_holder: dict[str, Any] = {}

    def _reflect(sync_conn) -> None:
        m = MetaData()
        m.reflect(bind=sync_conn)
        meta_holder["m"] = m
        # Stored ingestion settings (table may not exist on a fresh DB)
        try:
            rows = sync_conn.execute(select(TableMeta)).all()
            meta_holder["settings"] = {r.table_name: (r.upsert_key, r.dedup_enabled) for r in rows}
        except Exception:
            meta_holder["settings"] = {}

    await conn.run_sync(_reflect)
    meta = meta_holder["m"]
    stored_settings: dict[str, tuple[str | None, bool]] = meta_holder.get("settings", {})

    # Collect candidate tables and their business column definitions
    pending: dict[str, list[dict[str, Any]]] = {}
    display_names: dict[str, str] = {}
    for name, table in meta.tables.items():
        if name in static_names or name in _DYNAMIC_TABLES:
            continue
        col_names = {c.name for c in table.columns}
        # Dynamic tables carry the imported_at bookkeeping column
        if "imported_at" not in col_names:
            continue
        unique_cols = {
            next(iter(con.columns)).name
            for con in table.constraints
            if isinstance(con, UniqueConstraint) and len(con.columns) == 1
        }
        definitions: list[dict[str, Any]] = []
        for col in table.columns:
            if col.name in _HIDDEN_COLUMNS or (col.primary_key and col.name == "id"):
                continue
            fk = next(iter(col.foreign_keys), None)
            type_key, length = _sa_type_to_key(col.type)
            definitions.append(
                {
                    "name": col.name,
                    "type": type_key,
                    "length": length,
                    "nullable": col.nullable,
                    "unique": col.name in unique_cols,
                    "primary_key": col.primary_key,
                    "foreign_key": f"{fk.column.table.name}.{fk.column.name}" if fk else None,
                    "label": col.comment or col.name,
                    "default": _server_default_str(col),
                    # Keep the DB default verbatim instead of re-rendering it
                    "_server_default_clause": col.server_default,
                }
            )
        pending[name] = definitions
        display_names[name] = table.comment or name
        # Legacy tables (created before content_hash was dropped) keep the
        # column so imports can still populate it
        if "content_hash" in col_names:
            ch_col = table.columns["content_hash"]
            pending[name].append(
                {
                    "name": "content_hash",
                    "type": "String",
                    "length": 64,
                    "nullable": bool(ch_col.nullable),
                    "unique": "content_hash" in unique_cols,
                    "primary_key": False,
                    "foreign_key": None,
                    "label": ch_col.comment or "内容哈希",
                    "default": None,
                    "_server_default_clause": None,
                }
            )

    # Build models in FK-safe order (retry passes for parent/child ordering)
    restored = 0
    while pending:
        progressed = False
        for name in list(pending):
            # Resolve stored ingestion settings; legacy tables (created
            # before settings existed) default to PK-as-upsert-key and
            # dedup enabled, which preserves their historical behavior.
            stored = stored_settings.get(name)
            if stored is not None and (stored[0] or "").strip():
                upsert_key = [c.strip() for c in stored[0].split(",") if c.strip()]
                dedup_enabled = bool(stored[1])
            elif stored is not None:
                upsert_key = None
                dedup_enabled = bool(stored[1])
            else:
                upsert_key = None
                dedup_enabled = True
            try:
                model = build_dynamic_model(
                    name,
                    pending[name],
                    upsert_key=upsert_key,
                    dedup_enabled=dedup_enabled,
                    add_content_hash=False,  # restored from DB columns, never invented
                )
            except Exception:
                continue  # FK target not registered yet — retry next pass
            register_dynamic_table(name, display_names[name], model)
            set_table_settings(name, model.__upsert_key__, dedup_enabled)
            del pending[name]
            restored += 1
            progressed = True
        if not progressed:
            break  # remaining tables reference unknown targets — skip them
    return restored


async def resync_dynamic_models(conn: Any) -> int:
    """Rebuild every dynamic model from the live database.

    Called after any structural migration so the in-memory registry always
    mirrors the DB (handles renames, FK target changes, etc. in one pass).
    """
    for name in list(_DYNAMIC_TABLES):
        unregister_dynamic_table(name)
    return await restore_dynamic_tables(conn)


# ── Column metadata (descriptions & default values) ───────────────────


async def ensure_column_meta_table(conn: Any) -> None:
    """Create the column_meta table if it does not exist yet (idempotent)."""

    def _create(sync_conn) -> None:
        ColumnMeta.__table__.create(sync_conn, checkfirst=True)

    await conn.run_sync(_create)


async def get_column_meta(db: AsyncSession, table_name: str) -> dict[str, dict[str, str | None]]:
    """{column_name: {description, default_value}} for one table."""
    await ensure_column_meta_table(await db.connection())
    result = await db.execute(select(ColumnMeta).where(ColumnMeta.table_name == table_name))
    return {
        m.column_name: {"description": m.description, "default_value": m.default_value} for m in result.scalars().all()
    }


async def upsert_column_meta(
    db: AsyncSession,
    table_name: str,
    column_name: str,
    description: str | None = None,
    default_value: str | None = None,
) -> None:
    """Insert or update a column_meta row."""
    await ensure_column_meta_table(await db.connection())
    result = await db.execute(
        select(ColumnMeta).where(ColumnMeta.table_name == table_name, ColumnMeta.column_name == column_name)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = ColumnMeta(table_name=table_name, column_name=column_name)
        db.add(row)
    if description is not None:
        row.description = description or None
    if default_value is not None:
        row.default_value = default_value or None
    await db.flush()


async def rename_column_meta(db: AsyncSession, table_name: str, old_col: str, new_col: str) -> None:
    result = await db.execute(
        select(ColumnMeta).where(ColumnMeta.table_name == table_name, ColumnMeta.column_name == old_col)
    )
    row = result.scalar_one_or_none()
    if row is not None:
        row.column_name = new_col
        await db.flush()


async def retag_column_meta_table(db: AsyncSession, old_table: str, new_table: str) -> None:
    """Point every column_meta row of a table at its new table name."""
    result = await db.execute(select(ColumnMeta).where(ColumnMeta.table_name == old_table))
    for row in result.scalars().all():
        row.table_name = new_table
    await db.flush()


async def rename_table_meta(db: AsyncSession, old_table: str, new_table: str) -> None:
    """Repoint both meta stores (column_meta rows + table_meta row) at the new name."""
    await retag_column_meta_table(db, old_table, new_table)
    result = await db.execute(select(TableMeta).where(TableMeta.table_name == old_table))
    row = result.scalar_one_or_none()
    if row is not None:
        row.table_name = new_table
        await db.flush()


async def delete_column_meta(db: AsyncSession, table_name: str, column_name: str | None = None) -> None:
    """Delete meta for one column, or for a whole table when column_name is None."""
    stmt = select(ColumnMeta).where(ColumnMeta.table_name == table_name)
    if column_name is not None:
        stmt = stmt.where(ColumnMeta.column_name == column_name)
    for row in (await db.execute(stmt)).scalars().all():
        await db.delete(row)
    await db.flush()


# ── Table-level ingestion settings (upsert key + dedup toggle) ─────────


async def ensure_table_meta_table(conn: Any) -> None:
    """Create the table_meta table if it does not exist yet (idempotent)."""

    def _create(sync_conn) -> None:
        TableMeta.__table__.create(sync_conn, checkfirst=True)

    await conn.run_sync(_create)


async def save_table_meta(db: AsyncSession, table_name: str, upsert_key: list[str], dedup_enabled: bool) -> None:
    """Insert or update a table's stored ingestion settings."""
    await ensure_table_meta_table(await db.connection())
    result = await db.execute(select(TableMeta).where(TableMeta.table_name == table_name))
    row = result.scalar_one_or_none()
    if row is None:
        row = TableMeta(table_name=table_name)
        db.add(row)
    row.upsert_key = ",".join(upsert_key) if upsert_key else None
    row.dedup_enabled = bool(dedup_enabled)
    await db.flush()


async def delete_table_meta(db: AsyncSession, table_name: str) -> None:
    result = await db.execute(select(TableMeta).where(TableMeta.table_name == table_name))
    row = result.scalar_one_or_none()
    if row is not None:
        await db.delete(row)
        await db.flush()


# ── FK target options (dropdown data) ─────────────────────────────────


def fk_options() -> list[dict[str, Any]]:
    """Tables and their FK-eligible columns (PK/unique) for the UI picker."""
    options: list[dict[str, Any]] = []
    for name in schema_validator.get_registered_tables():
        model = schema_validator.get_registered_model(name)
        if model is None:
            continue
        unique_cols = _unique_column_names(model)
        cols: list[dict[str, Any]] = []
        for col in sa_inspect(model).columns:
            if col.name in _HIDDEN_COLUMNS:
                continue
            if col.primary_key or col.name in unique_cols:
                cols.append(
                    {
                        "name": col.name,
                        "label": getattr(col, "comment", None) or col.name,
                        "type": str(col.type),
                        "primary_key": bool(col.primary_key),
                        "unique": (not col.primary_key) and col.name in unique_cols,
                    }
                )
        if cols:
            options.append(
                {
                    "table": name,
                    "chinese_name": schema_validator.get_chinese_table_name(name),
                    "columns": cols,
                }
            )
    return options


# ── Schema inspection ───────────────────────────────────────────────────────


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _unique_column_names(model: type) -> set[str]:
    names: set[str] = set()
    for col in model.__table__.columns:
        if col.unique:
            names.add(col.name)
    for con in model.__table__.constraints:
        if isinstance(con, UniqueConstraint) and len(con.columns) == 1:
            names.add(next(iter(con.columns)).name)
    return names


async def list_tables_info(db: AsyncSession) -> list[dict[str, Any]]:
    """All registered tables with names, counts, and read-only flags."""
    tables: list[dict[str, Any]] = []
    for name in schema_validator.get_registered_tables():
        model = schema_validator.get_registered_model(name)
        if model is None:
            continue
        mapper = sa_inspect(model)
        column_count = sum(1 for c in mapper.columns if c.name not in _HIDDEN_COLUMNS)
        result = await db.execute(select(func.count()).select_from(model.__table__))
        tables.append(
            {
                "name": name,
                "chinese_name": schema_validator.get_chinese_table_name(name),
                "column_count": column_count,
                "row_count": result.scalar() or 0,
                "read_only": name in READ_ONLY_TABLES,
                "dynamic": name in _DYNAMIC_TABLES,
            }
        )
    return tables


async def table_detail(db: AsyncSession, name: str) -> dict[str, Any]:
    """Full column detail plus a small sample of rows for preview."""
    model = schema_validator.get_registered_model(name)
    if model is None:
        raise SchemaManagerError(f"数据表 '{name}' 不存在", status_code=404)

    meta = await get_column_meta(db, name)
    mapper = sa_inspect(model)
    unique_cols = _unique_column_names(model)
    fk_refs: dict[str, str] = {}
    for fk in model.__table__.foreign_keys:
        fk_refs[fk.parent.name] = f"{fk.column.table.name}.{fk.column.name}"
    columns: list[dict[str, Any]] = []
    for col in mapper.columns:
        col_meta = meta.get(col.name, {})
        columns.append(
            {
                "name": col.name,
                "type": str(col.type),
                "nullable": col.nullable,
                "primary_key": col.primary_key,
                "unique": col.name in unique_cols,
                "foreign_key": fk_refs.get(col.name),
                "label": getattr(col, "comment", None) or col.name,
                "description": col_meta.get("description"),
                "default": col_meta.get("default_value") or _server_default_str(col),
                "internal": col.name in _HIDDEN_COLUMNS,
            }
        )

    result = await db.execute(select(model).limit(5))
    visible = [c.name for c in mapper.columns if c.name not in _HIDDEN_COLUMNS]
    sample_rows = [
        {col: _serialize_value(getattr(row, col, None)) for col in visible} for row in result.scalars().all()
    ]

    return {
        "name": name,
        "chinese_name": schema_validator.get_chinese_table_name(name),
        "read_only": name in READ_ONLY_TABLES,
        "dynamic": name in _DYNAMIC_TABLES,
        "upsert_key": (_TABLE_SETTINGS.get(name) or {}).get("upsert_key", []),
        "dedup_enabled": (_TABLE_SETTINGS.get(name) or {}).get("dedup_enabled", True),
        "columns": columns,
        "sample_rows": sample_rows,
    }


# ── Dependency scanning ─────────────────────────────────────────────────────


def _references(haystacks: list[str], table_name: str, column_name: str | None) -> bool:
    table_pat = re.compile(rf"\b{re.escape(table_name)}\b")
    for haystack in haystacks:
        if not haystack or not table_pat.search(haystack):
            continue
        if column_name is None:
            return True
        if re.search(rf"\b{re.escape(column_name)}\b", haystack):
            return True
    return False


async def find_dependencies(
    db: AsyncSession, table_name: str, column_name: str | None = None
) -> dict[str, list[dict[str, str]]]:
    """Find saved views/visualizations and FK-referencing tables."""
    result = await db.execute(select(View))
    dep_views: list[dict[str, str]] = []
    view_ids: list[Any] = []
    for view in result.scalars().all():
        haystacks = [
            view.generated_sql or "",
            json.dumps(view.config_json, ensure_ascii=False),
        ]
        if _references(haystacks, table_name, column_name):
            dep_views.append({"id": str(view.id), "name": view.name})
            view_ids.append(view.id)

    dep_viz: list[dict[str, str]] = []
    if view_ids:
        viz_result = await db.execute(select(Visualization).where(Visualization.view_id.in_(view_ids)))
        dep_viz = [{"id": str(v.id), "name": v.name} for v in viz_result.scalars().all()]

    return {
        "views": dep_views,
        "visualizations": dep_viz,
        "tables": find_fk_dependencies(table_name, column_name),
    }


# ── CSV schema inference ────────────────────────────────────────────────────


def _english_column_name(header: str, index: int, used: set[str]) -> str:
    """Derive a safe English column name from a (possibly Chinese) header."""
    base = ""
    stripped = header.strip()
    if stripped and re.fullmatch(r"[A-Za-z][A-Za-z0-9_ ]*", stripped):
        base = re.sub(r"[^a-z0-9]+", "_", stripped.lower()).strip("_")
    if not base:
        base = f"col_{index + 1}"
    name = base
    suffix = 2
    while name in used or name in RESERVED_COLUMN_NAMES or name in SQL_KEYWORDS:
        name = f"{base}_{suffix}"
        suffix += 1
    used.add(name)
    return name


def _infer_column_type(values: list[str]) -> tuple[str, int | None]:
    """Infer a column type from string values (already stringified, may be empty)."""
    non_empty = [v.strip() for v in values if v is not None and str(v).strip()]
    if not non_empty:
        return "String", 255

    if all(INT_RE.match(v) for v in non_empty):
        big = any(abs(int(v)) > 2**31 - 1 for v in non_empty)
        return ("BigInteger" if big else "Integer"), None

    numeric = True
    for v in non_empty:
        try:
            Decimal(v)
        except InvalidOperation:
            numeric = False
            break
    if numeric:
        return "Numeric", None

    has_time = False
    all_dates = True
    for v in non_empty:
        parsed = False
        for fmt in _DATE_FORMATS:
            try:
                dt.datetime.strptime(v, fmt)
                parsed = True
                if " " in fmt or "%H" in fmt:
                    has_time = True
                break
            except ValueError:
                continue
        if not parsed:
            all_dates = False
            break
    if all_dates:
        return ("DateTime" if has_time else "Date"), None

    max_len = max(len(v) for v in non_empty)
    if max_len <= 200:
        return "String", min(255, max(max_len * 2, 50))
    return "Text", None


def infer_schema(df: pd.DataFrame, raw_headers: list[str]) -> list[dict[str, Any]]:
    """Propose a column schema from a parsed DataFrame + its raw headers."""
    used: set[str] = set()
    proposed: list[dict[str, Any]] = []
    for i, header in enumerate(raw_headers):
        header = str(header).strip()
        label = header or f"列{i + 1}"
        name = _english_column_name(header, i, used)
        values: list[str] = []
        if i < df.shape[1]:
            values = ["" if (v is None or (isinstance(v, float) and pd.isna(v))) else str(v) for v in df.iloc[:, i]]
        type_key, length = _infer_column_type(values)
        proposed.append(
            {
                "name": name,
                "label": label,
                "type": type_key,
                "length": length,
                "nullable": True,
                "unique": False,
            }
        )
    return proposed


# ── Alembic migration generation ────────────────────────────────────────────

_MIGRATION_TEMPLATE = '''"""{message}

Revision ID: {revision}
Revises: {down_revision_display}
Create Date: {create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = {revision_repr}
down_revision: Union[str, Sequence[str], None] = {down_revision_repr}
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
{upgrade_body}


def downgrade() -> None:
    """Downgrade schema."""
{downgrade_body}
'''


def _alembic_config() -> AlembicConfig:
    # version_locations (static + runtime dirs) comes from alembic.ini
    cfg = AlembicConfig(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


def current_migration_head() -> str | None:
    return ScriptDirectory.from_config(_alembic_config()).get_current_head()


def _slugify(message: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", message.lower()).strip("_")[:40] or "change"


def write_migration(message: str, upgrade_body: str, downgrade_body: str) -> Path:
    """Write a new migration file chained onto the current head.

    Files are written to RUNTIME_MIGRATIONS_DIR (outside the uvicorn
    --reload watch tree) so creating a table never restarts the server
    mid-request.
    """
    revision = uuid.uuid4().hex[:12]
    down = current_migration_head()
    content = _MIGRATION_TEMPLATE.format(
        message=message,
        revision=revision,
        down_revision_display=down or "None",
        create_date=dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        revision_repr=repr(revision),
        down_revision_repr=repr(down) if down else "None",
        upgrade_body=upgrade_body,
        downgrade_body=downgrade_body,
    )
    RUNTIME_MIGRATIONS_DIR.mkdir(parents=True, exist_ok=True)
    path = RUNTIME_MIGRATIONS_DIR / f"{revision}_{_slugify(message)}.py"
    path.write_text(content, encoding="utf-8")
    return path


def _run_alembic_upgrade_blocking() -> str:
    """Run `alembic upgrade head` synchronously; returns combined output.

    Uses blocking subprocess.run (loop-agnostic) instead of asyncio
    create_subprocess_exec, which raises NotImplementedError on Windows when
    the running event loop lacks a subprocess transport (e.g. uvicorn --reload).
    """
    env = {**os.environ, "DATABASE_URL": settings.database_url}
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return (completed.stdout or "") + (completed.stderr or "")


async def run_alembic_upgrade() -> None:
    """Run `alembic upgrade head` in a subprocess (own event loop, own connection)."""
    try:
        output = await asyncio.to_thread(_run_alembic_upgrade_blocking)
    except FileNotFoundError as e:
        raise SchemaManagerError(f"无法启动 Alembic 子进程: {e}", status_code=500) from e

    # Re-check the applied head; a non-zero exit surfaces the alembic output
    head = current_migration_head()
    applied = await _read_applied_version()
    if head is not None and applied != head:
        raise SchemaManagerError(
            f"Alembic 迁移执行失败 (已应用 {applied or '无'}, 目标 {head}): {output[-1500:]}",
            status_code=500,
        )
    # Dispose pooled connections so new DDL is picked up cleanly
    await engine.dispose()


async def _read_applied_version() -> str | None:
    """Read the alembic_version currently applied in the database."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return row[0] if row else None


# ── DDL op builders (source lines for generated migrations) ─────────────────


def _column_ddl(col: dict[str, Any]) -> str:
    label = (col.get("label") or col["name"]).replace("'", "\\'")
    nullable = False if col.get("primary_key") else bool(col.get("nullable", True))
    # User PK values come from imported data — suppress implicit SERIAL
    autoinc = ", autoincrement=False" if col.get("primary_key") else ""
    default_sql = default_server_default_sql(col)
    default_part = f", server_default={default_sql}" if default_sql else ""
    return (
        f"sa.Column('{col['name']}', {_type_ddl(col['type'], col.get('length'))}{autoinc}, "
        f"nullable={nullable}{default_part}, comment='{label}')"
    )


def create_table_ops(
    table_name: str,
    columns: list[dict[str, Any]],
    display_name: str | None = None,
    upsert_key: list[str] | None = None,
    add_content_hash: bool = False,
) -> str:
    """op.create_table(...) source for a dynamic table (with bookkeeping cols).

    When display_name is given, a COMMENT ON TABLE statement stores it in the
    database so the Chinese name survives server restarts. An explicit
    upsert key (that differs from the PK) becomes ``uq_{table}_key``;
    ``add_content_hash`` adds the dedup hash column + its unique constraint.
    """
    lines = [f"    op.create_table('{table_name}',"]
    pk_cols = [c["name"] for c in columns if c.get("primary_key")]
    if not pk_cols:
        lines.append("    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='主键ID'),")
    for col in columns:
        lines.append(f"    {_column_ddl(col)},")
    if add_content_hash:
        lines.append("    sa.Column('content_hash', sa.String(length=64), nullable=True, comment='内容哈希'),")
    lines.append(
        "    sa.Column('imported_at', sa.DateTime(), server_default=sa.text('now()'), "
        "nullable=True, comment='导入时间'),"
    )
    if pk_cols:
        lines.append(f"    sa.PrimaryKeyConstraint('{pk_cols[0]}'),")
    else:
        lines.append("    sa.PrimaryKeyConstraint('id'),")
    for col in columns:
        if col.get("unique") and not col.get("primary_key"):
            lines.append(f"    sa.UniqueConstraint('{col['name']}', name='uq_{table_name}_{col['name']}'),")
        fk = (col.get("foreign_key") or "").strip()
        if fk:
            lines.append(
                f"    sa.ForeignKeyConstraint(['{col['name']}'], ['{fk}'], name='fk_{table_name}_{col['name']}'),"
            )
    if upsert_key and list(upsert_key) != pk_cols:
        cols_sql = ", ".join(f"'{c}'" for c in upsert_key)
        lines.append(f"    sa.UniqueConstraint({cols_sql}, name='uq_{table_name}_key'),")
    if add_content_hash:
        lines.append(f"    sa.UniqueConstraint('content_hash', name='uq_{table_name}_content_hash'),")
    # IF NOT EXISTS guards against a DDL-success/response-lost retry race
    lines.append("    if_not_exists=True,")
    lines.append("    )")
    if display_name:
        escaped = display_name.replace("'", "''")
        lines.append(f"    op.execute(\"COMMENT ON TABLE {table_name} IS '{escaped}'\")")
    return "\n".join(lines)


def add_column_ops(table_name: str, col: dict[str, Any]) -> str:
    lines = [f"    op.add_column('{table_name}', {_column_ddl(col)})"]
    if col.get("unique"):
        lines.append(
            f"    op.create_unique_constraint('uq_{table_name}_{col['name']}', '{table_name}', ['{col['name']}'])"
        )
    fk = (col.get("foreign_key") or "").strip()
    if fk:
        target_table, target_col = fk.split(".", 1)
        lines.append(
            f"    op.create_foreign_key('fk_{table_name}_{col['name']}', '{table_name}', "
            f"'{target_table}', ['{col['name']}'], ['{target_col}'])"
        )
    return "\n".join(lines)


def drop_column_ops(table_name: str, col: dict[str, Any]) -> str:
    lines: list[str] = []
    fk = (col.get("foreign_key") or "").strip()
    if fk:
        lines.append(f"    op.drop_constraint('fk_{table_name}_{col['name']}', '{table_name}', type_='foreignkey')")
    if col.get("unique"):
        lines.append(f"    op.drop_constraint('uq_{table_name}_{col['name']}', '{table_name}', type_='unique')")
    lines.append(f"    op.drop_column('{table_name}', '{col['name']}')")
    return "\n".join(lines)


def alter_column_ops(
    table_name: str,
    col_name: str,
    old: dict[str, Any],
    new: dict[str, Any],
) -> str:
    parts = [
        f"    op.alter_column('{table_name}', '{col_name}',",
        f"        existing_type={_type_ddl(old['type'], old.get('length'))},",
        f"        type_={_type_ddl(new['type'], new.get('length'))},",
    ]
    if new.get("nullable") is not None:
        parts.append(f"        nullable={bool(new['nullable'])},")
    parts.append(f"        existing_nullable={bool(old.get('nullable', True))},")
    parts.append(f"        postgresql_using='{col_name}::{_PG_CAST[new['type']]}')")
    return "\n".join(parts)


def drop_table_ops(table_name: str) -> str:
    return f"    op.drop_table('{table_name}')"


# ── Comprehensive column-edit op builders ────────────────────────


def rename_column_ops(table_name: str, old_name: str, new_name: str) -> str:
    return f"    op.alter_column('{table_name}', '{old_name}', new_column_name='{new_name}')"


def column_comment_ops(table_name: str, col_name: str, label: str) -> str:
    escaped = label.replace("'", "''")
    return f"    op.execute(\"COMMENT ON COLUMN {table_name}.{col_name} IS '{escaped}'\")"


def nullable_ops(table_name: str, col_name: str, nullable: bool) -> str:
    return f"    op.alter_column('{table_name}', '{col_name}', nullable={bool(nullable)})"


def create_unique_ops(table_name: str, col_name: str) -> str:
    return f"    op.create_unique_constraint('uq_{table_name}_{col_name}', '{table_name}', ['{col_name}'])"


def drop_unique_ops(table_name: str, col_name: str) -> str:
    return f"    op.drop_constraint('uq_{table_name}_{col_name}', '{table_name}', type_='unique')"


def set_default_ops(table_name: str, col: dict[str, Any]) -> str:
    default_sql = default_server_default_sql(col)
    if default_sql is None:
        return f"    op.alter_column('{table_name}', '{col['name']}', server_default=None)"
    return f"    op.alter_column('{table_name}', '{col['name']}', server_default={default_sql})"


def drop_fk_ops(table_name: str, col_name: str) -> str:
    return f"    op.drop_constraint('fk_{table_name}_{col_name}', '{table_name}', type_='foreignkey')"


def create_fk_ops(table_name: str, col_name: str, fk_ref: str) -> str:
    target_table, target_col = fk_ref.split(".", 1)
    return (
        f"    op.create_foreign_key('fk_{table_name}_{col_name}', '{table_name}', "
        f"'{target_table}', ['{col_name}'], ['{target_col}'])"
    )


# ── Upsert-key / dedup settings op builders ─────────────────────


def create_upsert_key_ops(table_name: str, cols: list[str]) -> str:
    cols_sql = ", ".join(f"'{c}'" for c in cols)
    return f"    op.create_unique_constraint('uq_{table_name}_key', '{table_name}', [{cols_sql}])"


def drop_upsert_key_ops(table_name: str) -> str:
    return f"    op.drop_constraint('uq_{table_name}_key', '{table_name}', type_='unique')"


def add_content_hash_ops(table_name: str) -> str:
    return "\n".join(
        [
            f"    op.add_column('{table_name}', sa.Column('content_hash', sa.String(length=64), "
            "nullable=True, comment='内容哈希'))",
            f"    op.create_unique_constraint('uq_{table_name}_content_hash', '{table_name}', ['content_hash'])",
        ]
    )


def drop_content_hash_ops(table_name: str) -> str:
    return "\n".join(
        [
            f"    op.drop_constraint('uq_{table_name}_content_hash', '{table_name}', type_='unique')",
            f"    op.drop_column('{table_name}', 'content_hash')",
        ]
    )


def rename_table_ops(old_name: str, new_name: str) -> str:
    return f"    op.rename_table('{old_name}', '{new_name}')"


def table_comment_ops(table_name: str, display_name: str) -> str:
    escaped = display_name.replace("'", "''")
    return f"    op.execute(\"COMMENT ON TABLE {table_name} IS '{escaped}'\")"
