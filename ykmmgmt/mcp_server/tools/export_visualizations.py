"""MCP tool: export_visualizations — server-rendered visualization export.

Returns the exports INLINE in the tool result so an external agent can
hand the plots/tables straight to its user:

- ``table`` chart type → CSV text block (via
  ``GET /api/visualizations/{id}/export``)
- all other chart types → ``image/png`` content block rendered
  server-side by the MCP server's matplotlib renderer (data fetched
  from ``GET /api/visualizations/{id}/data``)

The first block is a compact JSON summary (per-file chart type, columns,
row count); the following blocks carry the actual content, one per
exported visualization in summary order.

``output_dir`` is optional — when given (a server-local path such as
``/exports``), the files are additionally written to disk.
"""

import base64
import csv
import io
import json
import re
import tempfile
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import mcp.types as types

from mcp_server.client import BackendClient, BackendError
from mcp_server.renderer import render_chart

name = "export_visualizations"

description = (
    "导出 YKMMgmt 可视化。表格类导出为 CSV 文本，其他图表由服务端渲染为 PNG 图片"
    "（确定性输出，中文标题与标签）。内容直接内联在工具结果中返回：第一个文本块是"
    "紧凑摘要（图表类型、列名、行数），随后每个可视化对应一个内容块（图片为 base64 "
    "image 块，表格为 CSV 文本），代理可直接展示给用户。可选参数 output_dir "
    "（服务端本地路径，如 /exports）可同时把文件写到磁盘。"
)

input_schema = {
    "type": "object",
    "properties": {
        "output_dir": {
            "type": "string",
            "description": "可选。同时把导出文件写入该服务端目录（不存在时自动创建）",
        },
        "visualization_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "要导出的可视化 ID 列表（UUID）；省略时导出全部可视化",
        },
    },
}

_INVALID_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|\r\n\t]')


def sanitize_filename(name: str) -> str:
    """Strip filesystem-unsafe characters from a visualization name."""
    cleaned = _INVALID_FILENAME_CHARS.sub("_", name).strip().strip(".")
    return cleaned or "未命名"


def _unique_path(directory: Path, base: str, ext: str, used: set[str]) -> Path:
    """Build a file path that does not collide within the current batch."""
    candidate = f"{base}{ext}"
    if candidate not in used:
        used.add(candidate)
        return directory / candidate
    # Same sanitized name twice — disambiguate with a numeric suffix
    n = 2
    while f"{base}_{n}{ext}" in used:
        n += 1
    candidate = f"{base}_{n}{ext}"
    used.add(candidate)
    return directory / candidate


async def _export_one(
    client: BackendClient,
    viz: dict[str, Any],
    output_dir: Path,
    used_names: set[str],
) -> tuple[dict[str, Any], types.TextContent | types.ImageContent]:
    """Export a single visualization; raises on failure (caller records it)."""
    viz_id = viz["id"]
    viz_name = viz.get("name", "")
    chart_type = viz.get("chart_type", "")

    if chart_type == "table":
        resp = await client.request("GET", f"/api/visualizations/{viz_id}/export")
        if resp.status_code != 200:
            raise BackendError(f"CSV 导出失败 (HTTP {resp.status_code}): {resp.text[:200]}")
        path = _unique_path(output_dir, sanitize_filename(viz_name), ".csv", used_names)
        path.write_bytes(resp.content)
        # Columns and row count from the CSV itself (header + data lines)
        rows = list(csv.reader(io.StringIO(resp.text.lstrip("\ufeff"))))
        columns = rows[0] if rows else []
        row_count = max(0, len(rows) - 1)
        entry = {
            "file": str(path),
            "chart_type": chart_type,
            "columns": columns,
            "row_count": row_count,
        }
        # Inline the CSV text (BOM stripped) so the agent can analyze it
        block = types.TextContent(type="text", text=resp.text.lstrip("\ufeff"))
    else:
        data = await client.get_json(f"/api/visualizations/{viz_id}/data")
        path = _unique_path(output_dir, sanitize_filename(viz_name), ".png", used_names)
        render_chart(viz_name, data, path)
        png_bytes = path.read_bytes()
        columns = data["columns"]
        row_count = len(data["rows"])
        entry = {
            "file": str(path),
            "chart_type": chart_type,
            "columns": columns,
            "row_count": row_count,
        }
        block = types.ImageContent(
            type="image",
            data=base64.b64encode(png_bytes).decode("ascii"),
            mimeType="image/png",
        )

    return entry, block


async def handler(
    client: BackendClient, arguments: dict[str, Any]
) -> dict[str, Any] | list[types.TextContent | types.ImageContent]:
    """Export visualizations and return inline content blocks.

    The first block is the compact JSON summary; each exported
    visualization follows as an image (charts) or CSV text (tables)
    block. Errors are returned as a plain ``{"error": ...}`` dict.
    """
    output_dir = arguments.get("output_dir")
    if output_dir is not None and (not isinstance(output_dir, str) or not output_dir):
        return {"error": "参数 output_dir 必须是非空字符串"}

    requested_ids = arguments.get("visualization_ids")
    if requested_ids is not None and (
        not isinstance(requested_ids, list) or not all(isinstance(i, str) for i in requested_ids)
    ):
        return {"error": "参数 visualization_ids 必须是 UUID 字符串数组"}

    # Without output_dir the files are rendered into a throwaway temp dir
    # and only the inline content survives.
    if output_dir is not None:
        try:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            return {"error": f"无法创建输出目录 '{output_dir}': {e}"}
        dest_ctx = nullcontext(out)
    else:
        dest_ctx = tempfile.TemporaryDirectory()

    try:
        viz_list = await client.get_json("/api/visualizations")
    except BackendError as e:
        return {"error": str(e)}

    failures: list[dict[str, str]] = []
    if requested_ids is not None:
        requested = set(requested_ids)
        by_id = {v["id"]: v for v in viz_list}
        for missing_id in sorted(requested - set(by_id)):
            failures.append(
                {
                    "visualization": missing_id,
                    "id": missing_id,
                    "error": "可视化不存在",
                }
            )
        targets = [by_id[i] for i in requested_ids if i in by_id]
    else:
        targets = list(viz_list)

    files: list[dict[str, Any]] = []
    blocks: list[types.TextContent | types.ImageContent] = []
    used_names: set[str] = set()
    with dest_ctx as dest:
        for viz in targets:
            try:
                entry, block = await _export_one(client, viz, Path(dest), used_names)
                files.append(entry)
                blocks.append(block)
            except Exception as e:
                # Per-visualization failures (backend errors, RenderError, …)
                # never abort the batch
                failures.append(
                    {
                        "visualization": viz.get("name", ""),
                        "id": viz.get("id", ""),
                        "error": str(e) or type(e).__name__,
                    }
                )

    summary: dict[str, Any] = {
        "exported": len(files),
        "failed": len(failures),
        "files": files,
        "failures": failures,
    }
    if output_dir is not None:
        summary["output_dir"] = str(out)
    else:
        # Without a destination the temp paths are meaningless — drop them
        for entry in files:
            entry.pop("file", None)
    return [types.TextContent(type="text", text=json.dumps(summary, ensure_ascii=False)), *blocks]
