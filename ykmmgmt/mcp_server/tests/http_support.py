"""Shared helpers for streamable-HTTP integration tests.

Builds the real ASGI app (API-key middleware + streamable-HTTP session
manager) around a mocked backend, then drives it with a real MCP
``ClientSession`` over an in-process ``httpx2`` ASGI transport — the same
code path an external agent uses against ``http://<host>:8001/mcp``.
"""

import contextlib
from collections.abc import AsyncIterator
from dataclasses import replace

import httpx
import httpx2
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp_server.config import Settings
from mcp_server.http_app import build_http_app

API_KEY = "test-api-key"

SETTINGS = Settings(
    backend_url="http://backend.test",
    service_username="svc",
    service_password="svc-pass",
    api_key=API_KEY,
)

TABLE_VIZ = {"id": "id-table", "name": "退款明细表", "chart_type": "table"}
BAR_VIZ = {"id": "id-bar", "name": "月度柱状图", "chart_type": "bar"}

TABLE_CSV = "\ufeff订单号,金额\nA001,100.5\nA002,200\n"

BAR_DATA = {
    "columns": ["月份", "金额"],
    "rows": [{"月份": "2026-06", "金额": 100}, {"月份": "2026-07", "金额": 200}],
    "chart_type": "bar",
    "config_json": {"x_column": "月份", "y_columns": ["金额"]},
    "column_types": {"月份": "date", "金额": "number"},
}

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def backend_transport(login_status: int = 200) -> httpx.MockTransport:
    """Mock YKMMgmt backend: login + one table viz + one bar viz."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/auth/login":
            if login_status != 200:
                return httpx.Response(login_status, json={"detail": "用户名或密码错误"})
            return httpx.Response(200, headers={"set-cookie": "access_token=tok; Path=/"})
        if path == "/api/visualizations":
            return httpx.Response(200, json=[TABLE_VIZ, BAR_VIZ])
        if path == "/api/visualizations/id-table/export":
            return httpx.Response(
                200,
                content=TABLE_CSV.encode("utf-8"),
                headers={"content-type": "text/csv; charset=utf-8"},
            )
        if path == "/api/visualizations/id-bar/data":
            return httpx.Response(200, json=BAR_DATA)
        return httpx.Response(404, json={"detail": "not found"})

    return httpx.MockTransport(handler)


@contextlib.asynccontextmanager
async def mcp_http_session(
    *,
    api_key: str = API_KEY,
    login_status: int = 200,
) -> AsyncIterator[ClientSession]:
    """A ClientSession wired to the MCP server over in-process streamable HTTP.

    Entered inside each test (not a fixture): anyio cancel scopes must not
    span pytest fixture setup/teardown, which run in different tasks.
    """
    settings = replace(SETTINGS, api_key=api_key)
    app = build_http_app(settings, transport=backend_transport(login_status))
    async with app.router.lifespan_context(app):
        http_client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            headers={"Authorization": f"Bearer {api_key}"},
        )
        async with http_client:
            async with streamable_http_client(
                "http://testserver/mcp", http_client=http_client
            ) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    yield session
