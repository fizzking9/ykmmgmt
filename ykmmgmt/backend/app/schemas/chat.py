"""Pydantic schemas for the Q&A chat feature (admin CRUD + chat runtime)."""

import datetime
import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Soft cap on variants (see requirements "Variant list length"); the DB stores
# JSONB with no hard limit — this bound just keeps embedding cost sane.
MAX_VARIANTS = 50


def _normalize_variant_list(value: list[str]) -> list[str]:
    """Trim each phrasing and drop blanks; order is preserved (server aligns
    embeddings to [question, *variants] positionally)."""
    cleaned = [s.strip() for s in value if s and s.strip()]
    if len(cleaned) > MAX_VARIANTS:
        raise ValueError(f"相似问法数量不能超过 {MAX_VARIANTS} 个")
    return cleaned


# ── Admin CRUD ──────────────────────────────────────────────────────────────


class QAPairCreate(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000, description="标准问题")
    question_variants: list[str] = Field(default_factory=list, description="相似问法列表")
    answer: str = Field(..., min_length=1, description="答案（Markdown）")
    category: str | None = Field(None, max_length=100, description="分类")
    is_active: bool = Field(True, description="是否启用")

    @field_validator("question")
    @classmethod
    def _strip_question(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("标准问题不能为空")
        return v

    @field_validator("question_variants")
    @classmethod
    def _clean_variants(cls, v: list[str]) -> list[str]:
        return _normalize_variant_list(v)


class QAPairUpdate(BaseModel):
    """Partial update; embeddings are recomputed whenever question/variants change."""

    question: str | None = Field(None, min_length=1, max_length=2000, description="标准问题")
    question_variants: list[str] | None = Field(None, description="相似问法列表")
    answer: str | None = Field(None, min_length=1, description="答案（Markdown）")
    category: str | None = Field(None, max_length=100, description="分类")
    is_active: bool | None = Field(None, description="是否启用")

    @field_validator("question_variants")
    @classmethod
    def _clean_variants(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _normalize_variant_list(v)


class QAPairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    question_variants: list[str]
    answer: str
    category: str | None
    is_active: bool
    has_embeddings: bool = Field(description="向量是否已生成")
    embedding_model: str | None = Field(None, description="向量所属模型（None 或不等当前模型 → 待重建）")
    needs_rebuild: bool = Field(description="该条向量是否需按当前模型重建")
    variant_count: int = Field(description="相似问法数量")
    created_at: datetime.datetime
    updated_at: datetime.datetime


class QAPairPage(BaseModel):
    items: list[QAPairResponse]
    total: int
    page: int
    size: int


class RebuildResult(BaseModel):
    rebuilt: int = Field(description="重新计算向量的问答条目数")
    model_name: str = Field(description="所用向量模型")


# ── Encoder selection ───────────────────────────────────────────────────────


class EmbeddingModelOptionResponse(BaseModel):
    name: str = Field(description="向量模型标识（写入 .env / 服务器权重目录）")
    label: str = Field(description="中文显示名")
    dims: int = Field(description="向量维度")
    note: str = Field(description="选型说明（体积/延迟/许可等权衡）")


class EmbeddingModelListResponse(BaseModel):
    items: list[EmbeddingModelOptionResponse] = Field(description="候选向量模型（按横评推荐度排序）")
    active_model: str = Field(description="当前生效的向量模型")
    active_label: str = Field(description="当前模型中文名")
    threshold: float = Field(description="当前相似度阈值")
    needs_rebuild: int = Field(description="向量不属于当前模型、需重建的条目数")


class ActivateEmbeddingModelRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=200, description="候选模型标识")


# ── Chat runtime ──────────────────────────────────────────────────────────────


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    session_id: uuid.UUID | None = Field(None, description="会话ID；缺省则新建会话")

    @field_validator("message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("问题内容不能为空")
        return v


class AskResponse(BaseModel):
    answer: str = Field(description="答案（Markdown）或无匹配时的友好提示")
    session_id: uuid.UUID
    matched_question: str | None = Field(None, description="命中的标准问题")
    matched_variant_index: int | None = Field(None, description="命中问法索引（0=标准问题）")
    similarity_score: float | None = Field(None, description="相似度分数")
    matched: bool = Field(description="是否命中知识库")


class SessionResponse(BaseModel):
    id: uuid.UUID
    created_at: datetime.datetime
    last_active_at: datetime.datetime


class ChatMessageResponse(BaseModel):
    id: uuid.UUID
    role: str
    content: str
    matched_qa_id: uuid.UUID | None
    matched_variant_index: int | None
    similarity_score: float | None
    created_at: datetime.datetime


class ChatMessagePage(BaseModel):
    items: list[ChatMessageResponse]
    total: int
    page: int
    size: int
