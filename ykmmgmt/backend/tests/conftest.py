"""Pytest fixtures shared across all backend tests."""

import uuid
from typing import Any

import httpx
import pytest

from app.core.database import engine

# ── Auth test accounts ─────────────────────────────────────────────────────
# Seeded once per test session into the real DB; tokens are generated
# directly (no HTTP login) so every AsyncClient gets valid auth cookies.

TEST_ACCOUNTS: dict[str, dict[str, str]] = {
    "root": {"username": "test__root", "password": "RootPass123", "role": "root"},
    "admin": {"username": "test__admin", "password": "AdminPass123", "role": "admin"},
    "user": {"username": "test__user", "password": "UserPass123", "role": "user"},
}

_auth_state: dict[str, Any] = {}


def _ensure_test_users() -> None:
    """Seed the three test accounts (idempotent) and mint their tokens."""
    if _auth_state:
        return

    import asyncio

    from sqlalchemy import select

    from app.core.database import async_session_factory
    from app.models.user import User
    from app.services.auth import create_access_token, create_refresh_token, hash_password

    async def _seed() -> dict[str, int]:
        try:
            async with async_session_factory() as session:
                ids: dict[str, int] = {}
                for key, acc in TEST_ACCOUNTS.items():
                    result = await session.execute(select(User).where(User.username == acc["username"]))
                    user = result.scalar_one_or_none()
                    if user is None:
                        user = User(
                            username=acc["username"],
                            password_hash=hash_password(acc["password"]),
                            role=acc["role"],
                            is_active=True,
                        )
                        session.add(user)
                        await session.flush()
                    ids[key] = user.id
                await session.commit()
                return ids
        finally:
            await engine.dispose()

    ids = asyncio.run(_seed())
    for key, user_id in ids.items():
        _auth_state[key] = {
            "id": user_id,
            "cookies": {
                "access_token": create_access_token(user_id),
                "refresh_token": create_refresh_token(user_id),
            },
        }


def auth_cookies(role: str = "root") -> dict[str, str]:
    """Valid auth cookies for the given test account ('root' | 'admin' | 'user')."""
    _ensure_test_users()
    return dict(_auth_state[role]["cookies"])


def anonymous_cookies() -> dict[str, str]:
    """Explicitly empty cookies — opts a client out of the default auth."""
    return {}


@pytest.fixture(scope="session", autouse=True)
def _remove_test_users_after_session():
    """Delete the test__* accounts when the session ends.

    The accounts are seeded into the real database (tests hit live tables),
    so without this they would linger as loginable accounts in the dev DB.
    Uses a throwaway engine in its own event loop — teardown must not touch
    the shared engine's pool from a foreign loop.
    """
    yield
    if not _auth_state:
        return

    import asyncio

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.core.config import settings
    from app.models.user import User

    async def _cleanup() -> None:
        eng = create_async_engine(settings.database_url)
        try:
            async with async_sessionmaker(eng)() as session:
                await session.execute(delete(User).where(User.username.like("test__%")))
                await session.commit()
        finally:
            await eng.dispose()

    asyncio.run(_cleanup())


@pytest.fixture(autouse=True)
def _default_authenticated_clients(monkeypatch):
    """Default every ``httpx.AsyncClient`` to the test root account.

    Existing tests construct clients inline (``AsyncClient(transport=...)``)
    so we inject default cookies at construction time instead of touching
    every call site. Tests that pass their own ``cookies`` (e.g. the auth
    and authz suites) are left untouched.
    """
    _ensure_test_users()
    default_cookies = dict(_auth_state["root"]["cookies"])

    original_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs.setdefault("cookies", default_cookies)
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)
    yield


# Standard business columns for fixture tables (labels double as the
# Chinese headers that imports match against)
FIXTURE_COLUMNS = [
    {"name": "order_no", "type": "String", "length": 50, "nullable": True, "label": "订单号"},
    {"name": "amount", "type": "Numeric", "nullable": True, "label": "金额"},
    {"name": "status", "type": "String", "length": 20, "nullable": True, "label": "状态"},
    {"name": "record_time", "type": "DateTime", "nullable": True, "label": "记录时间"},
]

# Rows seeded into every fixture table (spans June/July 2026 for date filters)
FIXTURE_CSV = (
    "订单号,金额,状态,记录时间\n"
    "A001,100.50,已完成,2026-06-05 10:00:00\n"
    "A002,200.00,已完成,2026-06-15 11:30:00\n"
    "A003,300.25,待处理,2026-07-01 09:00:00\n"
    "A004,50.00,已完成,2026-06-20 14:00:00\n"
    "A005,75.10,待处理,2026-07-05 16:30:00\n"
    "A006,120.00,已完成,2026-06-28 08:45:00\n"
)


@pytest.fixture
async def _dispose_engine_after_test():
    """Dispose async engine pool after async tests to prevent cross-loop leakage.

    Without this, asyncpg connections created in one function-scoped event
    loop become stale/corrupted when pytest-asyncio creates a fresh event
    loop for the next test, causing "another operation is in progress".

    This fixture is opt-in — only async DB tests request it via
    ``pytest.mark.usefixtures``.  Sync tests skip it entirely so they
    don't pay the cost of creating a throwaway event loop.
    """
    yield
    await engine.dispose()


@pytest.fixture(scope="module")
def shared_dynamic_table():
    """Module-wide holder for one Schema-Manager-created fixture table.

    Tests call :func:`ensure_shared_table` once; the table is created via
    the real API and purged (table + migrations + version chain) when the
    module finishes.
    """
    state: dict[str, Any] = {}
    yield state
    name = state.get("name")
    if name:
        import asyncio

        from tests.schema_cleanup import purge_dynamic_table

        asyncio.run(purge_dynamic_table(name))


async def ensure_shared_table(client, state: dict[str, Any], prefix: str = "fixt") -> str:
    """Lazily create + seed the module's fixture table; returns its name.

    Creates the table through POST /api/schema/tables and uploads the
    standard fixture rows through POST /api/imports, so every feature under
    test exercises the real generic pipeline (no built-in tables remain).
    """
    if state.get("name"):
        return state["name"]

    name = f"{prefix}_{uuid.uuid4().hex[:6]}"
    resp = await client.post(
        "/api/schema/tables",
        json={"name": name, "display_name": "测试业务表", "columns": FIXTURE_COLUMNS},
    )
    assert resp.status_code == 201, resp.text

    resp = await client.post(
        "/api/imports",
        files={"file": ("fixture.csv", FIXTURE_CSV.encode("utf-8"), "text/csv")},
        data={"target_table": name},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["rows_inserted"] == 6

    state["name"] = name
    return name
