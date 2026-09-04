"""Tests for the export_visualizations tool (inline content, CSV/PNG paths, errors)."""

import base64
import json
from typing import Any

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


async def _run(client, args: dict) -> tuple[dict, list]:
    """Call the handler; split the summary block from the content blocks."""
    out = await handler(client, args)
    assert not isinstance(out, dict), f"unexpected error result: {out}"
    assert out[0].type == "text"
    return json.loads(out[0].text), out[1:]


# ── Path selection: table → CSV, other → PNG ────────────────────────────────


async def test_table_viz_writes_csv_file(tmp_path):
    client = FakeClient([TABLE_VIZ], _responses())
    result, blocks = await _run(client, {"output_dir": str(tmp_path)})

    assert result["exported"] == 1
    assert result["failed"] == 0
    entry = result["files"][0]
    assert entry["chart_type"] == "table"
    assert entry["columns"] == ["订单号", "金额"]
    assert entry["row_count"] == 2
    assert entry["file"].endswith("退款明细表.csv")
    content = (tmp_path / "退款明细表.csv").read_text(encoding="utf-8")
    assert content.startswith("\ufeff")  # BOM preserved byte-for-byte
    # The CSV is also inlined as a text block (BOM stripped for parsing)
    assert len(blocks) == 1 and blocks[0].type == "text"
    assert blocks[0].text == content.lstrip("\ufeff")


async def test_non_table_viz_writes_rendered_png(tmp_path):
    client = FakeClient([BAR_VIZ], _responses())
    result, blocks = await _run(client, {"output_dir": str(tmp_path)})

    entry = result["files"][0]
    assert entry["chart_type"] == "bar"
    assert entry["row_count"] == 2
    assert entry["columns"] == ["月份", "金额"]
    assert entry["file"].endswith("月度柱状图.png")
    _assert_png_file(tmp_path / "月度柱状图.png")
    # No raw-data JSON file is written anymore
    assert not (tmp_path / "月度柱状图.json").exists()
    # The rendered chart is inlined as a base64 PNG image block
    assert len(blocks) == 1 and blocks[0].type == "image"
    assert blocks[0].mime_type == "image/png"
    assert base64.b64decode(blocks[0].data).startswith(PNG_SIGNATURE)


# ── Filename sanitization ────────────────────────────────────────────────────


def test_sanitize_filename_strips_unsafe_characters():
    assert sanitize_filename('报表/2026:Q3*"存"在?') == "报表_2026_Q3__存_在_"
    assert sanitize_filename("  正常名称  ") == "正常名称"
    assert sanitize_filename("..") == "未命名"


async def test_unsafe_name_produces_safe_file(tmp_path):
    viz = {**TABLE_VIZ, "name": "销售/华北:2026"}
    client = FakeClient([viz], _responses())
    result, _ = await _run(client, {"output_dir": str(tmp_path)})
    assert result["exported"] == 1
    assert (tmp_path / "销售_华北_2026.csv").exists()


async def test_duplicate_sanitized_names_get_unique_suffixes(tmp_path):
    vizzes = [
        {**BAR_VIZ, "id": "id-1", "name": "报表"},
        {**BAR_VIZ, "id": "id-2", "name": "报表"},
    ]
    responses = {
        "/api/visualizations/id-1/data": BAR_DATA,
        "/api/visualizations/id-2/data": BAR_DATA,
    }
    client = FakeClient(vizzes, responses)
    result, blocks = await _run(client, {"output_dir": str(tmp_path)})

    assert result["exported"] == 2
    files = sorted(f["file"] for f in result["files"])
    assert files[0].endswith("报表.png")
    assert files[1].endswith("报表_2.png")
    assert len(blocks) == 2  # one image block per export, in summary order


# ── Inline content delivery ──────────────────────────────────────────────


async def test_no_output_dir_returns_inline_content_only():
    """output_dir is optional — content blocks are returned without files."""
    client = FakeClient([TABLE_VIZ, BAR_VIZ], _responses())
    result, blocks = await _run(client, {})

    assert result["exported"] == 2
    assert "output_dir" not in result
    assert "file" not in result["files"][0]
    assert [b.type for b in blocks] == ["text", "image"]  # CSV text + PNG image


