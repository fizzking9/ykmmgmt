"""Pytest fixtures shared across all backend tests."""

import uuid
from typing import Any

import pytest

from app.core.database import engine

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
