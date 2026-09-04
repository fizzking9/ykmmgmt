"""MCP server instance setup — registers tools from the file-based registry.

Uses the low-level ``mcp.server.Server`` so tools keep their explicit
``input_schema`` JSON Schema (the registry contract) instead of schemas
derived from function signatures. All tool results are JSON — errors come
back as ``{"error": "..."}``, never raw tracebacks.
"""

import json
from typing import Any

import httpx
import mcp.types as types
from mcp.server import Server

from mcp_server.client import BackendClient, BackendError
from mcp_server.config import Settings, load_settings
from mcp_server.tools import ToolSpec, discover_tools


def build_server(
    settings: Settings | None = None,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Server:
    """Assemble the MCP server from the tool registry.

    ``settings``/``transport`` are injection points for tests; production
    reads environment variables and talks to the real backend over HTTP.
    """
    settings = settings or load_settings()
    tools = discover_tools()
    tools_by_name = {spec.name: spec for spec in tools}

    async def on_list_tools(ctx, params) -> types.ListToolsResult:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=spec.name,
                    description=spec.description,
                    input_schema=spec.input_schema,
                )
                for spec in tools
            ]
        )

    async def on_call_tool(ctx, params) -> types.CallToolResult:
        return await _call_tool(tools_by_name, settings, transport, params)

    return Server(
        "ykmmgmt",
        on_list_tools=on_list_tools,
        on_call_tool=on_call_tool,
    )


async def _call_tool(
    tools_by_name: dict[str, ToolSpec],
    settings: Settings,
    transport: httpx.AsyncBaseTransport | None,
    params: types.CallToolRequestParams,
) -> types.CallToolResult:
    """Dispatch one tools/call request with structured error handling."""
    spec = tools_by_name.get(params.name)
    if spec is None:
        return _error_result(f"未知工具: {params.name}")

    arguments: dict[str, Any] = dict(params.arguments or {})
    async with BackendClient(
        settings.backend_url,
        settings.service_username,
        settings.service_password,
        transport=transport,
    ) as client:
        try:
            result = await spec.handler(client, arguments)
        except BackendError as e:
            result = {"error": str(e)}
        except Exception as e:
            # Never leak raw tracebacks to the MCP client
            result = {"error": f"{type(e).__name__}: {e}"}
    if isinstance(result, list):
        # A list means ready-made content blocks (summary + inline
        # images/CSV from export_visualizations) — pass through as-is.
        return types.CallToolResult(content=result, is_error=False)
    return _json_result(result)


def _json_result(result: dict[str, Any]) -> types.CallToolResult:
    is_error = isinstance(result, dict) and "error" in result
    text = json.dumps(result, ensure_ascii=False)
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=text)],
        is_error=is_error,
    )


def _error_result(message: str) -> types.CallToolResult:
    """Structured error payload — a JSON body, never a raw traceback."""
    return _json_result({"error": message})
