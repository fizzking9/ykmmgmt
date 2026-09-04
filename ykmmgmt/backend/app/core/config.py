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
