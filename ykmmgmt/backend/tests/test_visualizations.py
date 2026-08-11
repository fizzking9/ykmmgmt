"""Tests for Visualization CRUD API — /api/visualizations endpoints."""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")


def _unique_name(prefix: str = "测试视图") -> str:
    """Generate a unique view name to avoid unique-constraint violations."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


async def _create_view(client: AsyncClient) -> str:
    """Helper: create a view with a unique name and return its ID."""
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


async def _cleanup(client: AsyncClient, view_id: str, viz_ids: list[str] | None = None):
    """Helper: delete visualizations and the view to keep the DB clean."""
    if viz_ids:
        for vid in viz_ids:
            await client.delete(f"/api/visualizations/{vid}")
    await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
async def test_create_visualization_success():
    """POST /api/visualizations creates a visualization with valid data."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "测试图表",
            "view_id": view_id,
            "chart_type": "bar",
            "config_json": {"x_column": "id", "y_columns": ["id"]},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "测试图表"
        assert data["chart_type"] == "bar"
        assert data["view_id"] == view_id
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

        await _cleanup(client, view_id, [data["id"]])


@pytest.mark.asyncio
async def test_create_visualization_duplicate_name_conflict():
    """POST /api/visualizations returns 409 when the name already exists."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        name = _unique_name("重复图表")
        payload = {
            "name": name,
            "view_id": view_id,
            "chart_type": "bar",
            "config_json": {"x_column": "id", "y_columns": ["id"]},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        # Same name again -> conflict
        resp2 = await client.post("/api/visualizations", json=payload)
        assert resp2.status_code == 409
        assert "已存在" in resp2.json()["detail"]

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_create_visualization_histogram():
    """POST /api/visualizations accepts the histogram chart type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "直方图",
            "view_id": view_id,
            "chart_type": "histogram",
            "config_json": {"columns": ["id"], "bins": 20},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["chart_type"] == "histogram"
        await _cleanup(client, view_id, [data["id"]])


@pytest.mark.asyncio
async def test_create_visualization_boxplot():
    """POST /api/visualizations accepts the boxplot chart type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "箱线图",
            "view_id": view_id,
            "chart_type": "boxplot",
            "config_json": {"category_column": "", "value_column": "id"},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["chart_type"] == "boxplot"
        await _cleanup(client, view_id, [data["id"]])


@pytest.mark.asyncio
async def test_create_visualization_histogram_missing_bins():
    """POST /api/visualizations rejects histogram config missing the bins key."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "直方图",
            "view_id": view_id,
            "chart_type": "histogram",
            "config_json": {"columns": ["id"]},  # missing bins
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 422
        assert "bins" in resp.json()["detail"]
        await _cleanup(client, view_id)


