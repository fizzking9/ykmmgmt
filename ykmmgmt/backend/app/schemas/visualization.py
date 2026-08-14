"""Pydantic schemas for Visualization CRUD."""

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

# ── Chart type constants ────────────────────────────────────────────────────

CHART_TYPES = ("table", "kpi_card", "bar", "line", "pie", "scatter", "histogram", "boxplot")

ChartType = Literal["table", "kpi_card", "bar", "line", "pie", "scatter", "histogram", "boxplot"]

# Required config_json keys per chart type
CHART_CONFIG_REQUIRED_KEYS: dict[str, set[str]] = {
    "table": {"visible_columns"},
    "kpi_card": {"value_column", "label"},
    "bar": {"x_column", "y_columns"},
    "line": {"x_column", "y_columns"},
    "pie": {"label_column", "value_column"},
    "scatter": {"x_column", "y_columns"},
    "histogram": {"columns", "bins"},
    "boxplot": {"category_column", "value_column"},
}


def validate_config_keys(chart_type: str, config_json: dict) -> list[str]:
    """Return a list of missing required keys for the given chart_type."""
    required = CHART_CONFIG_REQUIRED_KEYS.get(chart_type, set())
    return [k for k in required if k not in config_json]


# ── CRUD schemas ────────────────────────────────────────────────────────────


class VisualizationCreate(BaseModel):
    """Request body for creating a visualization."""

    name: str = Field(..., min_length=1, max_length=255, description="可视化名称")
    view_id: uuid.UUID = Field(..., description="关联视图ID")
    chart_type: ChartType = Field(..., description="图表类型")
    config_json: dict[str, Any] = Field(..., description="图表配置")


class VisualizationUpdate(BaseModel):
    """Request body for updating a visualization. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255, description="可视化名称")
    view_id: uuid.UUID | None = Field(None, description="关联视图ID")
    chart_type: ChartType | None = Field(None, description="图表类型")
    config_json: dict[str, Any] | None = Field(None, description="图表配置")


class VisualizationResponse(BaseModel):
    """Response body for a single visualization (full detail)."""

    id: uuid.UUID
    name: str
    view_id: uuid.UUID
    chart_type: str
    config_json: dict[str, Any]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class VisualizationListResponse(BaseModel):
    """Response body for visualization listing (summary)."""

    id: uuid.UUID
    name: str
    view_id: uuid.UUID
    chart_type: str
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class VisualizationDataResponse(BaseModel):
    """Response body for visualization data endpoint."""

    columns: list[str]
    rows: list[dict[str, Any]]
    chart_type: str
    config_json: dict[str, Any]
