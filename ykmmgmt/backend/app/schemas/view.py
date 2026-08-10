"""Pydantic schemas for View CRUD."""

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── ViewConfig sub-schemas ──────────────────────────────────────────────────


class ColumnSpec(BaseModel):
    """A single column selection with optional alias."""

    table: str = Field(..., description="Table name (English)")
    column: str = Field(..., description="Column name (English)")
    alias: str | None = Field(None, description="Output column alias")


class JoinSpec(BaseModel):
    """A single join specification."""

    left_table: str
    right_table: str
    right_alias: str | None = Field(
        None, description="Alias for right_table (used for self-joins, e.g. refund_orders_1)"
    )
    join_type: str = Field("INNER", description="INNER, LEFT, or RIGHT")
    left_key: str
    right_key: str


class FilterSpec(BaseModel):
    """A single filter condition."""

    column: str = Field(..., description="Fully qualified column (table.column) or computed column alias")
    operator: str = Field(
        default="eq",
        description=(
            "eq, neq, gt, gte, lt, lte, contains, "
            "startswith, endswith, is_null, is_not_null. "
            "Ignored when date_start or date_end is set."
        ),
    )
    value: Any = Field(None, description="Filter value (ignored for is_null/is_not_null and date ranges)")
    date_start: str | None = Field(None, description="Date range start (ISO date string, inclusive)")
    date_end: str | None = Field(None, description="Date range end (ISO date string, inclusive)")


class AggregationSpec(BaseModel):
    """A single aggregation expression."""

    function: str = Field(..., description="SUM, COUNT, AVG, MIN, MAX")
    column: str = Field(..., description="Column to aggregate (use '*' for COUNT)")
    alias: str | None = Field(None, description="Output column alias")


class ComputedOperand(BaseModel):
    """An operand in a computed column expression — either a table column or a constant."""

    type: Literal["column", "constant"] = Field(..., description="'column' or 'constant'")
    table: str | None = Field(None, description="Table logical name (required when type='column')")
    column: str | None = Field(None, description="Column name (required when type='column')")
    value: str | None = Field(None, description="Constant value as string (required when type='constant')")


class ComputedColumnSpec(BaseModel):
    """A computed / derived column expression."""

    alias: str = Field(..., min_length=1, description="Output column alias (required)")
    expression_type: Literal["arithmetic", "datetime_shift", "datetime_trunc"] = Field(
        ...,
        description=(
            "'arithmetic' (numeric +-*/), 'datetime_shift' (date ± interval), "
            "or 'datetime_trunc' (extract date part)"
        ),
    )
    # ── Arithmetic fields (chained) ──
    operands: list[ComputedOperand] = Field(default_factory=list, description="2+ operands for arithmetic")
    operators: list[str] = Field(default_factory=list, description="Operators between operands (+, -, *, /)")
    # ── Datetime shift fields ──
    base_column: ComputedOperand | None = None
    shift_value: str | None = None
    shift_unit: Literal["days", "months", "years"] | None = None
    # ── Datetime trunc fields ──
    trunc_column: ComputedOperand | None = None
    trunc_unit: Literal["year", "quarter", "month", "week", "day", "hour", "minute"] | None = None


class OrderSpec(BaseModel):
    """A single ORDER BY specification."""

    column: str = Field(..., description="Column name or computed column alias")
    direction: Literal["asc", "desc"] = Field("asc", description="Sort direction")


class ViewConfig(BaseModel):
    """The full view configuration stored in config_json."""

    from_tables: list[str] = Field(..., min_length=1, description="Source tables (first is primary FROM)")
    joins: list[JoinSpec] = Field(default_factory=list)
    columns: list[ColumnSpec] = Field(default_factory=list)
    computed_columns: list[ComputedColumnSpec] = Field(default_factory=list)
    selected_computed_columns: list[str] = Field(
        default_factory=list,
        description="Computed column aliases explicitly selected for SELECT output",
    )
    filters: list[FilterSpec] = Field(default_factory=list)
    group_by: list[str] = Field(default_factory=list, description="Column names for GROUP BY")
    aggregations: list[AggregationSpec] = Field(default_factory=list)
    order_by: list[OrderSpec] = Field(default_factory=list, description="Sort columns")
    limit: int | None = Field(None, ge=0, description="Maximum rows to return (0 or null = no limit)")


# ── CRUD schemas ────────────────────────────────────────────────────────────


class ViewCreate(BaseModel):
    """Request body for creating a view."""

    name: str = Field(..., min_length=1, max_length=255, description="视图名称")
    description: str | None = Field(None, description="视图描述")
    config_json: ViewConfig = Field(..., description="视图配置")


class ViewUpdate(BaseModel):
    """Request body for updating a view. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255, description="视图名称")
    description: str | None = Field(None, description="视图描述")
    config_json: ViewConfig | None = Field(None, description="视图配置")


class ViewResponse(BaseModel):
    """Response body for a single view."""

    id: uuid.UUID
    name: str
    description: str | None
    config_json: ViewConfig
    generated_sql: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ViewListResponse(BaseModel):
    """Response body for view listing (summary only, no SQL/config)."""

    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class PreviewRequest(BaseModel):
    """Request body for preview endpoint."""

    config_json: ViewConfig = Field(..., description="视图配置（不保存）")


class PreviewResponse(BaseModel):
    """Response body for preview endpoint."""

    sql: str
    rows: list[dict[str, Any]]
    columns: list[str]


class ViewDataResponse(BaseModel):
    """Response body for view data execution endpoint."""

    rows: list[dict[str, Any]]
    total: int
    page: int
    size: int
    columns: list[str]