@pytest.mark.asyncio
async def test_create_visualization_invalid_chart_type():
    """POST /api/visualizations rejects invalid chart_type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "测试",
            "view_id": view_id,
            "chart_type": "invalid_type",
            "config_json": {},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 422

        await _cleanup(client, view_id)


@pytest.mark.asyncio
async def test_create_visualization_invalid_view_id():
    """POST /api/visualizations rejects non-existent view_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = str(uuid.uuid4())
        payload = {
            "name": "测试",
            "view_id": fake_id,
            "chart_type": "bar",
            "config_json": {"x_column": "a", "y_columns": ["b"]},
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 422
        assert "不存在" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_create_visualization_missing_config_keys():
    """POST /api/visualizations rejects missing required config keys."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        payload = {
            "name": "测试",
            "view_id": view_id,
            "chart_type": "bar",
            "config_json": {"x_column": "a"},  # missing y_columns
        }
        resp = await client.post("/api/visualizations", json=payload)
        assert resp.status_code == 422
        assert "y_columns" in resp.json()["detail"]

        await _cleanup(client, view_id)


@pytest.mark.asyncio
async def test_update_visualization_success():
    """PUT /api/visualizations/{id} updates an existing visualization."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        # Create
        resp = await client.post(
            "/api/visualizations",
            json={
                "name": "原始名称",
                "view_id": view_id,
                "chart_type": "table",
                "config_json": {"visible_columns": ["id"]},
            },
        )
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        # Update
        resp = await client.put(
            f"/api/visualizations/{viz_id}",
            json={"name": "新名称"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "新名称"

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_update_visualization_not_found():
    """PUT /api/visualizations/{id} returns 404 for non-existent ID."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/api/visualizations/{fake_id}",
            json={"name": "测试"},
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_list_visualizations():
    """GET /api/visualizations returns a list."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/visualizations")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if len(data) > 0:
            item = data[0]
            assert "id" in item
            assert "name" in item
            assert "chart_type" in item
            assert "view_id" in item
            assert "created_at" in item
            assert "updated_at" in item
            # List should NOT include config_json
            assert "config_json" not in item


@pytest.mark.asyncio
async def test_get_visualization_detail():
    """GET /api/visualizations/{id} returns full detail."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        resp = await client.post(
            "/api/visualizations",
            json={
                "name": "详情测试",
                "view_id": view_id,
                "chart_type": "kpi_card",
                "config_json": {"value_column": "id", "label": "总数"},
            },
        )
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        resp = await client.get(f"/api/visualizations/{viz_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "详情测试"
        assert data["config_json"]["value_column"] == "id"
        assert data["config_json"]["label"] == "总数"

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_delete_visualization():
    """DELETE /api/visualizations/{id} removes the visualization."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        resp = await client.post(
            "/api/visualizations",
            json={
                "name": "待删除",
                "view_id": view_id,
                "chart_type": "pie",
                "config_json": {"label_column": "id", "value_column": "id"},
            },
        )
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        resp = await client.delete(f"/api/visualizations/{viz_id}")
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(f"/api/visualizations/{viz_id}")
        assert resp.status_code == 404

        await _cleanup(client, view_id)


@pytest.mark.asyncio
async def test_get_visualization_data():
    """GET /api/visualizations/{id}/data returns rows from the view's SQL."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_view(client)
        resp = await client.post(
            "/api/visualizations",
            json={
                "name": "数据测试",
                "view_id": view_id,
                "chart_type": "table",
                "config_json": {"visible_columns": ["id"]},
            },
        )
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        resp = await client.get(f"/api/visualizations/{viz_id}/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "columns" in data
        assert "rows" in data
        assert "chart_type" in data
        assert "config_json" in data
        assert data["chart_type"] == "table"
        assert isinstance(data["rows"], list)
        assert isinstance(data["columns"], list)

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_get_visualization_data_with_filtered_view():
    """Data endpoint works for views whose SQL has bind parameters.

    Regression test: the endpoint used to execute the stored generated_sql
    without bind params, which failed on filtered views with
    "A value is required for bind parameter". It must regenerate SQL +
    params from the view's stored config.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_config = {
            "from_tables": ["refund_orders"],
            "joins": [],
            "columns": [
                {"table": "refund_orders", "column": "refund_amount", "alias": None},
            ],
            "computed_columns": [],
            "selected_computed_columns": [],
            "filters": [
                {
                    "column": "refund_orders.record_created_at",
                    "date_start": "2026-01-01",
                    "date_end": "2026-12-31",
                }
            ],
            "group_by": [],
            "aggregations": [],
        }
        resp = await client.post(
            "/api/views",
            json={"name": _unique_name(), "description": "filtered", "config_json": view_config},
        )
        assert resp.status_code == 201
        view_id = resp.json()["id"]

        resp = await client.post(
            "/api/visualizations",
            json={
                "name": _unique_name("测试可视化"),
                "view_id": view_id,
                "chart_type": "histogram",
                "config_json": {"columns": ["refund_amount"], "bins": 10},
            },
        )
        assert resp.status_code == 201
        viz_id = resp.json()["id"]

        resp = await client.get(f"/api/visualizations/{viz_id}/data")
        assert resp.status_code == 200
        data = resp.json()
        assert "refund_amount" in data["columns"]
        assert isinstance(data["rows"], list)

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_get_visualization_data_not_found():
    """GET /api/visualizations/{id}/data returns 404 for non-existent viz."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/visualizations/{fake_id}/data")
        assert resp.status_code == 404


# ── Time-Profile (start/end/granularity/agg) tests ────────────────────────


async def _create_time_view(client: AsyncClient) -> str:
    """Helper: create a view exposing a datetime column + a numeric column."""
    view_config = {
        "from_tables": ["refund_orders"],
        "joins": [],
        "columns": [
            {"table": "refund_orders", "column": "record_created_at", "alias": None},
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
        json={"name": _unique_name("时间视图"), "description": "time", "config_json": view_config},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_time_viz(client: AsyncClient, view_id: str, *, with_date_column: bool) -> str:
    """Helper: create a line viz, optionally with a date_column time profile."""
    config = {"x_column": "record_created_at", "y_columns": ["refund_amount"]}
    if with_date_column:
        config["date_column"] = "record_created_at"
        config["default_granularity"] = "day"
        config["default_agg"] = "SUM"
    resp = await client.post(
        "/api/visualizations",
        json={
            "name": _unique_name("时间可视化"),
            "view_id": view_id,
            "chart_type": "line",
            "config_json": config,
        },
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_data_time_filter_narrows_rows():
    """start/end params narrow rows to the given date range."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=True)

        base = await client.get(f"/api/visualizations/{viz_id}/data")
        assert base.status_code == 200
        base_rows = base.json()["rows"]

        filtered = await client.get(
            f"/api/visualizations/{viz_id}/data",
            params={"start": "2026-06-01", "end": "2026-06-30"},
        )
        assert filtered.status_code == 200
        rows = filtered.json()["rows"]
        assert len(rows) <= len(base_rows)
        for row in rows:
            date_part = row["record_created_at"][:10]
            assert "2026-06-01" <= date_part <= "2026-06-30"

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_data_granularity_rebuckets_monthly():
    """granularity=month re-buckets daily rows into monthly SUM buckets."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=True)

        base = await client.get(f"/api/visualizations/{viz_id}/data")
        base_rows = base.json()["rows"]

        monthly = await client.get(
            f"/api/visualizations/{viz_id}/data",
            params={"granularity": "month", "agg": "SUM"},
        )
        assert monthly.status_code == 200
        rows = monthly.json()["rows"]
        assert len(rows) <= len(base_rows)
        # Every bucket starts on the 1st of a month
        for row in rows:
            assert row["record_created_at"][:10].endswith("-01")
        # Monthly sums preserve the overall total (NULL-date rows excluded)
        base_total = sum(
            float(r["refund_amount"])
            for r in base_rows
            if r["refund_amount"] is not None and r["record_created_at"] is not None
        )
        monthly_total = sum(float(r["refund_amount"]) for r in rows if r["refund_amount"] is not None)
        assert abs(base_total - monthly_total) < 0.01

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_data_time_params_ignored_without_date_column():
    """Time params are ignored when the viz has no date_column profile."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=False)

        plain = await client.get(f"/api/visualizations/{viz_id}/data")
        assert plain.status_code == 200
        overridden = await client.get(
            f"/api/visualizations/{viz_id}/data",
            params={
                "start": "2026-06-01",
                "end": "2026-06-30",
                "granularity": "month",
                "agg": "SUM",
            },
        )
        assert overridden.status_code == 200
        assert overridden.json()["rows"] == plain.json()["rows"]

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_data_invalid_granularity_rejected():
    """Invalid granularity is rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=True)

        resp = await client.get(
            f"/api/visualizations/{viz_id}/data", params={"granularity": "hour"}
        )
        assert resp.status_code == 422

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_data_invalid_agg_rejected():
    """Invalid agg function is rejected with 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=True)

        resp = await client.get(
            f"/api/visualizations/{viz_id}/data",
            params={"granularity": "month", "agg": "MEDIAN"},
        )
        assert resp.status_code == 422

        await _cleanup(client, view_id, [viz_id])


@pytest.mark.asyncio
async def test_data_invalid_start_date_rejected():
    """Malformed start date is rejected with 422 and a Chinese message."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = await _create_time_view(client)
        viz_id = await _create_time_viz(client, view_id, with_date_column=True)

        resp = await client.get(
            f"/api/visualizations/{viz_id}/data", params={"start": "not-a-date"}
        )
        assert resp.status_code == 422
        assert "格式无效" in resp.json()["detail"]

        await _cleanup(client, view_id, [viz_id])
