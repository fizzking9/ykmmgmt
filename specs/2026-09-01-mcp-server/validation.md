# Phase 14 — MCP Server for External AI Agents: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Backend tests pass

```bash
cd ykmmgmt/backend
python -m pytest tests/ -v --tb=short
```

**Expected:** All tests pass, including new tests for the `/api/visualizations/{id}/export` endpoint. No failures, no errors.

---

## Gate 2 — Backend linting clean

```bash
cd ykmmgmt/backend
python -m ruff check app/ tests/
python -m ruff format --check app/ tests/
```

**Expected:** No linting errors, no formatting issues.

---

## Gate 3 — Frontend tests pass

```bash
cd ykmmgmt/frontend
npx vitest run
```

**Expected:** All tests pass. Table export tests reflect the new CSV download behavior.

---

## Gate 4 — Frontend linting & type-check clean

```bash
cd ykmmgmt/frontend
npx eslint src/ --max-warnings 0
npx tsc --noEmit
```

**Expected:** No ESLint errors, no TypeScript errors.

---

## Gate 5 — CSV export endpoint works correctly

Manual test via API client (or curl with auth cookie):

1. Create a table-type visualization via the UI or API
2. `GET /api/visualizations/{id}/export`
3. Verify response headers: `Content-Type: text/csv; charset=utf-8`, `Content-Disposition: attachment`
4. Open the downloaded file in Excel — verify Chinese characters display correctly (BOM present)
5. `GET /api/visualizations/{id}/export` on a non-table visualization (e.g., bar chart)

**Expected:** Table visualization returns a valid CSV file with correct headers and data rows. Non-table returns 422 with a Chinese error message.

---

## Gate 6 — Frontend table export downloads CSV

1. Open the Visualizations list page in the browser
2. Click 导出 on a table-type visualization
3. Verify a CSV file downloads (not PNG)
4. Click 导出 on a non-table visualization (e.g., bar chart)
5. Verify a PNG file downloads (existing behavior preserved)

**Expected:** Table exports produce CSV files; non-table exports still produce PNG files. Toast messages reflect the correct export type.

---

## Gate 7 — MCP server starts as an HTTP service and lists tools

The MCP server runs as a persistent streamable-HTTP service (not stdio).

```bash
# In the production stack
docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up mcp_server

# Or locally (dev), from the directory that CONTAINS the mcp_server package
cd ykmmgmt
python -m mcp_server   # starts the HTTP server on YKM_MCP_HOST:YKM_MCP_PORT (default 0.0.0.0:8001)
```

Connect an MCP client (Inspector / Claude Desktop HTTP transport) to the endpoint with the API key:

```json
{
  "mcpServers": {
    "ykmmgmt": {
      "url": "http://localhost:8001/mcp",
      "headers": {
        "Authorization": "Bearer <YKM_MCP_API_KEY>"
      }
    }
  }
}
```

### Distribution — Docker image (for the production stack)

The primary deployment is the `mcp_server` Docker service built from `ykmmgmt/mcp_server/Dockerfile` and pushed to GHCR (`ghcr.io/fizzking9/ykmmgmt-mcp`). The pip-installable package (`ykmmgmt/mcp_server/pyproject.toml`, console script `ykmmgmt-mcp`) is retained for the tool code; the console script now starts the HTTP server (not stdio).

**Expected:** The service starts without errors and listens on the configured host/port. The MCP client connects over streamable HTTP with the API key and discovers the `export_visualizations` tool (correct name, description, input schema). No prompts are exposed (the SKILL/prompt mechanism was removed with the agent-side-rendering decision). No stdio code path remains.

Automated coverage (no MCP client needed): `cd ykmmgmt/mcp_server && python -m pytest tests/ -q` — tool discovery, renderer unit tests, HTTP integration tests (including API-key enforcement), and end-to-end `export_visualizations` against a mocked backend, plus registry/client/tool unit tests.

---

## Gate 7b — MCP endpoint enforces the API key

1. Call the MCP endpoint without an `Authorization` header
2. Call it with `Authorization: Bearer wrong-key`
3. Call it with `Authorization: Bearer <YKM_MCP_API_KEY>`

**Expected:** Missing key → 401; wrong key → 401; correct key → the MCP handshake succeeds and tools are listed. The 401 is returned before any MCP method runs.

---

