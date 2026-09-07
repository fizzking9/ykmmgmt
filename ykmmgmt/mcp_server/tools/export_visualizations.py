"""MCP tool: export_visualizations — server-rendered visualization export.

Exports are written to a per-call batch directory inside the MCP
server's file store and returned as **signed, expiring download URLs**:

- ``table`` chart type → CSV file (via
  ``GET /api/visualizations/{id}/export``)
- all other chart types → PNG chart image rendered server-side by the
  MCP server's matplotlib renderer (data fetched from
  ``GET /api/visualizations/{id}/data``)

The tool result is a compact summary (file names, download URLs, chart
type, columns, row count). Anyone with the URL can download the file in
a browser without extra headers; URLs are unforgeable (HMAC keyed with
the MCP API key) and expire after ``YKM_MCP_DOWNLOAD_TTL`` seconds
(default 24 h).
"""

import csv
import io
import re
from pathlib import Path
from typing import Any

from mcp_server.client import BackendClient, BackendError
from mcp_server.config import load_settings
from mcp_server.files import default_store
from mcp_server.renderer import render_chart

name = "export_visualizations"

description = (
    "导出 YKMMgmt 可视化。表格类导出为 CSV 文件，其他图表由服务端渲染为 PNG 图片"
    "（确定性输出，中文标题与标签）。返回紧凑摘要，其中每个文件附带一个可直接在"
    "浏览器打开的下载 URL（签名防伪造，默认 24 小时后过期）。代理把 URL 告诉"
    "用户即可下载文件。"
)

input_schema = {
    "type": "object",
    "properties": {
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
    batch_dir: Path,
    used_names: set[str],
) -> dict[str, Any]:
    """Export a single visualization into the batch dir; raises on failure."""
    viz_id = viz["id"]
    viz_name = viz.get("name", "")
    chart_type = viz.get("chart_type", "")

    if chart_type == "table":
        resp = await client.request("GET", f"/api/visualizations/{viz_id}/export")
        if resp.status_code != 200:
            raise BackendError(f"CSV 导出失败 (HTTP {resp.status_code}): {resp.text[:200]}")
        path = _unique_path(batch_dir, sanitize_filename(viz_name), ".csv", used_names)
        path.write_bytes(resp.content)
        # Columns and row count from the CSV itself (header + data lines)
        rows = list(csv.reader(io.StringIO(resp.text.lstrip("\ufeff"))))
        columns = rows[0] if rows else []
        row_count = max(0, len(rows) - 1)
    else:
        data = await client.get_json(f"/api/visualizations/{viz_id}/data")
        path = _unique_path(batch_dir, sanitize_filename(viz_name), ".png", used_names)
        render_chart(viz_name, data, path)
        columns = data["columns"]
        row_count = len(data["rows"])

    return {
        "file": path.name,
        "chart_type": chart_type,
        "columns": columns,
        "row_count": row_count,
    }


async def handler(client: BackendClient, arguments: dict[str, Any]) -> dict[str, Any]:
    """Export visualizations to the file store and return download URLs."""
    requested_ids = arguments.get("visualization_ids")
    if requested_ids is not None and (
        not isinstance(requested_ids, list) or not all(isinstance(i, str) for i in requested_ids)
    ):
        return {"error": "参数 visualization_ids 必须是 UUID 字符串数组"}

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

    store = default_store()
    store.cleanup()  # prune batches whose URLs have expired
    batch_id, batch_dir = store.create_batch()

    files: list[dict[str, Any]] = []
    used_names: set[str] = set()
    for viz in targets:
        try:
            files.append(await _export_one(client, viz, batch_dir, used_names))
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

    public_url = load_settings().public_url
    for entry in files:
        entry["url"] = store.build_url(public_url, batch_id, entry["file"])

    return {
        "exported": len(files),
        "failed": len(failures),
        "files": files,
        "failures": failures,
    }
