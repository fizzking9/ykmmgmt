"""Tests for Data Browser API — GET /api/tables endpoints with date filters.

Runs against a dynamically created fixture table (Schema Manager API),
since the system ships with no built-in business tables.
"""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.conftest import ensure_shared_table

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


@pytest.mark.asyncio
async def test_filter_with_start_date_only(shared_dynamic_table):
    """Start date far in future returns 0; far in past returns structured data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        # Start date far in the future — should return 0
        response = await client.get(
            f"/api/tables/{table}/data",
            params={"datetime_col": "record_time", "start": "2099-01-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Without datetime_col, returns unfiltered data
        response = await client.get(f"/api/tables/{table}/data", params={"size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data


@pytest.mark.asyncio
async def test_filter_with_end_date_only(shared_dynamic_table):
    """End date far in past returns 0; far in future returns structured data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        # End date far in the past — should return 0
        response = await client.get(
            f"/api/tables/{table}/data",
            params={"datetime_col": "record_time", "end": "2000-01-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # End date far in the future — should return structure with data
        response = await client.get(
            f"/api/tables/{table}/data",
            params={"datetime_col": "record_time", "end": "2099-12-31"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_filter_with_both_dates(shared_dynamic_table):
    """Both start and end: far future returns 0, wide range returns data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        # Wide range far in the future — should return 0
        response = await client.get(
            f"/api/tables/{table}/data",
            params={
                "datetime_col": "record_time",
                "start": "2099-01-01",
                "end": "2099-12-31",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Exact single-date range — structure valid
        response = await client.get(
            f"/api/tables/{table}/data",
            params={
                "datetime_col": "record_time",
                "start": "2026-06-15",
                "end": "2026-06-15",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data


@pytest.mark.asyncio
async def test_filter_invalid_table_returns_404():
    """Unknown table name returns 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/tables/nonexistent/data")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_filter_without_datetime_col_ignored(shared_dynamic_table):
    """Providing start without datetime_col returns unfiltered data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        response = await client.get(
            f"/api/tables/{table}/data",
            params={"start": "2026-06-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_filter_invalid_date_format(shared_dynamic_table):
    """Invalid date format returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        response = await client.get(
            f"/api/tables/{table}/data",
            params={
                "datetime_col": "record_time",
                "start": "not-a-date",
            },
        )
        assert response.status_code == 422


# ── Column value filters with operators (View Builder parity) ──────────────────────


@pytest.mark.asyncio
async def test_column_filter_text_operators(shared_dynamic_table):
    """Text columns support eq/neq/startswith/contains/is_not_null."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)

        async def total(params: list[tuple[str, str]]) -> int:
            resp = await client.get(f"/api/tables/{table}/data", params=params)
            assert resp.status_code == 200, resp.text
            return resp.json()["total"]

        # 4 rows are 已完成 in the fixture
        assert await total([("filter_col", "status"), ("filter_op", "eq"), ("filter_value", "已完成")]) == 4
        assert await total([("filter_col", "status"), ("filter_op", "neq"), ("filter_value", "已完成")]) == 2
        assert await total([("filter_col", "order_no"), ("filter_op", "startswith"), ("filter_value", "A00")]) == 6
        assert await total([("filter_col", "order_no"), ("filter_op", "startswith"), ("filter_value", "A001")]) == 1
        assert await total([("filter_col", "order_no"), ("filter_op", "endswith"), ("filter_value", "05")]) == 1
        assert await total([("filter_col", "status"), ("filter_op", "is_not_null")]) == 6
        assert await total([("filter_col", "status"), ("filter_op", "is_null")]) == 0


@pytest.mark.asyncio
async def test_column_filter_numeric_operators(shared_dynamic_table):
    """Numeric columns support comparison operators; values parse as numbers."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)

        async def total(params: list[tuple[str, str]]) -> int:
            resp = await client.get(f"/api/tables/{table}/data", params=params)
            assert resp.status_code == 200, resp.text
            return resp.json()["total"]

        # Fixture amounts: 100.50, 200.00, 300.25, 50.00, 75.10, 120.00
        assert await total([("filter_col", "amount"), ("filter_op", "gt"), ("filter_value", "100")]) == 4
        assert await total([("filter_col", "amount"), ("filter_op", "gte"), ("filter_value", "100")]) == 4
        assert await total([("filter_col", "amount"), ("filter_op", "lt"), ("filter_value", "100")]) == 2
        assert await total([("filter_col", "amount"), ("filter_op", "lte"), ("filter_value", "100")]) == 2
        assert await total([("filter_col", "amount"), ("filter_op", "eq"), ("filter_value", "200.00")]) == 1


@pytest.mark.asyncio
async def test_column_filter_date_range_row(shared_dynamic_table):
    """A filter row on a date column uses filter_date_start/end (inclusive)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        # June 2026 rows: A001, A002, A004, A006
        resp = await client.get(
            f"/api/tables/{table}/data",
            params=[
                ("filter_col", "record_time"),
                ("filter_date_start", "2026-06-01"),
                ("filter_date_end", "2026-06-30"),
            ],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 4

        # Invalid date string is rejected
        resp = await client.get(
            f"/api/tables/{table}/data",
            params=[
                ("filter_col", "record_time"),
                ("filter_date_start", "not-a-date"),
            ],
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_column_filter_invalid_numeric_value(shared_dynamic_table):
    """A non-numeric value against a numeric column returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        resp = await client.get(
            f"/api/tables/{table}/data",
            params=[
                ("filter_col", "amount"),
                ("filter_op", "gt"),
                ("filter_value", "abc"),
            ],
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_column_filter_unsupported_operator(shared_dynamic_table):
    """Unknown operators are rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        resp = await client.get(
            f"/api/tables/{table}/data",
            params=[
                ("filter_col", "status"),
                ("filter_op", "regex"),
                ("filter_value", "x"),
            ],
        )
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_column_filter_legacy_mode_still_supported(shared_dynamic_table):
    """The legacy filter_mode param (contains|exact) still works."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        table = await ensure_shared_table(client, shared_dynamic_table)
        resp = await client.get(
            f"/api/tables/{table}/data",
            params=[
                ("filter_col", "status"),
                ("filter_mode", "exact"),
                ("filter_value", "已完成"),
            ],
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 4
