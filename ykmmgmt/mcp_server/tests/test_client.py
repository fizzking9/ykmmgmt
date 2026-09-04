"""Tests for the shared backend HTTP client (login, refresh, error handling)."""

import httpx
import pytest
from mcp_server.client import BackendClient, BackendError


def _client(handler, **kwargs) -> BackendClient:
    return BackendClient(
        "http://backend.test",
        "svc",
        "svc-pass",
        transport=httpx.MockTransport(handler),
        **kwargs,
    )


def _ok_login(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, headers={"set-cookie": "access_token=tok; Path=/"})


# ── Login ────────────────────────────────────────────────────────────────────


async def test_lazy_login_on_first_request():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, str(request.url.path)))
        if request.url.path == "/api/auth/login":
            return _ok_login(request)
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as client:
        assert not client.logged_in
        resp = await client.request("GET", "/api/things")
        assert resp.status_code == 200
        assert client.logged_in

    # Login happens exactly once, before the actual request
    assert calls == [("POST", "/api/auth/login"), ("GET", "/api/things")]


async def test_login_bad_credentials_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": "用户名或密码错误"})

    async with _client(handler) as client:
        with pytest.raises(BackendError, match="用户名或密码错误"):
            await client.request("GET", "/api/things")
        assert not client.logged_in


async def test_login_non_200_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    async with _client(handler) as client:
        with pytest.raises(BackendError, match="HTTP 500"):
            await client.request("GET", "/api/things")


# ── Token refresh ────────────────────────────────────────────────────────────


async def test_request_retries_once_after_401():
    calls: list[str] = []
    state = {"logged_in": False, "expire_after_login": False}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        if path == "/api/auth/login":
            state["logged_in"] = True
            return _ok_login(request)
        # Simulate token expiry: reject once, then accept after re-login
        if path == "/api/things" and not state["expire_after_login"]:
            state["expire_after_login"] = True
            state["logged_in"] = False
            return httpx.Response(401, json={"detail": "未登录或登录已过期"})
        return httpx.Response(200, json={"ok": True})

    async with _client(handler) as client:
        resp = await client.request("GET", "/api/things")
        assert resp.status_code == 200
        assert client.logged_in

    assert calls == [
        "/api/auth/login",
        "/api/things",
        "/api/auth/login",  # re-login after the 401
        "/api/things",  # retried request
    ]


async def test_get_json_raises_on_error_status_with_detail():
    def handler_full(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return _ok_login(request)
        return httpx.Response(422, json={"detail": "仅表格类可视化支持 CSV 导出"})

    async with _client(handler_full) as client:
        with pytest.raises(BackendError, match="仅表格类可视化支持"):
            await client.get_json("/api/visualizations/x/export")


async def test_get_json_returns_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/auth/login":
            return _ok_login(request)
        return httpx.Response(200, json=[{"id": "a"}])

    async with _client(handler) as client:
        data = await client.get_json("/api/visualizations")
        assert data == [{"id": "a"}]


# ── Connectivity ─────────────────────────────────────────────────────────────


async def test_connection_error_becomes_backend_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    async with _client(handler) as client:
        with pytest.raises(BackendError, match="无法连接后端服务"):
            await client.request("GET", "/api/visualizations")
