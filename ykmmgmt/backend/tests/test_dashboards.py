"""Tests for Dashboard CRUD API — /api/dashboards endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


def _unique_name(prefix: str = "测试仪表盘") -> str:
    """Generate a unique name to avoid unique-constraint violations."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_view(client: AsyncClient) -> str:
    """Helper: create a view with a unique name and return its ID."""
    view_config = {
        "from_tables": ["refund_orders"],
        "joins": [],
        "columns": [
            {"table": "refund_orders", "column": "id", "alias": None},
            {"table": "refund_orders", "column": "refund_amount", "alias": None},
        ],
        "computed_columns": [],
        "selected_computed_columns": [],
        "filters": [],
        "group_by": [],
        "aggregations": [],
    }
    resp = await client.post(
        "/api/views",
        json={"name": _unique_name("测试视图"), "description": "test", "config_json": view_config},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_viz(client: AsyncClient, view_id: str) -> str:
    """Helper: create a visualization on the view and return its ID."""
    resp = await client.post(
        "/api/visualizations",
        json={
            "name": _unique_name("测试可视化"),
            "view_id": view_id,
            "chart_type": "bar",
            "config_json": {"x_column": "id", "y_columns": ["refund_amount"]},
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _text_tile(i: str = "tile-text-1") -> dict:
    return {"i": i, "tile_type": "text", "x": 0, "y": 0, "w": 6, "h": 2, "content": "# 标题"}


def _viz_tile(viz_id: str, i: str = "tile-viz-1") -> dict:
    return {"i": i, "tile_type": "visualization", "visualization_id": viz_id, "x": 0, "y": 2, "w": 6, "h": 4}


def _kpi_tile(view_id: str, i: str = "tile-kpi-1") -> dict:
    return {
        "i": i,
        "tile_type": "kpi_card",
        "x": 6,
        "y": 0,
        "w": 3,
        "h": 2,
        "config": {
            "view_id": view_id,
            "value_column": "refund_amount",
            "label": "退款总额",
            "agg": "SUM",
        },
    }


async def _cleanup(
    client: AsyncClient,
    dashboard_ids: list[str] | None = None,
    viz_ids: list[str] | None = None,
    view_ids: list[str] | None = None,
):
    """Helper: delete created entities to keep the DB clean."""
    for did in dashboard_ids or []:
        await client.delete(f"/api/dashboards/{did}")
    for vid in viz_ids or []:
        await client.delete(f"/api/visualizations/{vid}")
    for vid in view_ids or []:
        await client.delete(f"/api/views/{vid}")


@pytest.mark.asyncio
async def test_create_dashboard_success():
    """POST /api/dashboards creates a dashboard with all three tile types."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        viz_id = await _create_viz(client, view_id)
        name = _unique_name()
        payload = {
            "name": name,
            "description": "测试描述",
            "layout_json": [_text_tile(), _viz_tile(viz_id), _kpi_tile(view_id)],
        }
        resp = await client.post("/api/dashboards", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == name
        assert data["description"] == "测试描述"
        assert len(data["layout_json"]) == 3
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

        await _cleanup(client, [data["id"]], [viz_id], [view_id])


@pytest.mark.asyncio
async def test_create_dashboard_empty_layout():
    """POST /api/dashboards allows an empty layout."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/dashboards", json={"name": _unique_name()})
        assert resp.status_code == 201
        assert resp.json()["layout_json"] == []
        await _cleanup(client, [resp.json()["id"]])


@pytest.mark.asyncio
async def test_create_dashboard_duplicate_name_conflict():
    """POST /api/dashboards returns 409 when the name already exists."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        name = _unique_name("重复仪表盘")
        resp = await client.post("/api/dashboards", json={"name": name})
        assert resp.status_code == 201
        dash_id = resp.json()["id"]

        resp2 = await client.post("/api/dashboards", json={"name": name})
        assert resp2.status_code == 409
        assert "已存在" in resp2.json()["detail"]

        await _cleanup(client, [dash_id])


@pytest.mark.asyncio
async def test_create_dashboard_invalid_visualization_id():
    """POST /api/dashboards rejects tiles referencing missing visualizations."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_viz_id = str(uuid.uuid4())
        payload = {
            "name": _unique_name(),
            "layout_json": [_viz_tile(fake_viz_id)],
        }
        resp = await client.post("/api/dashboards", json=payload)
        assert resp.status_code == 422
        assert "不存在的可视化" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_dashboard_viz_tile_missing_visualization_id():
    """POST /api/dashboards rejects visualization tiles without visualization_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": _unique_name(),
            "layout_json": [{"i": "t1", "tile_type": "visualization", "x": 0, "y": 0, "w": 6, "h": 4}],
        }
        resp = await client.post("/api/dashboards", json=payload)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_dashboard_kpi_tile_missing_config_keys():
    """POST /api/dashboards rejects KPI tiles with incomplete config."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": _unique_name(),
            "layout_json": [
                {
                    "i": "t1",
                    "tile_type": "kpi_card",
                    "x": 0,
                    "y": 0,
                    "w": 3,
                    "h": 2,
                    "config": {"view_id": str(uuid.uuid4())},  # missing value_column/label/agg
                }
            ],
        }
        resp = await client.post("/api/dashboards", json=payload)
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_dashboard_kpi_tile_invalid_view_id():
    """POST /api/dashboards rejects KPI tiles referencing missing views."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": _unique_name(),
            "layout_json": [_kpi_tile(str(uuid.uuid4()))],
        }
        resp = await client.post("/api/dashboards", json=payload)
        assert resp.status_code == 422
        assert "不存在的视图" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_get_dashboard_not_found():
    """GET /api/dashboards/{id} returns 404 for non-existent ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(f"/api/dashboards/{uuid.uuid4()}")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_list_dashboards_includes_tile_count():
    """GET /api/dashboards returns summaries including tile_count."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        name = _unique_name("列表仪表盘")
        resp = await client.post(
            "/api/dashboards",
            json={"name": name, "layout_json": [_text_tile(), _text_tile("tile-text-2")]},
        )
        assert resp.status_code == 201
        dash_id = resp.json()["id"]

        resp = await client.get("/api/dashboards")
        assert resp.status_code == 200
        items = [d for d in resp.json() if d["id"] == dash_id]
        assert len(items) == 1
        item = items[0]
        assert item["name"] == name
        assert item["tile_count"] == 2
        assert "layout_json" not in item

        await _cleanup(client, [dash_id])


@pytest.mark.asyncio
async def test_update_dashboard_success():
    """PUT /api/dashboards/{id} updates name/description/layout."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/dashboards",
            json={"name": _unique_name("原始"), "layout_json": [_text_tile()]},
        )
        assert resp.status_code == 201
        dash_id = resp.json()["id"]

        new_layout = [_text_tile(), _text_tile("tile-text-2")]
        resp = await client.put(
            f"/api/dashboards/{dash_id}",
            json={"name": _unique_name("更新"), "description": "新描述", "layout_json": new_layout},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == "新描述"
        assert len(data["layout_json"]) == 2

        await _cleanup(client, [dash_id])


@pytest.mark.asyncio
async def test_update_dashboard_name_conflict():
    """PUT /api/dashboards/{id} returns 409 when renaming to a taken name."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        name_a = _unique_name("冲突A")
        resp_a = await client.post("/api/dashboards", json={"name": name_a})
        assert resp_a.status_code == 201
        resp_b = await client.post("/api/dashboards", json={"name": _unique_name("冲突B")})
        assert resp_b.status_code == 201
        dash_b_id = resp_b.json()["id"]

        resp = await client.put(f"/api/dashboards/{dash_b_id}", json={"name": name_a})
        assert resp.status_code == 409
        assert "已存在" in resp.json()["detail"]

        await _cleanup(client, [resp_a.json()["id"], dash_b_id])


@pytest.mark.asyncio
async def test_update_dashboard_not_found():
    """PUT /api/dashboards/{id} returns 404 for non-existent ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put(f"/api/dashboards/{uuid.uuid4()}", json={"name": "测试"})
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dashboard():
    """DELETE /api/dashboards/{id} removes the dashboard."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/dashboards", json={"name": _unique_name("待删除")})
        assert resp.status_code == 201
        dash_id = resp.json()["id"]

        resp = await client.delete(f"/api/dashboards/{dash_id}")
        assert resp.status_code == 204

        resp = await client.get(f"/api/dashboards/{dash_id}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_dashboard_not_found():
    """DELETE /api/dashboards/{id} returns 404 for non-existent ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete(f"/api/dashboards/{uuid.uuid4()}")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_layout_round_trip_fidelity():
    """Layout tiles round-trip exactly through create/get, incl. extra fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        viz_id = await _create_viz(client, view_id)
        tiles = [
            {**_text_tile(), "static": False},
            {**_viz_tile(viz_id), "moved": True},
            _kpi_tile(view_id),
        ]
        resp = await client.post(
            "/api/dashboards",
            json={"name": _unique_name("往返"), "layout_json": tiles},
        )
        assert resp.status_code == 201
        dash_id = resp.json()["id"]

        resp = await client.get(f"/api/dashboards/{dash_id}")
        assert resp.status_code == 200
        saved = resp.json()["layout_json"]
        assert len(saved) == 3

        by_i = {t["i"]: t for t in saved}
        assert by_i["tile-text-1"]["content"] == "# 标题"
        assert by_i["tile-text-1"]["static"] is False
        assert by_i["tile-viz-1"]["visualization_id"] == viz_id
        assert by_i["tile-viz-1"]["moved"] is True
        assert by_i["tile-kpi-1"]["config"]["agg"] == "SUM"
        assert by_i["tile-kpi-1"]["config"]["view_id"] == view_id
        for t in saved:
            assert set(t) >= {"i", "tile_type", "x", "y", "w", "h"}

        await _cleanup(client, [dash_id], [viz_id], [view_id])
