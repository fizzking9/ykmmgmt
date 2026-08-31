"""User management API tests — hierarchy enforcement."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.models.user import User
from main import app
from tests.conftest import TEST_ACCOUNTS, _ensure_test_users, anonymous_cookies, auth_cookies

PREFIX = "test__u_"


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    """Remove users created by this module (never the shared test accounts).

    Uses a throwaway engine in its own event loop so teardown never leaves
    stale connections in the shared engine's pool across pytest-asyncio's
    per-test loops.
    """
    yield

    import asyncio

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings

    async def _clean():
        eng = create_async_engine(settings.database_url)
        try:
            async with async_sessionmaker(eng)() as session:
                await session.execute(delete(User).where(User.username.like(f"{PREFIX}%")))
                await session.commit()
        finally:
            await eng.dispose()

    asyncio.run(_clean())


def _uname() -> str:
    return f"{PREFIX}{uuid.uuid4().hex[:10]}"


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestAccessControl:
    async def test_l3_user_gets_403_on_all_user_endpoints(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("user")) as client:
            resp = await client.get("/api/users")
            assert resp.status_code == 403
            resp = await client.post(
                "/api/users", json={"username": _uname(), "password": "Password123", "role": "user"}
            )
            assert resp.status_code == 403
            resp = await client.put("/api/users/1", json={"role": "user"})
            assert resp.status_code == 403
            resp = await client.put("/api/users/1/status", json={"is_active": False})
            assert resp.status_code == 403

    async def test_unauthenticated_gets_401(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=anonymous_cookies()) as client:
            resp = await client.get("/api/users")
        assert resp.status_code == 401


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestListing:
    async def test_root_sees_all_roles(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.get("/api/users")
        assert resp.status_code == 200
        roles = {u["role"] for u in resp.json()}
        assert "root" in roles
        assert "admin" in roles
        assert "user" in roles

    async def test_admin_cannot_see_root_accounts(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.get("/api/users")
        assert resp.status_code == 200
        usernames = [u["username"] for u in resp.json()]
        assert TEST_ACCOUNTS["root"]["username"] not in usernames
        # The admin's own account and plain users are visible
        assert TEST_ACCOUNTS["admin"]["username"] in usernames


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestCreateHierarchy:
    async def test_root_creates_admin(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "admin"})
            assert resp.status_code == 201, resp.text
            assert resp.json()["role"] == "admin"

    async def test_root_creates_user(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            assert resp.status_code == 201

    async def test_admin_creates_user(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            assert resp.status_code == 201

    async def test_admin_cannot_create_admin(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "admin"})
            assert resp.status_code == 403

    async def test_root_role_never_assignable(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "root"})
            # Literal["admin","user"] rejects "root" at validation time
            assert resp.status_code in (403, 422)

    async def test_duplicate_username_returns_409(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            assert resp.status_code == 201
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            assert resp.status_code == 409


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestUpdateHierarchy:
    async def test_root_changes_admin_to_user(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "admin"})
            uid = resp.json()["id"]
            resp = await client.put(f"/api/users/{uid}", json={"role": "user"})
            assert resp.status_code == 200
            assert resp.json()["role"] == "user"

    async def test_root_cannot_promote_to_root(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            uid = resp.json()["id"]
            resp = await client.put(f"/api/users/{uid}", json={"role": "root"})
            assert resp.status_code in (403, 422)

    async def test_admin_cannot_modify_other_admin(self):
        transport = ASGITransport(app=app)
        name = _uname()
        # Root creates a second admin; the acting admin must not touch it
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "admin"})
            other_admin_id = resp.json()["id"]

        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.put(f"/api/users/{other_admin_id}", json={"role": "user"})
            assert resp.status_code == 403

    async def test_admin_resets_password_of_user(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            uid = resp.json()["id"]
            resp = await client.put(f"/api/users/{uid}", json={"password": "NewPassword456"})
            assert resp.status_code == 200

        # New password actually works for login
        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post("/api/auth/login", json={"username": name, "password": "NewPassword456"})
        assert resp.status_code == 200

    async def test_self_modification_returns_409(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.get("/api/users")
            me = next(u for u in resp.json() if u["username"] == TEST_ACCOUNTS["admin"]["username"])
            resp = await client.put(f"/api/users/{me['id']}", json={"password": "NewPassword456"})
            assert resp.status_code == 409


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestStatusHierarchy:
    async def test_admin_deactivates_user(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            uid = resp.json()["id"]
            resp = await client.put(f"/api/users/{uid}/status", json={"is_active": False})
            assert resp.status_code == 200
            assert resp.json()["is_active"] is False

    async def test_deactivated_user_cannot_login(self):
        transport = ASGITransport(app=app)
        name = _uname()
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "user"})
            uid = resp.json()["id"]
            await client.put(f"/api/users/{uid}/status", json={"is_active": False})

        async with AsyncClient(transport=transport, base_url="http://test", cookies={}) as client:
            resp = await client.post("/api/auth/login", json={"username": name, "password": "Password123"})
        assert resp.status_code == 401

    async def test_admin_cannot_deactivate_admin(self):
        transport = ASGITransport(app=app)
        name = _uname()
        # Root creates a second admin; the acting admin must not touch it
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.post("/api/users", json={"username": name, "password": "Password123", "role": "admin"})
            other_admin_id = resp.json()["id"]

        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.put(f"/api/users/{other_admin_id}/status", json={"is_active": False})
            assert resp.status_code == 403

    async def test_self_deactivation_returns_409(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.get("/api/users")
            me = next(u for u in resp.json() if u["username"] == TEST_ACCOUNTS["admin"]["username"])
            resp = await client.put(f"/api/users/{me['id']}/status", json={"is_active": False})
            assert resp.status_code == 409


@pytest.mark.usefixtures("_dispose_engine_after_test")
class TestRootImmutability:
    async def test_root_account_cannot_be_deactivated(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.get("/api/users")
            root = next(u for u in resp.json() if u["role"] == "root")
            resp = await client.put(f"/api/users/{root['id']}/status", json={"is_active": False})
            assert resp.status_code == 409

    async def test_root_account_cannot_be_demoted(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("root")) as client:
            resp = await client.get("/api/users")
            root = next(u for u in resp.json() if u["role"] == "root")
            resp = await client.put(f"/api/users/{root['id']}", json={"role": "user"})
            assert resp.status_code == 409

    async def test_admin_cannot_touch_root_account_by_id(self):
        """Root is hidden from the admin list, but direct ID access is blocked too."""
        from tests.conftest import _auth_state

        _ensure_test_users()
        root_id = _auth_state["root"]["id"]
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test", cookies=auth_cookies("admin")) as client:
            resp = await client.put(f"/api/users/{root_id}", json={"password": "NewPassword456"})
            assert resp.status_code == 409  # root account is immutable
            resp = await client.put(f"/api/users/{root_id}/status", json={"is_active": False})
            assert resp.status_code == 409
