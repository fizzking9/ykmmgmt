"""HTTP transport tests: the API-key guard and the download file route.

MCP requests without a valid ``Authorization: Bearer <key>`` header are
rejected with 401 before any MCP method runs. Download URLs under
``/mcp/files/`` skip the Bearer guard and authenticate with their HMAC
token instead — they must work in a plain browser.
"""

from dataclasses import replace

import httpx2
from http_support import SETTINGS, backend_transport
from mcp_server import files
from mcp_server.http_app import build_http_app

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 200

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


# ── Download file route (token-authenticated, no Bearer header) ──────────


def _seed_file(app) -> str:
    """Store one PNG in the app's file store; returns its download URL."""
    store = files.default_store()
    batch_id, batch_dir = store.create_batch()
    (batch_dir / "报表.png").write_bytes(PNG_BYTES)
    return store.build_url("", batch_id, "报表.png")


async def _get(app, path: str) -> httpx2.Response:
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app)) as client:
        return await client.get(f"http://testserver{path}")


async def test_download_with_valid_token_serves_file_without_bearer():
    app = _app()
    url = _seed_file(app)
    resp = await _get(app, url)  # no Authorization header at all
    assert resp.status_code == 200
    assert resp.content == PNG_BYTES
    assert resp.headers["content-type"].startswith("image/png")
    assert "attachment" in resp.headers.get("content-disposition", "")


async def test_download_with_wrong_token_rejected():
    app = _app()
    url = _seed_file(app).replace("token=", "token=ffff")
    resp = await _get(app, url)
    assert resp.status_code == 403


async def test_download_without_token_rejected():
    app = _app()
    url = _seed_file(app).split("?")[0]
    resp = await _get(app, url)
    assert resp.status_code == 403


async def test_download_with_expired_timestamp_rejected():
    import time

    app = _app()
    store = files.default_store()
    batch_id, batch_dir = store.create_batch()
    (batch_dir / "报表.png").write_bytes(PNG_BYTES)
    old_ts = int(time.time()) - settings_ttl(app) - 10
    url = f"/mcp/files/{batch_id}/报表.png?ts={old_ts}&token={store._sign(old_ts, batch_id, '报表.png')}"
    resp = await _get(app, url)
    assert resp.status_code == 403


def settings_ttl(app) -> int:
    return files.default_store().ttl


async def test_download_valid_token_but_missing_file_404():
    app = _app()
    store = files.default_store()
    batch_id, _ = store.create_batch()
    url = store.build_url("", batch_id, "ghost.png")
    resp = await _get(app, url)
    assert resp.status_code == 404


async def test_download_path_traversal_rejected():
    app = _app()
    store = files.default_store()
    batch_id, _ = store.create_batch()
    # A signed-looking URL for a traversal filename cannot exist (the token
    # binds the filename), but the route must reject it regardless
    url = f"/mcp/files/{batch_id}/..%2F..%2Fsecret?ts=1&token=x"
    resp = await _get(app, url)
    assert resp.status_code in (403, 404)
