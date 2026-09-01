"""Profile self-service tests — PUT /api/auth/profile (username & password)."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.user import User
from app.services.auth import create_access_token, hash_password
from main import app
from tests.conftest import TEST_ACCOUNTS, _ensure_test_users

PROFILE_USERNAME = "test__profile"
PROFILE_PASSWORD = "ProfilePass123"


async def _profile_user_id() -> int:
    """Ensure a dedicated account exists with known credentials (idempotent)."""
    async with async_session_factory() as session:
        result = await session.execute(select(User).where(User.username == PROFILE_USERNAME))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(
                username=PROFILE_USERNAME,
                password_hash=hash_password(PROFILE_PASSWORD),
                role="user",
                is_active=True,
            )
        else:
            # Reset credentials so tests do not depend on execution order
            user.password_hash = hash_password(PROFILE_PASSWORD)
            user.is_active = True
        session.add(user)
        await session.flush()
        user_id = user.id
        await session.commit()
    return user_id


def _profile_cookies(user_id: int) -> dict[str, str]:
    return {"access_token": create_access_token(user_id)}


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestUpdateProfile:
    async def test_change_username(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"username": "test__profile_renamed"},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == "test__profile_renamed"

        # /me reflects the new username immediately
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
            cookies=_profile_cookies(user_id),
        ) as client:
            me = await client.get("/api/auth/me")
        assert me.status_code == 200
        assert me.json()["username"] == "test__profile_renamed"

    async def test_change_password_then_relogin(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={
                    "current_password": PROFILE_PASSWORD,
                    "new_password": "NewProfilePass456",
                },
            )
        assert resp.status_code == 200, resp.text

        # Old password no longer works, new one does
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            old = await client.post(
                "/api/auth/login",
                json={"username": PROFILE_USERNAME, "password": PROFILE_PASSWORD},
            )
            new = await client.post(
                "/api/auth/login",
                json={"username": PROFILE_USERNAME, "password": "NewProfilePass456"},
            )
        assert old.status_code == 401
        assert new.status_code == 200, new.text

    async def test_wrong_current_password_rejected(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"current_password": "wrong-pass", "new_password": "NewProfilePass456"},
            )
        assert resp.status_code == 400
        assert resp.json()["detail"] == "当前密码不正确"

    async def test_password_change_without_current_password_rejected(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"new_password": "NewProfilePass456"},
            )
        assert resp.status_code == 422

    async def test_duplicate_username_rejected(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"username": TEST_ACCOUNTS["admin"]["username"]},
            )
        assert resp.status_code == 409

    async def test_no_change_fields_rejected(self):
        """username and new_password both absent → validation error."""
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"current_password": PROFILE_PASSWORD},
            )
            assert resp.status_code == 422

            # Username-only requests must NOT require the current password
            ok = await client.put(
                "/api/auth/profile",
                json={"current_password": PROFILE_PASSWORD, "username": "test__profile"},
            )
            assert ok.status_code == 200

    async def test_short_password_rejected(self):
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"current_password": PROFILE_PASSWORD, "new_password": "short"},
            )
        assert resp.status_code == 422

    async def test_requires_auth(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"current_password": "x", "username": "someone"},
            )
        assert resp.status_code == 401

    async def test_same_username_is_noop(self):
        """Submitting the current username unchanged should succeed without
        touching the uniqueness check."""
        _ensure_test_users()
        user_id = await _profile_user_id()

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", cookies=_profile_cookies(user_id)
        ) as client:
            resp = await client.put(
                "/api/auth/profile",
                json={"username": PROFILE_USERNAME},
            )
        assert resp.status_code == 200, resp.text
        assert resp.json()["username"] == PROFILE_USERNAME
