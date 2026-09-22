import datetime
import uuid

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

ROLE_USER = "user"
ROLE_ASSISTANT = "assistant"


class ChatMessage(Base):
    """A single message in a chat session.

    Assistant messages record which Q&A pair answered them (``matched_qa_id``),
    which phrasing produced the hit (``matched_variant_index``: 0 = canonical
    question, k>=1 = the k-th variant), and the cosine similarity that fired.
    """

    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, comment="主键ID"
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="所属会话ID",
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="角色: user/assistant"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False, comment="消息内容")
    matched_qa_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("qa_pairs.id", ondelete="SET NULL"),
        nullable=True,
        comment="命中的问答ID",
    )
    matched_variant_index: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="命中的问法索引（0=标准问题，k>=1=第k个相似问法）"
    )
    similarity_score: Mapped[float | None] = mapped_column(
        Float, nullable=True, comment="相似度分数"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), comment="创建时间"
    )
