"""Pydantic schemas for Dashboard CRUD."""

import datetime
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

# ── Tile type constants ─────────────────────────────────────────────────────

TILE_TYPES = ("visualization", "text", "kpi_card")

TileType = Literal["visualization", "text", "kpi_card"]

# Required config keys for ad-hoc KPI card tiles
KPI_TILE_REQUIRED_KEYS: set[str] = {"view_id", "value_column", "label", "agg"}


class DashboardTile(BaseModel):
    """A single tile in the dashboard layout.

    Carries the raw ``react-grid-layout`` geometry fields (``i``, ``x``,
    ``y``, ``w``, ``h``) plus tile-type-specific payload. Extra fields from
    the layout array (e.g. ``static``, ``moved``) are preserved so the
    layout round-trips faithfully.
    """

    model_config = {"extra": "allow"}

    i: str = Field(..., min_length=1, description="瓦片唯一标识（布局键）")
    tile_type: TileType = Field(..., description="瓦片类型")
    visualization_id: uuid.UUID | None = Field(None, description="关联可视化ID（tile_type=visualization 时必填）")
    x: int = Field(..., ge=0, description="网格列位置")
    y: int = Field(..., ge=0, description="网格行位置")
    w: int = Field(..., ge=1, description="网格宽度")
    h: int = Field(..., ge=1, description="网格高度")
    content: str | None = Field(None, description="文本瓦片内容（Markdown）")
    config: dict[str, Any] | None = Field(None, description="KPI 瓦片配置（view_id/value_column/label/agg）")

    @model_validator(mode="after")
    def _validate_tile_payload(self) -> "DashboardTile":
        """Enforce per-type payload requirements."""
        if self.tile_type == "visualization" and self.visualization_id is None:
            raise ValueError("瓦片类型为 visualization 时必须提供 visualization_id")
        if self.tile_type == "kpi_card":
            cfg = self.config or {}
            missing = [k for k in sorted(KPI_TILE_REQUIRED_KEYS) if k not in cfg]
            if missing:
                raise ValueError(f"KPI 瓦片配置缺少必需项: {', '.join(missing)}")
        return self


# ── CRUD schemas ────────────────────────────────────────────────────────────


class DashboardCreate(BaseModel):
    """Request body for creating a dashboard."""

    name: str = Field(..., min_length=1, max_length=255, description="仪表盘名称")
    description: str | None = Field(None, description="仪表盘描述")
    layout_json: list[DashboardTile] = Field(default_factory=list, description="布局瓦片数组")


class DashboardUpdate(BaseModel):
    """Request body for updating a dashboard. All fields optional."""

    name: str | None = Field(None, min_length=1, max_length=255, description="仪表盘名称")
    description: str | None = Field(None, description="仪表盘描述")
    layout_json: list[DashboardTile] | None = Field(None, description="布局瓦片数组")


class DashboardResponse(BaseModel):
    """Response body for a single dashboard (full detail)."""

    id: uuid.UUID
    name: str
    description: str | None
    layout_json: list[dict[str, Any]]
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class DashboardListResponse(BaseModel):
    """Response body for dashboard listing (summary)."""

    id: uuid.UUID
    name: str
    description: str | None
    tile_count: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
