"""Integration tests: MCP server + ClientSession over streamable HTTP.

The real ASGI app (API-key middleware + streamable-HTTP session manager)
is exercised in-process with the real matplotlib renderer and a mocked
backend transport — the same code path an external agent uses against
``http://<host>:8001/mcp`` with a Bearer API key.
"""

import json

from http_support import PNG_SIGNATURE, mcp_http_session
from mcp_server.files import default_store


async def _tool_payload(result) -> dict:
    """Decode the single TextContent block of a CallToolResult as JSON."""
    assert len(result.content) == 1
    return json.loads(result.content[0].text)


def _stored_file(url: str):
    """Resolve a download URL from a tool result to a local file path."""
    store = default_store()
    path_part = url.split("?", 1)[0]
    batch_id, filename = path_part.rsplit("/", 2)[1:]
    return store.file_path(batch_id, filename)


# ── Tool discovery ───────────────────────────────────────────────────────────


async def test_client_discovers_export_visualizations_tool():
    async with mcp_http_session() as session:
        result = await session.list_tools()
        tools = {t.name: t for t in result.tools}
    assert "export_visualizations" in tools

    tool = tools["export_visualizations"]
    assert tool.description
    assert tool.input_schema["type"] == "object"
    assert tool.input_schema.get("required") is None
    assert "visualization_ids" in tool.input_schema["properties"]


async def test_unknown_tool_returns_structured_error():
    async with mcp_http_session() as session:
        result = await session.call_tool("no_such_tool", {})
        payload = await _tool_payload(result)
    assert "未知工具" in payload["error"]


# ── End-to-end tool call ─────────────────────────────────────────────────────


async def test_export_visualizations_returns_download_urls():
    async with mcp_http_session() as session:
        result = await session.call_tool("export_visualizations", {})
        payload = await _tool_payload(result)

    assert payload["exported"] == 2
    assert payload["failed"] == 0
    assert {f["chart_type"] for f in payload["files"]} == {"table", "bar"}
    assert all(f["url"].startswith("/mcp/files/") for f in payload["files"])

    # The CSV file is stored intact (BOM preserved)
    csv_entry = next(f for f in payload["files"] if f["chart_type"] == "table")
    csv_path = _stored_file(csv_entry["url"])
    csv_text = csv_path.read_text(encoding="utf-8")
    assert csv_text.startswith("\ufeff")
    assert "A001" in csv_text

    # The bar chart is rendered server-side to a real PNG
    png_entry = next(f for f in payload["files"] if f["chart_type"] == "bar")
    png_path = _stored_file(png_entry["url"])
    png_bytes = png_path.read_bytes()
    assert png_bytes.startswith(PNG_SIGNATURE)
    assert len(png_bytes) > 100

    # Compact summary only — no dataset values inlined
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "A001" not in serialized
    assert "2026-06" not in serialized


async def test_export_with_id_filter():
    async with mcp_http_session() as session:
        result = await session.call_tool(
            "export_visualizations",
            {"visualization_ids": ["id-bar"]},
        )
        payload = await _tool_payload(result)
    assert payload["exported"] == 1
    assert payload["files"][0]["chart_type"] == "bar"


# ── Error propagation ────────────────────────────────────────────────────────


async def test_backend_auth_failure_returns_structured_error():
    async with mcp_http_session(login_status=401) as session:
        result = await session.call_tool("export_visualizations", {})
        payload = await _tool_payload(result)
    assert "登录失败" in payload["error"]
    assert "Traceback" not in payload["error"]
