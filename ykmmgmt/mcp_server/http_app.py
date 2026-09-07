"""Streamable-HTTP ASGI app — the MCP server's network transport.

Wraps the low-level :class:`~mcp.server.Server` built by ``server.py`` in the
SDK's ``StreamableHTTPSessionManager`` and mounts it at ``/mcp`` behind an
API-key guard: requests without a valid ``Authorization: Bearer <key>``
header are rejected with 401 before any MCP method runs.

Exported files are served at ``/mcp/files/{batch}/{name}`` — these requests
skip the Bearer guard and authenticate with the HMAC ``token`` query
parameter embedded in each download URL instead (a browser cannot send
Authorization headers, and the link must stay shareable-but-unforgeable).

The app is stateless (a fresh transport per request) and answers with plain
JSON responses — both choices keep it robust behind the frp tunnel, where
long-lived SSE streams and sticky sessions would be fragile.
"""

import contextlib
import mimetypes
import secrets
from collections.abc import AsyncIterator
from pathlib import Path

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server import files
from mcp_server.config import Settings, _default_files_dir, load_settings
from mcp_server.server import build_server

MCP_PATH = "/mcp"
FILES_PREFIX = "/mcp/files/"


class _MCPASGIHandler:
    """Raw-ASGI adapter so the session manager is routed without redirects.

    A ``Mount("/mcp")`` would 307-redirect exact ``/mcp`` requests to
    ``/mcp/`` — MCP clients may not follow that, so the endpoint is routed
    exactly with a ``Route`` wrapping this class (class endpoints are raw
    ASGI in Starlette).
    """

    def __init__(self, handle_request):
        self._handle_request = handle_request

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self._handle_request(scope, receive, send)


class APIKeyMiddleware:
    """Reject HTTP requests that lack the configured Bearer API key.

    Download URLs under ``/mcp/files/`` are exempt — they authenticate
    with their own HMAC token (verified in the route handler).
    """

    def __init__(self, app: ASGIApp, api_key: str):
        self.app = app
        self.api_key = api_key

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and not self._authorized(scope):
            response = JSONResponse({"detail": "无效或缺失的 API 密钥"}, status_code=401)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)

    def _authorized(self, scope: Scope) -> bool:
        if scope.get("path", "").startswith(FILES_PREFIX):
            return True  # token-authenticated in the download handler
        # An unconfigured key rejects everything — an open MCP endpoint must
        # never be reachable by accident.
        if not self.api_key:
            return False
        auth = next(
            (v.decode("latin-1") for k, v in scope.get("headers", []) if k == b"authorization"),
            "",
        )
        scheme, _, token = auth.partition(" ")
        return scheme.lower() == "bearer" and secrets.compare_digest(token, self.api_key)


def build_http_app(
    settings: Settings | None = None,
    *,
    transport=None,
) -> Starlette:
    """Assemble the Starlette app serving the MCP endpoint at ``/mcp``.

    ``settings``/``transport`` are injection points for tests; production
    reads environment variables and talks to the real backend over HTTP.
    """
    settings = settings or load_settings()
    server = build_server(settings, transport=transport)
    # One store for the whole process, keyed by the injected settings —
    # download URLs are signed with the same API key that guards /mcp.
    store = files.FileStore(
        Path(settings.files_dir or _default_files_dir()),
        settings.api_key,
        settings.download_ttl,
    )
    files.set_default_store(store)
    session_manager = StreamableHTTPSessionManager(
        app=server,
        stateless=True,
        json_response=True,
    )
    mcp_handler = _MCPASGIHandler(session_manager.handle_request)

    async def download(request) -> FileResponse | JSONResponse:
        """Serve one exported file after verifying its signed URL."""
        batch_id = request.path_params["batch_id"]
        filename = request.path_params["filename"]
        query = request.query_params
        if not store.verify(batch_id, filename, query.get("ts"), query.get("token")):
            return JSONResponse({"detail": "下载链接无效或已过期"}, status_code=403)
        path = store.file_path(batch_id, filename)
        if path is None:
            return JSONResponse({"detail": "文件不存在或已过期"}, status_code=404)
        media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return FileResponse(path, media_type=media_type, filename=filename)

    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        # The session manager needs its task group running for the whole
        # life of the app — uvicorn enters this on startup, exits on stop.
        async with session_manager.run():
            yield

    return Starlette(
        # Both "/mcp" and "/mcp/" answer — clients are configured either way.
        # The files route is registered first so the session manager never
        # sees download requests.
        routes=[
            Route(FILES_PREFIX + "{batch_id}/{filename}", download, methods=["GET"]),
            *[
                Route(path, mcp_handler, methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
                for path in (MCP_PATH, MCP_PATH + "/")
            ],
        ],
        lifespan=lifespan,
        middleware=[Middleware(APIKeyMiddleware, api_key=settings.api_key)],
    )
