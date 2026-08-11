import datetime
import uuid

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Dashboard(Base):
    __tablename__ = "dashboards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="主键ID"
    )
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, comment="仪表盘名称"
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="仪表盘描述"
    )
    layout_json: Mapped[list] = mapped_column(
        JSONB, nullable=False, comment="布局配置（瓦片对象数组，JSON）"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
