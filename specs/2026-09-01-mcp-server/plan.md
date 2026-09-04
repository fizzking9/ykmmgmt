# Phase 14 — MCP Server for External AI Agents: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

> **Revision (transport):** Groups 1–3 are implemented (backend CSV endpoint, frontend CSV switch, MCP scaffold + tool framework + HTTP client). Group 4 was originally data-centric agent-side rendering; after manual testing revealed non-deterministic output, misread chart variables, and per-run scripts, this plan replaces it with server-side matplotlib rendering (Group 4′) and removes the SKILL/prompt mechanism.
>
> **Revision (stdio → streamable HTTP):** the original design ran the MCP server on stdio, launched as a subprocess by each MCP client. It is replanned as a persistent streamable-HTTP service deployed in Docker Compose and exposed via the frpc tunnel, with an API key guarding the endpoint. Group 3's stdio entrypoint is superseded by Group 6 (HTTP transport) and Group 7 (Docker & deployment); stdio support is removed.

---

## Group 1 — Backend: CSV Export Endpoint ✅ (implemented)

1. Add `GET /api/visualizations/{id}/export` endpoint to `app/routers/visualizations.py`
   - For **table** chart type: generate CSV from the visualization data (same query logic as the `/data` endpoint), return as `StreamingResponse` with `Content-Type: text/csv; charset=utf-8` and `Content-Disposition: attachment; filename="..."`
   - CSV encoding: UTF-8 with BOM (`\ufeff`) for Excel compatibility
   - CSV content: header row from column names, data rows from the query result; datetime values formatted as ISO strings
   - For all other chart types: return 422 with a Chinese message explaining that only table visualizations support CSV export
   - Accept the same optional query params as the `/data` endpoint (`start`/`end`/`granularity`/`agg`) and apply them identically
   - Auth: same as the `/data` endpoint (requires authenticated user)
2. Write backend tests for the export endpoint
   - Table visualization returns CSV with correct headers, rows, BOM, and Content-Disposition
   - Non-table visualization returns 422
   - Time-profile params work identically to the `/data` endpoint
   - Unauthenticated request returns 401

## Group 2 — Frontend: Switch Table Export to CSV ✅ (implemented)

3. Modify the visualization list page export behavior in `VisualizationsListPage.tsx`
   - When `chart_type === "table"`: trigger a browser download from `GET /api/visualizations/{id}/export` instead of the html2canvas PNG capture flow
   - When `chart_type !== "table"`: keep the existing html2canvas PNG export unchanged
   - Show a toast indicating CSV download for table exports
4. Update frontend tests if needed to reflect the dual export behavior

## Group 3 — MCP Server Scaffold & Tool Framework ✅ (implemented; entrypoint superseded by Group 6)

5. Create `ykmmgmt/mcp_server/` package structure
   - `requirements.txt` with `mcp`, `httpx` dependencies
   - `__main__.py` — entry point (**originally stdio; superseded — Group 6 starts a streamable-HTTP server instead**) plus `cli()` for the `ykmmgmt-mcp` console script
   - `server.py` — MCP server instance setup using the `mcp` SDK (low-level `Server` with `on_*` callbacks) — tool-registration logic unchanged by the transport switchq
   - `config.py` — environment variable loading (`YKM_BACKEND_URL`, `YKM_SERVICE_USERNAME`, `YKM_SERVICE_PASSWORD`); **extended in Group 6 with `YKM_MCP_API_KEY`, `YKM_MCP_HOST`, `YKM_MCP_PORT`**
6. Implement tool registry pattern
   - `tools/__init__.py` — auto-discovers and registers all tool modules
   - Each tool module defines: `name`, `description`, `input_schema` (JSON Schema), `handler` (async function)
   - Registry collects tools and exposes them to the MCP server
7. Implement shared backend HTTP client
   - `client.py` — async httpx client with base URL from config
   - Login flow: POST `/api/auth/login` with service account credentials, store access_token cookie
   - Token refresh: on 401, re-login and retry the request once
   - All backend calls go through this client
8. Implement structured error handling
   - Tool handlers catch exceptions and return `{"error": "..."}` JSON
   - Never leak raw tracebacks to the MCP client
9. Distribution: `pyproject.toml` (package-dir `..`, console script `ykmmgmt-mcp`, package data) — pip-installable from the repo subdirectory (**the console script now launches the HTTP server; see Group 6**)

## Group 4′ — MCP Tool: export_visualizations (server-side rendering) — replaces Group 4

