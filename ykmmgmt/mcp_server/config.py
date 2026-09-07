"""Environment variable loading for the MCP server."""

import os
import tempfile
from dataclasses import dataclass

DEFAULT_BACKEND_URL = "http://localhost:8000"
DEFAULT_MCP_HOST = "0.0.0.0"
DEFAULT_MCP_PORT = 8001
DEFAULT_DOWNLOAD_TTL = 86400  # download URLs stay valid for 24 hours


def _default_files_dir() -> str:
    return os.path.join(tempfile.gettempdir(), "ykmmgmt-files")


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
    # Base URL used to build absolute download links for exported files
    # (e.g. "http://<cloud-ip>/mcp"); empty → relative paths are returned.
    public_url: str = ""
    # Root directory for exported files awaiting download
    files_dir: str = ""
    download_ttl: int = DEFAULT_DOWNLOAD_TTL


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
        public_url=os.environ.get("YKM_MCP_PUBLIC_URL", "").rstrip("/"),
        files_dir=os.environ.get("YKM_MCP_FILES_DIR") or _default_files_dir(),
        download_ttl=int(os.environ.get("YKM_MCP_DOWNLOAD_TTL", DEFAULT_DOWNLOAD_TTL)),
    )
