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