## Gate 7c — Docker service healthy and reachable via the frpc tunnel

1. `docker compose -f docker-compose.prod.yml --env-file deploy/.env.prod up mcp_server` — the container becomes healthy
2. Verify the frpc `[[proxies]]` entry for the MCP port is loaded (`docker logs ykmmgmt-prod-frpc` shows the proxy started)
3. From an external machine, connect an MCP client to the cloud entry's MCP endpoint (through the tunnel) with the API key and call a tool

**Expected:** The `mcp_server` container runs and reaches the backend over the internal network. External agents reach the MCP endpoint through the frpc tunnel and can invoke tools with a valid API key.

---

## Gate 8 — MCP export_visualizations tool produces CSV and PNG files

1. Ensure the backend is running and has at least one table visualization and one non-table visualization (e.g., a bar chart)
2. Via MCP client (over the HTTP connection), call `export_visualizations` with `output_dir` set to a temp directory
3. Check the output directory and the tool's summary response
4. Call the tool a second time with the same visualizations

**Expected:** Table visualizations produce `.csv` files; non-table visualizations produce `.png` chart images that match their configuration (correct x/y columns, labels, Chinese titles — no tofu boxes) and are byte-stable (or visually identical) across repeated runs — deterministic server-side rendering. The tool returns a compact summary with `exported` count, `failed` count, and per-file previews (file path, chart type, columns, row count) — no full datasets and no raw chart data inline. Files are readable and correctly named.

**Aggregation parity (critical):** the backend `/data` endpoint returns RAW view rows — the UI aggregates client-side before Recharts draws. The MCP renderer must replicate that pipeline, so exported PNGs must show the same aggregated shape users see in the app: categorical-x bars aggregate per category (`config.aggregation`, default SUM), date-x line/bar charts bucket by `time_granularity` and apply `time_aggregation`, `group_by_column` splits into per-category series (top-10 + 其他）， pie charts group by label (top-8 slices + 其他). A raw-row plot (one bar/slice per transaction row) is a defect.

---

## Gate 9 — MCP server handles errors gracefully

1. Call `export_visualizations` with an invalid `output_dir` (e.g., a path that doesn't exist and can't be created)
2. Call `export_visualizations` when the backend is not running
3. Call `export_visualizations` with invalid service account credentials

**Expected:** All error cases return `{"error": "..."}` JSON with a human-readable message. No raw Python tracebacks are exposed to the MCP client.

---

## Merge Checklist

- [ ] All gates pass on a clean checkout
- [ ] Backend: new `/api/visualizations/{id}/export` endpoint returns CSV for table charts, 422 for others
- [ ] Frontend: table export button downloads CSV; non-table export still produces PNG
- [ ] MCP server: runs as a persistent streamable-HTTP service, discovers tools, authenticates with the backend via service account; no stdio code path remains
- [ ] MCP endpoint: enforces the API key — missing/invalid `Authorization: Bearer` rejected with 401
- [ ] Deployment: `ykmmgmt/mcp_server/Dockerfile` builds; `mcp_server` service runs in `docker-compose.prod.yml` (GHCR image with `build:` fallback) and reaches the backend over the internal network
- [ ] Exposure: frpc `[[proxies]]` entry tunnels the MCP port; external agents reach the endpoint through the tunnel
- [ ] CI/CD: `deploy.yml` builds/pushes `ghcr.io/fizzking9/ykmmgmt-mcp`; `scripts/deploy.ps1` pulls it; `deploy/.env.prod.example` documents `MCP_IMAGE` and `YKM_MCP_API_KEY`
- [ ] MCP tool: `export_visualizations` writes CSV files (tables) and server-rendered PNG chart images (other chart types) to the output directory
- [ ] Renderer: honors `config_json` required keys per chart type, Chinese text renders correctly (no tofu, incl. in the Docker container's CJK font), figures closed after each render
- [ ] Context-window protection: tool summary contains only file paths and previews, never full datasets — raw chart data never enters the agent's context
- [ ] SKILL/prompt mechanism fully removed (no `SKILLS/` dir, no prompt handlers, no stale references)
- [ ] Error handling: MCP tool errors return structured JSON, never raw tracebacks
- [ ] No dead code: no unused imports, functions, or files introduced (incl. removed stdio path)
- [ ] All new code follows project conventions (Chinese UI text, Ruff/ESLint clean)
