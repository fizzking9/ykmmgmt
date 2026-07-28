import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DataSource(Base):
    __tablename__ = "datasources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    name: Mapped[str] = mapped_column(String(255), nullable=False, comment="数据源名称")
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, comment="数据源类型（csv/excel）")
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="数据源配置（文件路径、分隔符、编码等）")
    schedule: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="调度计划（cron表达式，为空表示手动导入）"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
