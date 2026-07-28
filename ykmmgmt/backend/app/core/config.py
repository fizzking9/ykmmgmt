from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://ykmmgmt:ykmmgmt@localhost:5432/ykmmgmt"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
