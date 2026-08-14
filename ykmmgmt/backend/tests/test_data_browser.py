"""Tests for Data Browser API — GET /api/tables endpoints with date filters."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


@pytest.mark.asyncio
async def test_filter_with_start_date_only():
    """Start date far in future returns 0; far in past returns structured data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Start date far in the future — should return 0
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={"datetime_col": "record_created_at", "start": "2099-01-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Without datetime_col, returns unfiltered data
        response = await client.get("/api/tables/refund_orders/data", params={"size": 10})
        assert response.status_code == 200
        data = response.json()
        assert "rows" in data
        assert "total" in data
        assert "page" in data
        assert "size" in data


@pytest.mark.asyncio
async def test_filter_with_end_date_only():
    """End date far in past returns 0; far in future returns structured data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # End date far in the past — should return 0
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={"datetime_col": "record_created_at", "end": "2000-01-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # End date far in the future — should return structure with data
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={"datetime_col": "record_created_at", "end": "2099-12-31"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_filter_with_both_dates():
    """Both start and end: far future returns 0, wide range returns data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Wide range far in the future — should return 0
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={
                "datetime_col": "record_created_at",
                "start": "2099-01-01",
                "end": "2099-12-31",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0

        # Exact single-date range — structure valid
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={
                "datetime_col": "record_created_at",
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
async def test_filter_without_datetime_col_ignored():
    """Providing start without datetime_col returns unfiltered data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={"start": "2026-06-01"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert isinstance(data["rows"], list)


@pytest.mark.asyncio
async def test_filter_invalid_date_format():
    """Invalid date format returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/tables/refund_orders/data",
            params={
                "datetime_col": "record_created_at",
                "start": "not-a-date",
            },
        )
        assert response.status_code == 422
