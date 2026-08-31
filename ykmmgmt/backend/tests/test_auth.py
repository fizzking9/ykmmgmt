"""Auth API tests — login, /me, refresh, logout, and password hashing."""

import datetime as dt

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt

from app.core.config import settings
from app.models.user import User
from app.services.auth import (
    ACCESS_TOKEN_TYPE,
    create_access_token,
    hash_password,
    verify_password,
)
from main import app
from tests.conftest import TEST_ACCOUNTS, _ensure_test_users


def _expired_access_token(user_id: int) -> str:
    now = dt.datetime.now(dt.UTC)
    payload = {"sub": str(user_id), "type": ACCESS_TOKEN_TYPE, "iat": now, "exp": now - dt.timedelta(minutes=1)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestPasswordHashing:
    def test_hash_and_verify_round_trip(self):
        hashed = hash_password("s3cret-password")
        assert hashed != "s3cret-password"
        assert verify_password("s3cret-password", hashed)
        assert not verify_password("wrong-password", hashed)

    def test_hash_is_salted(self):
        assert hash_password("same") != hash_password("same")


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestLogin:
    async def test_login_success_sets_cookies(self):
        _ensure_test_users()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post(
                "/api/auth/login",
                json={
                    "username": TEST_ACCOUNTS["root"]["username"],
                    "password": TEST_ACCOUNTS["root"]["password"],
                },
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["username"] == TEST_ACCOUNTS["root"]["username"]
        assert body["role"] == "root"
        # httpOnly auth cookies are set
        set_cookies = "; ".join(resp.headers.get_list("set-cookie"))
        assert "access_token=" in set_cookies
        assert "refresh_token=" in set_cookies

    async def test_login_wrong_password(self):
        _ensure_test_users()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post(
                "/api/auth/login",
                json={"username": TEST_ACCOUNTS["root"]["username"], "password": "nope"},
            )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "用户名或密码错误"

    async def test_login_unknown_user(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post(
                "/api/auth/login",
                json={"username": "ghost_user", "password": "whatever"},
            )
        assert resp.status_code == 401

    async def test_login_deactivated_user(self):
        from sqlalchemy import select

        from app.core.database import async_session_factory

        _ensure_test_users()

        # Create + deactivate a dedicated user for this test
        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == "test__deactivated"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    username="test__deactivated",
                    password_hash=hash_password("Deactivated123"),
                    role="user",
                    is_active=False,
                )
                session.add(user)
            else:
                user.is_active = False
            await session.commit()
            username = user.username

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post(
                "/api/auth/login",
                json={"username": username, "password": "Deactivated123"},
            )
        assert resp.status_code == 401


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestMe:
    async def test_me_with_valid_token(self):
        _ensure_test_users()
        from tests.conftest import auth_cookies

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.get("/api/auth/me")
        assert resp.status_code == 200
        assert resp.json()["username"] == TEST_ACCOUNTS["admin"]["username"]
        assert resp.json()["role"] == "admin"

    async def test_me_with_missing_token(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_with_expired_token(self):
        _ensure_test_users()
        from tests.conftest import _auth_state

        expired = _expired_access_token(_auth_state["root"]["id"])
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies={"access_token": expired}
        ) as client:
            resp = await client.get("/api/auth/me")
        assert resp.status_code == 401


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestRefresh:
    async def test_refresh_rotates_tokens(self):
        _ensure_test_users()
        from tests.conftest import auth_cookies

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            # Simulate an expired access token — refresh should still work
            client.cookies.set("access_token", _expired_access_token(999999))
            resp = await client.post("/api/auth/refresh")

        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == TEST_ACCOUNTS["user"]["username"]
        set_cookies = "; ".join(resp.headers.get_list("set-cookie"))
        assert "access_token=" in set_cookies
        assert "refresh_token=" in set_cookies

    async def test_refresh_without_cookie(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401

    async def test_access_token_rejected_as_refresh_token(self):
        _ensure_test_users()
        from tests.conftest import auth_cookies

        transport = ASGITransport(app=app)
        cookies = auth_cookies("user")
        # Only send the access token — the refresh endpoint must reject it
        cookies.pop("refresh_token")
        async with AsyncClient(transport=transport, base_url="http://test", cookies=cookies) as client:
            resp = await client.post("/api/auth/refresh")
        assert resp.status_code == 401


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestLogout:
    async def test_logout_clears_cookies(self):
        _ensure_test_users()
        from tests.conftest import auth_cookies

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200
        set_cookies = "; ".join(resp.headers.get_list("set-cookie"))
        # Both cookies are cleared (empty values / max-age=0)
        assert "access_token=" in set_cookies
        assert "refresh_token=" in set_cookies


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestTokenHelpers:
    async def test_deactivated_user_token_rejected(self):
        """Tokens of a user deactivated after issuance stop working."""
        from sqlalchemy import select

        from app.core.database import async_session_factory

        _ensure_test_users()

        async with async_session_factory() as session:
            result = await session.execute(select(User).where(User.username == "test__lapsed"))
            user = result.scalar_one_or_none()
            if user is None:
                user = User(
                    username="test__lapsed",
                    password_hash=hash_password("LapsedPass123"),
                    role="user",
                    is_active=True,
                )
                session.add(user)
                await session.flush()
            token = create_access_token(user.id)
            user.is_active = False
            await session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={"access_token": token}) as client:
            resp = await client.get("/api/auth/me")
        assert resp.status_code == 401
