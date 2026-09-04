"""Integration tests: MCP server + ClientSession over streamable HTTP.

The real ASGI app (API-key middleware + streamable-HTTP session manager)
is exercised in-process with the real matplotlib renderer and a mocked
backend transport — the same code path an external agent uses against
``http://<host>:8001/mcp`` with a Bearer API key.
"""

import base64
import json

from http_support import PNG_SIGNATURE, mcp_http_session


async def _tool_payload(result) -> dict:
    """Decode the single TextContent block of a CallToolResult as JSON."""
    assert len(result.content) == 1
    return json.loads(result.content[0].text)


async def _export_payload(result) -> tuple[dict, list]:
    """Split an export result into (summary JSON, remaining content blocks)."""
    assert result.content[0].type == "text"
    return json.loads(result.content[0].text), result.content[1:]


# ── Tool discovery ───────────────────────────────────────────────────────────


async def test_client_discovers_export_visualizations_tool():
    async with mcp_http_session() as session:
        result = await session.list_tools()
        tools = {t.name: t for t in result.tools}
    assert "export_visualizations" in tools

    tool = tools["export_visualizations"]
    assert tool.description
    assert tool.input_schema["type"] == "object"
    assert tool.input_schema.get("required") is None  # output_dir is optional
    assert "output_dir" in tool.input_schema["properties"]
    assert "visualization_ids" in tool.input_schema["properties"]


async def test_unknown_tool_returns_structured_error():
    async with mcp_http_session() as session:
        result = await session.call_tool("no_such_tool", {})
        payload = await _tool_payload(result)
    assert "未知工具" in payload["error"]


# ── End-to-end tool call ─────────────────────────────────────────────────────


async def test_export_visualizations_creates_csv_and_png_files(tmp_path):
    async with mcp_http_session() as session:
        result = await session.call_tool("export_visualizations", {"output_dir": str(tmp_path)})
        payload, blocks = await _export_payload(result)

    assert payload["exported"] == 2
    assert payload["failed"] == 0
    files = {f["file"] for f in payload["files"]}
    assert files == {str(tmp_path / "退款明细表.csv"), str(tmp_path / "月度柱状图.png")}

    csv_text = (tmp_path / "退款明细表.csv").read_text(encoding="utf-8")
    assert csv_text.startswith("\ufeff")
    assert "A001" in csv_text

    # The bar chart is rendered server-side to a real PNG
    png_bytes = (tmp_path / "月度柱状图.png").read_bytes()
    assert png_bytes.startswith(PNG_SIGNATURE)
    assert len(png_bytes) > 100

    # The exports are also inlined: CSV text block + base64 image block
    assert [b.type for b in blocks] == ["text", "image"]
    assert blocks[0].text == csv_text.lstrip("\ufeff")
    assert blocks[1].mime_type == "image/png"
    assert base64.b64decode(blocks[1].data).startswith(PNG_SIGNATURE)

    # The summary JSON itself stays compact — no dataset values in it
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "A001" not in serialized
    assert "2026-06" not in serialized


async def test_export_with_id_filter(tmp_path):
    async with mcp_http_session() as session:
        result = await session.call_tool(
            "export_visualizations",
            {"output_dir": str(tmp_path), "visualization_ids": ["id-bar"]},
        )
        payload, blocks = await _export_payload(result)
    assert payload["exported"] == 1
    assert (tmp_path / "月度柱状图.png").exists()
    assert not (tmp_path / "退款明细表.csv").exists()
    assert [b.type for b in blocks] == ["image"]


# ── Error propagation ────────────────────────────────────────────────────────


async def test_backend_auth_failure_returns_structured_error(tmp_path):
    async with mcp_http_session(login_status=401) as session:
        result = await session.call_tool(
            "export_visualizations",
            {"output_dir": str(tmp_path)},
        )
        payload = await _tool_payload(result)
    assert "登录失败" in payload["error"]
    assert "Traceback" not in payload["error"]
