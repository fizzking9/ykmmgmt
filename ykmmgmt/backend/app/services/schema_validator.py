"""Pre-cleaning schema validation gate.

Compares uploaded file headers (Chinese) against SQLAlchemy model column comments
(also Chinese) to validate the file matches the target table before any processing.
"""

from dataclasses import dataclass, field

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase


@dataclass
class SchemaValidationResult:
    """Result of schema validation."""

    valid: bool
    target_table: str
    column_mapping: dict[str, str] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)
    expected: list[str] = field(default_factory=list)


# English table name → Chinese display name
TABLE_DISPLAY_NAMES: dict[str, str] = {
    "refund_orders": "退费单",
    "service_refund_work_orders": "服务退款工单",
    "wallet_withdrawals": "钱包提现操作",
}

# Reverse mapping for Chinese → English
CHINESE_TO_ENGLISH_TABLE: dict[str, str] = {v: k for k, v in TABLE_DISPLAY_NAMES.items()}

# Model registry: English table name → SQLAlchemy model class
_MODEL_REGISTRY: dict[str, type[DeclarativeBase]] = {}


def register_model(table_name: str, model_class: type[DeclarativeBase]) -> None:
    """Register a model class for schema validation."""
    _MODEL_REGISTRY[table_name] = model_class


def unregister_model(table_name: str) -> None:
    """Remove a model from the registry (used when a dynamic table is dropped)."""
    _MODEL_REGISTRY.pop(table_name, None)


def set_table_display_name(english_name: str, chinese_name: str) -> None:
    """Add/update the Chinese display name for a table and refresh the reverse map."""
    TABLE_DISPLAY_NAMES[english_name] = chinese_name
    _rebuild_chinese_map()


def remove_table_display_name(english_name: str) -> None:
    """Remove a table's display name entry and refresh the reverse map."""
    TABLE_DISPLAY_NAMES.pop(english_name, None)
    _rebuild_chinese_map()


def _rebuild_chinese_map() -> None:
    """Rebuild CHINESE_TO_ENGLISH_TABLE in place (keeps module references valid)."""
    CHINESE_TO_ENGLISH_TABLE.clear()
    CHINESE_TO_ENGLISH_TABLE.update({v: k for k, v in TABLE_DISPLAY_NAMES.items()})


def get_registered_tables() -> list[str]:
    """Return list of registered English table names."""
    return list(_MODEL_REGISTRY.keys())


def get_registered_model(table_name: str) -> type[DeclarativeBase] | None:
    """Return the registered model class for a table name, or None."""
    return _MODEL_REGISTRY.get(table_name)


def get_chinese_table_name(english_name: str) -> str:
    """Map English table name to Chinese display name."""
    return TABLE_DISPLAY_NAMES.get(english_name, english_name)


def resolve_target_table(raw: str) -> str | None:
    """Resolve a target_table value (Chinese or English) to English table name."""
    if raw in _MODEL_REGISTRY:
        return raw
    if raw in CHINESE_TO_ENGLISH_TABLE:
        return CHINESE_TO_ENGLISH_TABLE[raw]
    return None


def build_comment_mapping(model_class: type[DeclarativeBase]) -> dict[str, str]:
    """Build {chinese_comment: english_column_name} from a SQLAlchemy model.

    Handles duplicate comments (e.g., two "备注" columns) by using positional
    ordering: first occurrence in model → first match, second → second.

    Only the surrogate ``id`` column is excluded — a user-defined primary key
    is a business column and must be importable from the file.
    """
    mapper = sa_inspect(model_class)
    mapping: dict[str, str] = {}
    comment_order: dict[str, list[str]] = {}

    for col in mapper.columns:
        comment = getattr(col, "comment", None)
        if not comment or col.name == "id" or col.name in ("imported_at", "created_at", "content_hash"):
            continue
        comment = comment.strip()
        if comment not in mapping:
            mapping[comment] = col.name
            comment_order[comment] = [col.name]
        else:
            comment_order[comment].append(col.name)

    return mapping


def get_comment_order(model_class: type[DeclarativeBase]) -> dict[str, list[str]]:
    """Build {comment: [ordered_column_names]} for disambiguation."""
    mapper = sa_inspect(model_class)
    order: dict[str, list[str]] = {}
    for col in mapper.columns:
        comment = getattr(col, "comment", None)
        if not comment or col.name == "id" or col.name in ("imported_at", "created_at"):
            continue
        comment = comment.strip()
        if comment not in order:
            order[comment] = []
        order[comment].append(col.name)
    return order


def validate_headers(
    file_headers: list[str],
    target_table: str,
) -> SchemaValidationResult:
    """Validate file headers against the target table's column labels.

    Headers are matched primarily against the Chinese labels (column
    comments); a header that equals a column's real name also matches, so
    files with English headers — and production tables whose column names
    are themselves Chinese — import without extra configuration.

    Returns a SchemaValidationResult. If valid=True, column_mapping contains
    {header: english_column} for the parser to rename columns.
    """
    english_name = resolve_target_table(target_table)
    if english_name is None:
        return SchemaValidationResult(
            valid=False,
            target_table=target_table,
            missing=[],
            unexpected=[],
            expected=list(TABLE_DISPLAY_NAMES.values()),
        )

    model_class = _MODEL_REGISTRY.get(english_name)
    if model_class is None:
        return SchemaValidationResult(
            valid=False,
            target_table=target_table,
            missing=[],
            unexpected=[],
            expected=list(TABLE_DISPLAY_NAMES.values()),
        )

    chinese_name = get_chinese_table_name(english_name)
    comment_to_col = build_comment_mapping(model_class)
    comment_order = get_comment_order(model_class)
    expected_comments = list(comment_to_col.keys())

    # Fallback: match by the column's real name (skipping bookkeeping cols)
    mapper = sa_inspect(model_class)
    name_to_col: dict[str, str] = {}
    for col in mapper.columns:
        if col.name == "id" or col.name in ("imported_at", "created_at", "content_hash"):
            continue
        name_to_col[col.name] = col.name

    # Track which headers matched
    column_mapping: dict[str, str] = {}
    missing: list[str] = []
    unexpected: list[str] = []
    used_cols: set[str] = set()

    # Track usage count per comment for disambiguation
    comment_use_count: dict[str, int] = dict.fromkeys(comment_order, 0)

    for header in file_headers:
        header = header.strip()
        if not header:
            continue

        # 1) Label (Chinese comment) match
        if header in comment_to_col:
            idx = comment_use_count[header]
            cols = comment_order[header]
            if idx < len(cols) and cols[idx] not in used_cols:
                column_mapping[header] = cols[idx]
                used_cols.add(cols[idx])
                comment_use_count[header] += 1
            else:
                unexpected.append(header)
        # 2) Real column name match
        elif header in name_to_col and name_to_col[header] not in used_cols:
            column_mapping[header] = name_to_col[header]
            used_cols.add(name_to_col[header])
        else:
            unexpected.append(header)

    # Find required columns (non-nullable without default)
    for col in mapper.columns:
        comment = getattr(col, "comment", None)
        if not comment or col.name == "id" or col.name in ("imported_at", "created_at", "content_hash"):
            continue
        comment = comment.strip()
        if not col.nullable and col.default is None and col.server_default is None:
            # This is a required column — check if any header mapped to it
            if col.name not in column_mapping.values():
                if comment not in missing:
                    missing.append(comment)

    valid = len(missing) == 0

    return SchemaValidationResult(
        valid=valid,
        target_table=chinese_name,
        column_mapping=column_mapping,
        missing=missing,
        unexpected=unexpected,
        expected=expected_comments,
    )