10. Implement `mcp_server/renderer.py` — matplotlib chart renderer
    - Input: visualization data payload (columns, rows, column_types, chart_type, config_json) + name; output: PNG bytes written to a path
    - Per-chart-type rendering honoring `config_json` required keys exactly (no guessing):
      - bar / line / scatter: `x_column` × `y_columns` (one series per y column; line sorts x when the x column is date-typed)
      - pie: `label_column` / `value_column`, sectors sorted descending
      - histogram: `columns` × `bins`
      - boxplot: `category_column` (empty → single box) × `value_column`
      - kpi_card: styled text card with `label` and the aggregated `value_column`
      - table never reaches the renderer (CSV path)
    - Chinese font handling: try `Microsoft YaHei` / `SimHei` / `PingFang SC` / `Noto Sans CJK SC` via `matplotlib.font_manager`, fall back gracefully; never tofu boxes
    - Style conventions: chart title = visualization name (Chinese), axis labels/legends from data column names, amounts to 2 decimals, deterministic output (no randomness)
    - **Styling revision (2026-09-04):** an earlier pass copied the Recharts theme onto matplotlib and read *worse* — thinned category labels broke the bar↔category correspondence, and an in-plot frameless legend sat on top of the data. Styling now follows matplotlib's own conventions for a static image (no hover/zoom/brush), keeping only the frontend palette and light grid for familiarity:
      - Y ticks: matplotlib's `ScalarFormatter` chooses precision from the tick spacing the locator derives from the data range (so 0.005-scale and 1.005-scale axes both stay distinguishable); a subclass only layers 万/亿 units on values ≥1e4. The original defect was a hardcoded `%.2f` override that discarded this
      - Categorical axes (bar, boxplot) keep EVERY label — rotate 90°/shrink past 12 categories; only continuous axes (line/scatter date slots) thin to ≤8 ticks with both ends kept
      - Legend above the axes, title clears it; left+bottom spines kept as a visible frame; 8% y headroom on line/scatter/boxplot so peaks do not hug the top edge
      - Line markers dropped beyond 60 points (static images have no hover to disambiguate dense dots)
      - Histogram bin axis uses matplotlib's own numeric ticks instead of labelling every bin edge
      - Titles/captions read from `config_json` (`title` → name fallback, `x_label`, `y_label`), dates formatted via `formatAxisDate` honoring `show_time`; scatter gained categorical-x slots and per-category marker shapes, histograms overlap bins at 50% opacity, boxplots are colored per category
    - Non-blocking: run under `matplotlib.use("Agg")`; every figure is explicitly closed after save
11. Rewrite `tools/export_visualizations.py` for the new output contract
    - Input schema unchanged: `output_dir` (required), `visualization_ids` (optional array of UUID strings)
    - **table** chart type → download CSV from `GET /api/visualizations/{id}/export`, save `{sanitized_name}.csv`
    - **all other chart types** → fetch data from `GET /api/visualizations/{id}/data`, render with `renderer.py`, save `{sanitized_name}.png`
    - File naming: sanitize visualization name (strip filesystem-unsafe characters), batch-unique suffixes on collisions
    - Return the same compact summary shape: `exported` / `failed` counts, per-file `{file, chart_type, columns, row_count}`, failed entries with name + reason — never full datasets or raw data inline
12. Remove the SKILL/prompt mechanism (superseded by server-side rendering)
    - Delete `mcp_server/SKILLS/render-visualization.md` and the SKILLS directory
    - Remove `on_list_prompts` / `on_get_prompt` / SKILL-loading code from `server.py`
    - Update the tool description (no more "参见 render-visualization 提示词" reference); drop SKILLS package-data from `pyproject.toml`
    - Update requirements: add `matplotlib` to `requirements.txt` and `pyproject.toml` dependencies

## Group 5′ — Testing (revised)

13. Renderer unit tests (`tests/test_renderer.py`)
    - One test per chart type: bar, line, pie, scatter, histogram, boxplot, kpi_card — each produces a non-empty PNG file with a PNG signature
    - Config keys are honored (e.g., pie renders `label_column`/`value_column`, not the first two columns)
    - Chinese text renders without raising (font fallback path exercised)
    - Figures are closed after rendering (no figure leakage across calls)
14. Update `export_visualizations` tool tests (`tests/test_export_visualizations.py`)
    - Table → CSV path unchanged; non-table → `.png` file with PNG signature (not JSON)
    - Summary shape: file paths, chart types, columns, row counts — no dataset values inline
    - Per-visualization render failure recorded, batch continues
    - Filename sanitization / collision suffixes still hold for `.png`
