"""Environment variable loading for the MCP server."""

import os
from dataclasses import dataclass

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 8001


@dataclass(frozen=True)
class Settings:
    """Runtime configuration, sourced from environment variables."""

    backend_url: str
    service_username: str
    service_password: str
    # Empty by default so tool-level unit tests can construct Settings
    # without it; the HTTP layer refuses to serve (and the entrypoint refuses
    # to start) when the API key is missing.
    api_key: str = ""
    host: str = DEFAULT_MCP_HOST
    port: int = DEFAULT_MCP_PORT


def load_settings() -> Settings:
    """Read YKM_* environment variables into a Settings instance.

    Credentials are never hardcoded — the service account comes from the
    deployment environment (``YKM_SERVICE_USERNAME`` /
    ``YKM_SERVICE_PASSWORD``), and ``YKM_MCP_API_KEY`` guards the MCP
    endpoint itself.
    """
    return Settings(
        backend_url=os.environ.get("YKM_BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/"),
        service_username=os.environ.get("YKM_SERVICE_USERNAME", ""),
        service_password=os.environ.get("YKM_SERVICE_PASSWORD", ""),
        api_key=os.environ.get("YKM_MCP_API_KEY", ""),
        host=os.environ.get("YKM_MCP_HOST", DEFAULT_MCP_HOST),
        port=int(os.environ.get("YKM_MCP_PORT", DEFAULT_MCP_PORT)),
    )