async def test_summary_block_itself_stays_compact(tmp_path):
    """The summary JSON never carries dataset values (blocks do, by design)."""
    client = FakeClient([TABLE_VIZ, BAR_VIZ], _responses())
    out = await handler(client, {"output_dir": str(tmp_path)})
    summary_text = out[0].text

    assert "A001" not in summary_text  # no CSV cell values in the summary
    assert "2026-06" not in summary_text  # no chart row values in the summary
    assert "exported" in summary_text


# ── Error handling ──────────────────────────────────────────────────────────


async def test_per_viz_failure_does_not_abort_batch(tmp_path):
    responses = _responses()
    responses["/api/visualizations/id-bar/data"] = RuntimeError("boom")
    client = FakeClient([TABLE_VIZ, BAR_VIZ], responses)
    result, blocks = await _run(client, {"output_dir": str(tmp_path)})

    assert result["exported"] == 1
    assert result["failed"] == 1
    failure = result["failures"][0]
    assert failure["visualization"] == "月度柱状图"
    assert "boom" in failure["error"]
    assert len(blocks) == 1  # only the successful export is inlined


async def test_render_failure_recorded_as_failure(tmp_path):
    """A visualization whose config cannot be rendered fails alone."""
    responses = _responses()
    responses["/api/visualizations/id-bar/data"] = {
        **BAR_DATA,
        "config_json": {"y_columns": ["金额"]},  # missing x_column
    }
    client = FakeClient([BAR_VIZ], responses)
    result, _ = await _run(client, {"output_dir": str(tmp_path)})

    assert result["exported"] == 0
    assert result["failed"] == 1
    assert "x_column" in result["failures"][0]["error"]


async def test_export_endpoint_error_recorded_as_failure(tmp_path):
    responses = _responses()
    responses["/api/visualizations/id-table/export"] = (422, '{"detail": "仅表格类可视化支持 CSV 导出"}')
    client = FakeClient([TABLE_VIZ], responses)
    result, _ = await _run(client, {"output_dir": str(tmp_path)})

    assert result["exported"] == 0
    assert result["failed"] == 1
    assert "422" in result["failures"][0]["error"]


async def test_unknown_requested_ids_reported_as_failures(tmp_path):
    client = FakeClient([TABLE_VIZ], _responses())
    result, _ = await _run(
        client,
        {"output_dir": str(tmp_path), "visualization_ids": ["id-table", "missing-id"]},
    )

    assert result["exported"] == 1
    assert result["failed"] == 1
    assert result["failures"][0]["error"] == "可视化不存在"
    assert (tmp_path / "退款明细表.csv").exists()


async def test_requested_ids_filter_the_export_set(tmp_path):
    client = FakeClient([TABLE_VIZ, BAR_VIZ], _responses())
    result, _ = await _run(
        client,
        {"output_dir": str(tmp_path), "visualization_ids": ["id-bar"]},
    )
    assert result["exported"] == 1
    assert result["files"][0]["chart_type"] == "bar"
    assert not (tmp_path / "退款明细表.csv").exists()


async def test_invalid_output_dir_returns_error(tmp_path):
    # A path occupied by a regular file cannot be used as a directory
    blocker = tmp_path / "blocker"
    blocker.write_text("occupied", encoding="utf-8")

    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(client, {"output_dir": str(blocker)})
    assert "error" in result
    assert "无法创建输出目录" in result["error"]


async def test_invalid_visualization_ids_type_returns_error(tmp_path):
    client = FakeClient([TABLE_VIZ], _responses())
    result = await handler(
        client,
        {"output_dir": str(tmp_path), "visualization_ids": "id-table"},
    )
    assert "error" in result


async def test_backend_error_on_list_returns_error(tmp_path):
    from mcp_server.client import BackendError

    client = FakeClient([], {"/api/visualizations": BackendError("无法连接后端服务")})
    result = await handler(client, {"output_dir": str(tmp_path)})
    assert result == {"error": "无法连接后端服务"}


async def test_empty_visualization_set_exports_nothing(tmp_path):
    client = FakeClient([], _responses())
    result, blocks = await _run(client, {"output_dir": str(tmp_path)})
    assert result["exported"] == 0
    assert result["failed"] == 0
    assert result["files"] == []
    assert blocks == []
