import datetime
import uuid

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class QAPair(Base):
    """A curated Q&A entry backing the semantic FAQ assistant.

    ``embeddings`` is a parallel array aligned with ``[question, *question_variants]``
    — index 0 is the canonical question, indices 1..N are the variants — so a
    user message can be matched against every phrasing that resolves to this
    single ``answer``.
    """

    __tablename__ = "qa_pairs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="主键ID"
    )
    question: Mapped[str] = mapped_column(Text, nullable=False, comment="标准问题")
    question_variants: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        comment="相似问法列表（与 embeddings[1:] 对齐）",
    )
    answer: Mapped[str] = mapped_column(Text, nullable=False, comment="答案（Markdown）")
    embeddings: Mapped[list | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="向量数组，与 [question, *question_variants] 位置对齐",
    )
    embedding_model: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="生成 embeddings 的向量模型（NULL 或不等当前模型 → 待重建）",
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="分类")
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true", comment="是否启用"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), comment="更新时间"
    )
