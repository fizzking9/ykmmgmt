from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ykmmgmt:ykmmgmt@127.0.0.1:15432/ykmmgmt"

    # ── Auth ──────────────────────────────────────────────────────────────
    # JWT signing key — override in production via .env
    secret_key: str = "dev-insecure-secret-key-change-me"
    access_token_expire_minutes: int = 120  # 2 hours
    refresh_token_expire_days: int = 7
    # Set Secure on auth cookies (enable behind HTTPS in production)
    cookie_secure: bool = False
    # Seed credentials for the initial root account (scripts/seed_root.py).
    # No defaults — the seeder refuses to run without them.
    root_username: str | None = None
    root_password: str | None = None

    # ── Semantic Q&A chat widget ──────────────────────────────────────────
    # Bootstrap encoder, used until the knowledge base carries vectors of its own;
    # admins switch it on 问答管理 (see app/services/embedding_models.py), which
    # rebuilds every stored embedding in the same action.
    embedding_model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"
    # Weights are pre-baked into the image (Dockerfile), so loading stays offline by
    # default. Reaching for huggingface.co on a blocked network makes every retry
    # back off for minutes and stalls the first encode after startup — set
    # YKM_EMBEDDING_ALLOW_DOWNLOAD=true only when you intend to fetch a new model.
    embedding_allow_download: bool = Field(
        default=False,
        validation_alias=AliasChoices("embedding_allow_download", "YKM_EMBEDDING_ALLOW_DOWNLOAD"),
    )
    # Minimum cosine similarity to accept a match; below → friendly fallback.
    # Tuned via scripts/tune_chat_threshold.py (highest recall at precision >= 0.95).
    # 0.79 holds after seeding 9 more 相似问法 only because app/services/time_window.py
    # refuses a match whose calendar window contradicts the question: on the seeded KB
    # that combination measures precision 1.000 / recall 0.767, versus 0.500 recall if
    # the guard were replaced by pushing this value to 0.89. Re-tune after every change
    # to the KB or the encoder.
    # The YKM_-prefixed name is what .env.example documents and what an init system
    # exports, so bind it explicitly — a plain field name silently ignored it and the
    # tuned value never took effect.
    chat_similarity_threshold: float = Field(
        default=0.79,
        validation_alias=AliasChoices("chat_similarity_threshold", "YKM_CHAT_SIMILARITY_THRESHOLD"),
    )
    # Width below the threshold that still counts as a "near miss" in the ask log.
    chat_log_near_threshold_window: float = 0.10

    # Look in the backend dir first, then the repo root — the project keeps
    # its .env at the repo root while servers/tests run from backend/
    # extra="ignore": the root .env also carries MCP keys (YKM_*) that the
    # backend doesn't consume — they must not fail validation.
    model_config = {
        "env_file": (".env", "../../.env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
