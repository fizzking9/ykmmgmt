from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TableMeta(Base):
    """Table-level ingestion settings for Schema-Manager tables.

    upsert_key stores the comma-joined column names the import engine
    matches incoming rows against (empty/NULL = fall back to the user
    primary key). dedup_enabled only matters for tables with no upsert
    key and no primary key: enabled = identical rows are skipped via the
    content_hash mechanism, disabled = every row is inserted.
    """

    __tablename__ = "table_meta"

    table_name: Mapped[str] = mapped_column(String(100), primary_key=True, comment="数据表英文名")
    upsert_key: Mapped[str | None] = mapped_column(
        String(400), nullable=True, comment="Upsert 键列名（逗号分隔，空表示默认主键）"
    )
    dedup_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, comment="是否启用去重")
