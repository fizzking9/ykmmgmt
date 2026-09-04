"""MCP tool: export_visualizations — server-rendered visualization export.

Writes visualization exports to files on disk with deterministic output:

- ``table`` chart type → CSV via ``GET /api/visualizations/{id}/export``
- all other chart types → PNG chart image rendered server-side by the
  MCP server's matplotlib renderer (data fetched from
  ``GET /api/visualizations/{id}/data``)

The tool result is a compact summary (file paths + chart type, columns,
row count) — raw chart data never enters the agent's context.
"""

import csv
import io
import re
from pathlib import Path
from typing import Any

from mcp_server.client import BackendClient, BackendError
from mcp_server.renderer import render_chart

name = "export_visualizations"

description = (
    "导出 YKMMgmt 可视化到本地文件。表格类可视化导出为 CSV 文件，"
    "其他图表类型由服务端渲染为 PNG 图片文件（确定性输出，中文标题与标签）。"
    "返回紧凑摘要（文件路径、图表类型、列名、行数），不内联完整数据。"
)

input_schema = {
    "type": "object",
    "properties": {
        "output_dir": {
            "type": "string",
            "description": "导出文件的输出目录（不存在时自动创建）",
        },
        "visualization_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": "要导出的可视化 ID 列表（UUID）；省略时导出全部可视化",
        },
    },
    "required": ["output_dir"],
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
) -> dict[str, Any]:
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
    else:
        data = await client.get_json(f"/api/visualizations/{viz_id}/data")
        path = _unique_path(output_dir, sanitize_filename(viz_name), ".png", used_names)
        render_chart(viz_name, data, path)
        columns = data["columns"]
        row_count = len(data["rows"])

    return {
        "file": str(path),
        "chart_type": chart_type,
        "columns": columns,
        "row_count": row_count,
    }


async def handler(client: BackendClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Export visualizations to files and return a compact summary."""
    output_dir = arguments.get("output_dir")
    if not isinstance(output_dir, str) or not output_dir:
        return {"error": "缺少必需参数 output_dir"}

    requested_ids = arguments.get("visualization_ids")
    if requested_ids is not None and (
        not isinstance(requested_ids, list) or not all(isinstance(i, str) for i in requested_ids)
    ):
        return {"error": "参数 visualization_ids 必须是 UUID 字符串数组"}

    try:
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"error": f"无法创建输出目录 '{output_dir}': {e}"}

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
    used_names: set[str] = set()
    for viz in targets:
        try:
            files.append(await _export_one(client, viz, out, used_names))
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

    return {
        "output_dir": str(out),
        "exported": len(files),
        "failed": len(failures),
        "files": files,
        "failures": failures,
    }
