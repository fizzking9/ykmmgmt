from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ColumnMeta(Base):
    """User-facing metadata for Schema-Manager table columns.

    Stores the free-form description and the user-specified default value
    (as entered in the UI). The actual DDL default lives on the table
    itself; this record keeps the original text for display and editing.
    """

    __tablename__ = "column_meta"

    table_name: Mapped[str] = mapped_column(String(100), primary_key=True, comment="数据表英文名")
    column_name: Mapped[str] = mapped_column(String(100), primary_key=True, comment="列英文名")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="列描述")
    default_value: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="默认值（用户输入原文）")
