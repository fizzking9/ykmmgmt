import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    source_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasources.id"), nullable=False, comment="数据源ID")
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending", comment="导入状态(pending/running/completed/failed)"
    )
    started_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="开始时间")
    finished_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True, comment="完成时间")
    row_count: Mapped[int] = mapped_column(Integer, default=0, comment="导入行数")
    error_count: Mapped[int] = mapped_column(Integer, default=0, comment="错误行数")
    rows_inserted: Mapped[int] = mapped_column(Integer, default=0, comment="新增行数")
    rows_updated: Mapped[int] = mapped_column(Integer, default=0, comment="更新行数")
    rows_skipped: Mapped[int] = mapped_column(Integer, default=0, comment="跳过行数")
    errors: Mapped[dict | None] = mapped_column(JSON, nullable=True, comment="错误详情")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), comment="创建时间")
