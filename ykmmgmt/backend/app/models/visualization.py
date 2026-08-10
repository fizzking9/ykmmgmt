import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Visualization(Base):
    __tablename__ = "visualizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="主键ID"
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="可视化名称")
    view_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("views.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联视图ID",
    )
    chart_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="图表类型（table/kpi_card/bar/line/pie/scatter）"
    )
    config_json: Mapped[dict] = mapped_column(JSONB, nullable=False, comment="图表配置（JSON）")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
