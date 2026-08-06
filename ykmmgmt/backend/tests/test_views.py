"""Tests for View CRUD API — GET/DELETE /api/views endpoints."""

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


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
        # First, list views to get an ID
        list_resp = await client.get("/api/views")
        views = list_resp.json()

        if len(views) == 0:
            pytest.skip("No views in database to test detail endpoint")

        view_id = views[0]["id"]
        response = await client.get(f"/api/views/{view_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == view_id
        assert "name" in data
        assert "config_json" in data
        assert "generated_sql" in data
        assert "created_at" in data
        assert "updated_at" in data


@pytest.mark.asyncio
async def test_get_view_404():
    """GET /api/views/{id} returns 404 for non-existent view."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/views/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_view_data():
    """GET /api/views/{id}/data returns paginated results."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First, list views to get an ID
        list_resp = await client.get("/api/views")
        views = list_resp.json()

        if len(views) == 0:
            pytest.skip("No views in database to test data endpoint")

        view_id = views[0]["id"]
        response = await client.get(
            f"/api/views/{view_id}/data", params={"page": 1, "size": 10}
        )
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


@pytest.mark.asyncio
async def test_get_view_data_404():
    """GET /api/views/{id}/data returns 404 for non-existent view."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/api/views/00000000-0000-0000-0000-000000000000/data"
        )
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_view_data_size_capped():
    """GET /api/views/{id}/data caps size at 100."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        list_resp = await client.get("/api/views")
        views = list_resp.json()

        if len(views) == 0:
            pytest.skip("No views in database to test size capping")

        view_id = views[0]["id"]
        response = await client.get(
            f"/api/views/{view_id}/data", params={"page": 1, "size": 200}
        )
        assert response.status_code == 200
        data = response.json()
        # size should be clamped to 100
        assert data["size"] <= 100
        assert len(data["rows"]) <= 100


@pytest.mark.asyncio
async def test_delete_view_returns_204():
    """DELETE /api/views/{id} returns 204 and view is removed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # First, list views to get an ID
        list_resp = await client.get("/api/views")
        views = list_resp.json()

        if len(views) == 0:
            pytest.skip("No views in database to test delete")

        view_id = views[0]["id"]

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
        response = await client.delete(
            "/api/views/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
