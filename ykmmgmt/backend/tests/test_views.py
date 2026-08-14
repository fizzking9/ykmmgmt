"""Tests for View CRUD API — GET/DELETE /api/views endpoints.

Every test creates its own uniquely-named view and only ever deletes what it
created — tests run against the shared dev database and must never touch
pre-existing user data (an earlier version deleted `views[0]` and silently
removed user-created views on every test run).
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


def _unique_name(prefix: str = "测试视图") -> str:
    """Generate a unique view name to avoid unique-constraint violations."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_view(client: AsyncClient) -> str:
    """Helper: create a throwaway view and return its ID."""
    view_config = {
        "from_tables": ["refund_orders"],
        "joins": [],
        "columns": [{"table": "refund_orders", "column": "id", "alias": None}],
        "computed_columns": [],
        "selected_computed_columns": [],
        "filters": [],
        "group_by": [],
        "aggregations": [],
    }
    resp = await client.post(
        "/api/views",
        json={"name": _unique_name(), "description": "test", "config_json": view_config},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_list_views_returns_array():
    """GET /api/views returns a JSON array with correct keys and ordering."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/views")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            item = data[0]
            assert "id" in item
            assert "name" in item
            assert "description" in item
            assert "created_at" in item
            assert "updated_at" in item
            # Must NOT include config_json or generated_sql in list response
            assert "config_json" not in item
            assert "generated_sql" not in item

            # Verify ordering: newer first (created_at descending)
            if len(data) >= 2:
                d1 = data[0]["created_at"]
                d2 = data[1]["created_at"]
                assert d1 >= d2, f"Expected created_at DESC, got {d1} < {d2}"


@pytest.mark.asyncio
async def test_get_view_detail():
    """GET /api/views/{id} returns full view with config_json and generated_sql."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        try:
            response = await client.get(f"/api/views/{view_id}")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == view_id
            assert "name" in data
            assert "config_json" in data
            assert "generated_sql" in data
            assert "created_at" in data
            assert "updated_at" in data
        finally:
            await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
async def test_get_view_404():
    """GET /api/views/{id} returns 404 for non-existent view."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/views/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_view_data():
    """GET /api/views/{id}/data returns paginated results."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        try:
            response = await client.get(f"/api/views/{view_id}/data", params={"page": 1, "size": 10})
            assert response.status_code == 200
            data = response.json()
            assert "rows" in data
            assert "total" in data
            assert "page" in data
            assert "size" in data
            assert "columns" in data
            assert data["page"] == 1
            assert data["size"] == 10
            assert isinstance(data["rows"], list)
            assert isinstance(data["total"], int)
            assert len(data["rows"]) <= 10
        finally:
            await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
async def test_get_view_data_404():
    """GET /api/views/{id}/data returns 404 for non-existent view."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/views/00000000-0000-0000-0000-000000000000/data")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_view_data_size_capped():
    """GET /api/views/{id}/data caps size at 100."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        try:
            response = await client.get(f"/api/views/{view_id}/data", params={"page": 1, "size": 200})
            assert response.status_code == 200
            data = response.json()
            # size should be clamped to 100
            assert data["size"] <= 100
            assert len(data["rows"]) <= 100
        finally:
            await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
async def test_delete_view_returns_204():
    """DELETE /api/views/{id} returns 204 and view is removed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create a dedicated throwaway view — never delete pre-existing views
        view_id = await _create_view(client)

        # Delete it
        del_resp = await client.delete(f"/api/views/{view_id}")
        assert del_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/views/{view_id}")
        assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_view_404():
    """DELETE /api/views/{id} returns 404 for non-existent view."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.delete("/api/views/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404
