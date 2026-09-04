"""Shared async HTTP client for the YKMMgmt backend.

Handles service-account login (cookie-based JWT) and transparent
re-login + retry on 401 so tool handlers can call backend endpoints
without touching auth themselves.
"""

import httpx


class BackendError(Exception):
    """A backend call failed (auth, HTTP status, or connectivity)."""


class BackendClient:
    """Thin authenticated wrapper around :class:`httpx.AsyncClient`."""

    def __init__(
        self,
        backend_url: str,
        username: str,
        password: str,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=backend_url,
            timeout=timeout,
            transport=transport,
        )
        self._username = username
        self._password = password
        self._logged_in = False

    async def __aenter__(self) -> "BackendClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def close(self) -> None:
        await self._client.aclose()

    @property
    def logged_in(self) -> bool:
        return self._logged_in

    async def login(self) -> None:
        """POST /api/auth/login and keep the auth cookies in the client jar."""
        resp = await self._client.post(
            "/api/auth/login",
            json={"username": self._username, "password": self._password},
        )
        if resp.status_code == 401:
            self._logged_in = False
            raise BackendError("服务账号登录失败：用户名或密码错误")
        if resp.status_code != 200:
            self._logged_in = False
            raise BackendError(f"服务账号登录失败: HTTP {resp.status_code}")
        self._logged_in = True

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
        json: dict | None = None,
    ) -> httpx.Response:
        """Send a request, logging in lazily and retrying once after a 401."""
        try:
            if not self._logged_in:
                await self.login()
            resp = await self._client.request(method, path, params=params, json=json)
            if resp.status_code == 401:
                # Access token may have expired — re-login and retry once
                await self.login()
                resp = await self._client.request(method, path, params=params, json=json)
            return resp
        except httpx.HTTPError as e:
            raise BackendError(f"无法连接后端服务 ({self._client.base_url}): {e}") from e

    async def get_json(self, path: str, *, params: dict | None = None):
        """GET a JSON endpoint; raise :class:`BackendError` on non-200."""
        resp = await self.request("GET", path, params=params)
        if resp.status_code != 200:
            raise BackendError(f"后端请求失败 {path} (HTTP {resp.status_code}): {_detail(resp)}")
        return resp.json()


def _detail(resp: httpx.Response) -> str:
    """Extract a human-readable reason from an error response body."""
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:200] if resp.text else ""
    detail = body.get("detail") if isinstance(body, dict) else None
    return str(detail) if detail else ""
