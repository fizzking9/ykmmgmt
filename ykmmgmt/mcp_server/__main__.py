"""Entry point — start the MCP server on streamable HTTP.

Two ways to launch:

- Dev, from the repo: ``cd ykmmgmt && python -m mcp_server``
- Installed: the ``ykmmgmt-mcp`` console script (any working directory)

``YKM_MCP_API_KEY`` is required — without it the endpoint would be
unauthenticated, so startup refuses to continue.
"""

import uvicorn

from mcp_server.config import load_settings
from mcp_server.http_app import build_http_app


def cli() -> None:
    """Entry point for ``python -m mcp_server`` and the console script."""
    settings = load_settings()
    if not settings.api_key:
        raise SystemExit("YKM_MCP_API_KEY 未设置 — 拒绝启动未鉴权的 MCP 服务")
    app = build_http_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port)


if __name__ == "__main__":
    cli()
