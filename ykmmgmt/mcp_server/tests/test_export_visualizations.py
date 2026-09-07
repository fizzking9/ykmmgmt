"""Tests for the export_visualizations tool (download URLs, errors)."""

from typing import Any

from mcp_server.files import default_store
from mcp_server.tools.export_visualizations import handler, sanitize_filename

TABLE_CSV = "\ufeff订单号,金额\nA001,100.5\nA002,200\n"

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

BAR_DATA = {
    "columns": ["月份", "金额"],
    "rows": [{"月份": "2026-06", "金额": 100}, {"月份": "2026-07", "金额": 200}],
    "chart_type": "bar",
    "config_json": {"x_column": "月份", "y_columns": ["金额"]},
    "column_types": {"月份": "date", "金额": "number"},
}


class FakeClient:
    """In-memory stand-in for BackendClient: scripted endpoint responses."""

    def __init__(self, viz_list: list[dict], responses: dict[str, Any]):
        self.viz_list = viz_list
        self.responses = responses  # path → return value or Exception

    async def get_json(self, path: str, *, params: dict | None = None):
        value = self.responses.get(path)
        if isinstance(value, Exception):
            raise value
        if value is not None:
            return value
        if path == "/api/visualizations":
            return self.viz_list
        raise KeyError(path)

    async def request(self, method: str, path: str, *, params=None, json=None):
        class FakeResponse:
            def __init__(self, status_code: int, text: str):
                self.status_code = status_code
                self.text = text
                self.content = text.encode("utf-8")

        value = self.responses.get(path)
        if isinstance(value, Exception):
            raise value
        if value is None:
            return FakeResponse(404, "not found")
        status, body = value
        return FakeResponse(status, body)


TABLE_VIZ = {
    "id": "id-table",
    "name": "退款明细表",
    "chart_type": "table",
}
BAR_VIZ = {
    "id": "id-bar",
    "name": "月度柱状图",
    "chart_type": "bar",
}


def _responses() -> dict[str, Any]:
    return {
        "/api/visualizations/id-table/export": (200, TABLE_CSV),
        "/api/visualizations/id-bar/data": BAR_DATA,
    }


def _assert_png_file(path) -> None:
    content = path.read_bytes()
    assert len(content) > 100, "PNG file is suspiciously small"
    assert content.startswith(PNG_SIGNATURE), "exported file is not a PNG"


# ── Path selection: table → CSV, other → PNG ────────────────────────────────


async def test_table_viz_stores_csv_and_returns_url():
    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(client, {})

    assert result["exported"] == 1
    assert result["failed"] == 0
    entry = result["files"][0]
    assert entry["chart_type"] == "table"
    assert entry["columns"] == ["订单号", "金额"]
    assert entry["row_count"] == 2
    assert entry["file"].endswith("退款明细表.csv")
    # The file is stored in the file store and the URL is verifiable
    store = default_store()
    batch_id, filename = _parse_url(entry["url"])
    stored = store.file_path(batch_id, filename)
    assert stored is not None
    assert stored.read_text(encoding="utf-8").startswith("\ufeff")  # BOM preserved
    assert store.verify(batch_id, filename, _ts_of(entry["url"]), _token_of(entry["url"]))


async def test_non_table_viz_renders_png_and_returns_url():
    client = FakeClient([BAR_VIZ], _responses())
    result = await handler(client, {})

    entry = result["files"][0]
    assert entry["chart_type"] == "bar"
    assert entry["row_count"] == 2
    assert entry["columns"] == ["月份", "金额"]
    assert entry["file"].endswith("月度柱状图.png")
    store = default_store()
    batch_id, filename = _parse_url(entry["url"])
    _assert_png_file(store.file_path(batch_id, filename))


def _parse_url(url: str) -> tuple[str, str]:
    """Extract (batch_id, filename) from a download URL."""
    path = url.split("?", 1)[0]
    parts = path.rsplit("/", 2)
    return parts[1], parts[2]


def _ts_of(url: str) -> str:
    return dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))["ts"]


def _token_of(url: str) -> str:
    return dict(p.split("=", 1) for p in url.split("?", 1)[1].split("&"))["token"]


# ── Filename sanitization ────────────────────────────────────────────────────


def test_sanitize_filename_strips_unsafe_characters():
    assert sanitize_filename('报表/2026:Q3*"存"在?') == "报表_2026_Q3__存_在_"
    assert sanitize_filename("  正常名称  ") == "正常名称"
    assert sanitize_filename("..") == "未命名"