15. Update server integration tests (`tests/test_server.py`)
    - Tool discovery unchanged; prompt discovery tests removed (no prompts anymore)
    - End-to-end: mocked backend + real renderer → `.csv` + `.png` files in temp dir
    - Error propagation unchanged (structured `{"error": ...}`, no tracebacks)
16. Manual test: MCP client (WorkBuddy / Claude Desktop / Inspector) calls `export_visualizations`, gets CSV + PNG files; rendered charts are deterministic across repeated runs and match the visualization configuration

## Group 6 — Streamable HTTP Transport (replaces the stdio entrypoint) ✅ (implemented)

17. Replace the stdio entrypoint with a streamable-HTTP server
    - In `__main__.py` / `cli()`: swap `stdio_server()` for the `mcp` SDK's streamable-HTTP ASGI app, served by uvicorn
    - `server.py` tool-registration logic (`build_server`, `on_list_tools`, `on_call_tool`) is unchanged — only the transport layer changes
    - Add `uvicorn` to `requirements.txt` and `pyproject.toml`
18. Add an API-key guard on the MCP endpoint
    - Middleware/dependency that reads `Authorization: Bearer <key>` and compares it to `YKM_MCP_API_KEY`
    - Reject requests with a missing or invalid key with 401 (before any MCP method runs)
19. Extend `config.py`
    - `YKM_MCP_API_KEY` (required in production), `YKM_MCP_HOST` (default `0.0.0.0`), `YKM_MCP_PORT` (default `8001`)
20. Remove stdio support
    - Delete the `stdio_server()` code path and any stdio-specific docs/config examples
    - Update the `ykmmgmt-mcp` console script description to "starts the streamable-HTTP MCP server"

## Group 7 — Docker & Deployment ✅ (implemented)

21. Add `ykmmgmt/mcp_server/Dockerfile`
    - Python 3.12 base, install the package (and deps: `mcp`, `httpx`, `matplotlib`, `uvicorn`), run `ykmmgmt-mcp`
    - Include CJK fonts so matplotlib renders Chinese (e.g., Noto Sans CJK) — the renderer's font fallback chain must find a usable font in the container
22. Add the `mcp_server` service to `docker-compose.prod.yml`
    - `image: ${MCP_IMAGE:-ykmmgmt-mcp:dev}` with `build: ./ykmmgmt/mcp_server` fallback
    - Env: `YKM_BACKEND_URL=http://backend:8000`, `YKM_SERVICE_USERNAME`/`YKM_SERVICE_PASSWORD`, `YKM_MCP_API_KEY` (from `deploy/.env.prod`)
    - `depends_on: backend`, on the `internal` network, `restart: unless-stopped`, same logging anchor as other services
23. Add the `mcp_server` service to dev `docker-compose.yml` (pointing at the dev backend) for local testing
24. Expose via the frpc tunnel
    - Add a `[[proxies]]` entry to `deploy/frpc.toml` and `deploy/frpc.toml.example` tunneling the MCP port (`localIP = "mcp_server"`, `localPort = 8001`) to a new remote port on the cloud server
    - Document the cloud-side Nginx/port for the MCP endpoint (configured once, like the frontend)
25. CI/CD
    - Extend `.github/workflows/deploy.yml` to build and push `ghcr.io/fizzking9/ykmmgmt-mcp`
    - Extend `scripts/deploy.ps1` to pull the new image
    - Add `MCP_IMAGE` and `YKM_MCP_API_KEY` to `deploy/.env.prod.example`

## Group 8 — Testing (HTTP transport & deployment) ✅ (implemented; items 28–29 manual, pending deployment)

26. HTTP integration tests (`tests/test_server.py` or a new `test_http.py`)
    - Spin up the ASGI app in-process; connect an MCP client over streamable HTTP
    - Valid API key → tools listed, `export_visualizations` callable
    - Missing API key → 401; invalid API key → 401
27. Update existing integration tests to connect over HTTP instead of stdio
28. Manual test: MCP client (Inspector / Claude Desktop HTTP transport) connects to `http://localhost:8001/mcp` with the API key and calls `export_visualizations`
29. Manual test: `docker compose -f docker-compose.prod.yml up mcp_server` becomes healthy; an external agent reaches the MCP endpoint through the frpc tunnel and calls a tool

---

## Validation

See `validation.md` for the gate definitions (updated for streamable HTTP, API-key auth, and Docker deployment).
