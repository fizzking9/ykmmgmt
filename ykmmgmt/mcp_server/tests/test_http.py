"""HTTP transport tests: the API-key guard on the MCP endpoint.

Requests without a valid ``Authorization: Bearer <key>`` header are
rejected with 401 before any MCP method runs.
"""

from dataclasses import replace

import httpx2
from http_support import SETTINGS, backend_transport
from mcp_server.http_app import build_http_app

# A JSON-RPC initialize request — enough body to look like an MCP client;
# the guard must reject it before the session manager ever sees it.
INITIALIZE_BODY = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "pytest", "version": "0"},
    },
}


async def _post(app, headers: dict | None = None):
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as client:
        return await client.post(
            "http://testserver/mcp",
            json=INITIALIZE_BODY,
            headers=headers or {},
        )


def _app(api_key: str = SETTINGS.api_key):
    return build_http_app(
        replace(SETTINGS, api_key=api_key),
        transport=backend_transport(),
    )


async def test_missing_api_key_rejected_with_401():
    resp = await _post(_app())
    assert resp.status_code == 401
    assert "API 密钥" in resp.json()["detail"]


async def test_invalid_api_key_rejected_with_401():
    resp = await _post(_app(), headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 401


async def test_non_bearer_scheme_rejected_with_401():
    resp = await _post(_app(), headers={"Authorization": f"Basic {SETTINGS.api_key}"})
    assert resp.status_code == 401


async def test_unconfigured_api_key_rejects_everything():
    # An empty YKM_MCP_API_KEY must never leave the endpoint open
    resp = await _post(_app(api_key=""), headers={"Authorization": "Bearer anything"})
    assert resp.status_code == 401