async def test_unsafe_name_produces_safe_file():
    viz = {**TABLE_VIZ, "name": "销售/华北:2026"}
    client = FakeClient([viz], _responses())
    result = await handler(client, {})
    assert result["exported"] == 1
    assert "/" not in result["files"][0]["file"]
    assert "\\" not in result["files"][0]["file"]


async def test_duplicate_sanitized_names_get_unique_suffixes():
    vizzes = [
        {**BAR_VIZ, "id": "id-1", "name": "报表"},
        {**BAR_VIZ, "id": "id-2", "name": "报表"},
    ]
    responses = {
        "/api/visualizations/id-1/data": BAR_DATA,
        "/api/visualizations/id-2/data": BAR_DATA,
    }
    client = FakeClient(vizzes, responses)
    result = await handler(client, {})

    assert result["exported"] == 2
    files = sorted(f["file"] for f in result["files"])
    assert files[0].endswith("报表.png")
    assert files[1].endswith("报表_2.png")


# ── Summary shape ────────────────────────────────────────────────────────────


async def test_summary_stays_compact():
    """The summary carries metadata + URLs, never dataset values."""
    client = FakeClient([TABLE_VIZ, BAR_VIZ], _responses())
    result = await handler(client, {})

    serialized = str(result)
    assert "A001" not in serialized  # no CSV cell values inline
    assert "2026-06" not in serialized  # no chart row values inline
    assert result["exported"] == 2
    assert {f["chart_type"] for f in result["files"]} == {"table", "bar"}
    assert all(f["url"].startswith("/mcp/files/") for f in result["files"])


async def test_public_url_prefixes_download_links(monkeypatch):
    """When YKM_MCP_PUBLIC_URL is set, URLs are absolute."""
    monkeypatch.setenv("YKM_MCP_PUBLIC_URL", "http://cloud.example/mcp/")
    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(client, {})
    url = result["files"][0]["url"]
    assert url.startswith("http://cloud.example/mcp/files/")
    assert "token=" in url and "ts=" in url


# ── Error handling ──────────────────────────────────────────────────────────


async def test_per_viz_failure_does_not_abort_batch():
    responses = _responses()
    responses["/api/visualizations/id-bar/data"] = RuntimeError("boom")
    client = FakeClient([TABLE_VIZ, BAR_VIZ], responses)
    result = await handler(client, {})

    assert result["exported"] == 1
    assert result["failed"] == 1
    failure = result["failures"][0]
    assert failure["visualization"] == "月度柱状图"
    assert "boom" in failure["error"]


async def test_render_failure_recorded_as_failure():
    """A visualization whose config cannot be rendered fails alone."""
    responses = _responses()
    responses["/api/visualizations/id-bar/data"] = {
        **BAR_DATA,
        "config_json": {"y_columns": ["金额"]},  # missing x_column
    }
    client = FakeClient([BAR_VIZ], responses)
    result = await handler(client, {})

    assert result["exported"] == 0
    assert result["failed"] == 1
    assert "x_column" in result["failures"][0]["error"]


async def test_export_endpoint_error_recorded_as_failure():
    responses = _responses()
    responses["/api/visualizations/id-table/export"] = (422, '{"detail": "仅表格类可视化支持 CSV 导出"}')
    client = FakeClient([TABLE_VIZ], responses)
    result = await handler(client, {})

    assert result["exported"] == 0
    assert result["failed"] == 1
    assert "422" in result["failures"][0]["error"]


async def test_unknown_requested_ids_reported_as_failures():
    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(
        client,
        {"visualization_ids": ["id-table", "missing-id"]},
    )

    assert result["exported"] == 1
    assert result["failed"] == 1
    assert result["failures"][0]["error"] == "可视化不存在"


async def test_requested_ids_filter_the_export_set():
    client = FakeClient([TABLE_VIZ, BAR_VIZ], _responses())
    result = await handler(client, {"visualization_ids": ["id-bar"]})
    assert result["exported"] == 1
    assert result["files"][0]["chart_type"] == "bar"


async def test_invalid_visualization_ids_type_returns_error():
    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(client, {"visualization_ids": "id-table"})
    assert "error" in result


async def test_backend_error_on_list_returns_error():
    from mcp_server.client import BackendError

    client = FakeClient([], {"/api/visualizations": BackendError("无法连接后端服务")})
    result = await handler(client, {})
    assert result == {"error": "无法连接后端服务"}


async def test_empty_visualization_set_exports_nothing():
    client = FakeClient([], _responses())
    result = await handler(client, {})
    assert result["exported"] == 0
    assert result["failed"] == 0
    assert result["files"] == []
