# YKMMgmt — Roadmap

High-level implementation order in small, shippable phases. Each phase produces something demonstrable.

---

## Phase 1 — Project Scaffolding

**Goal:** Two runnable "hello world" apps that talk to each other.

- [x] Initialize FastAPI project (`ykmmgmt/backend/`) with conda env (Python 3.12)
- [x] Single health-check endpoint (`GET /api/health`)
- [x] Initialize React + TypeScript + Vite project (`ykmmgmt/frontend/`) with shadcn/ui
- [x] Single page that calls `/api/health` via TanStack Query and displays the result
- [x] Vite proxy config so the dev server routes `/api/*` to FastAPI
- [x] `.gitignore`, `README.md` with quick-start instructions
- [x] Linting: Ruff (backend), ESLint + Prettier (frontend)
- [x] Testing: Vitest + React Testing Library configured, test scripts in package.json
- [x] Responsive viewport meta tag, Tailwind CSS breakpoints active

---

## Phase 2 — Database & Core Models

**Goal:** PostgreSQL is running, tables exist, migrations work.

> ⚠️ **Dependency:** Sample data files have been placed in the project folder. The database schema MUST be designed by inspecting these files — column names, types, and relationships should reflect the actual data shape, not generic placeholders.

- [x] SQLAlchemy base + async engine setup
- [x] Alembic initialized, first migration
- [x] Inspect provided sample data files and derive the schema from them:
  - `DataSource` — name, type (csv/excel), config JSON, schedule
  - `ImportJob` — source FK, status, started_at, finished_at, row count, errors
  - Business data tables — columns and types driven by the actual sample data structure
- [x] Seed script using the sample data files for development

---

## Phase 3 — CSV & Excel Import Engine

**Goal:** Upload a CSV or Excel file, clean it, and load clean data into the database.

> Only two file formats are supported: **.csv** and **.xlsx**.

- [x] Unified import endpoint (`POST /api/imports`) — accepts both CSV and Excel files
- [x] **Data preparation (cleaning) pipeline** — must run BEFORE loading into DB:
  - [x] Strip whitespace, normalize column headers
  - [x] Handle missing values and blank rows/columns (drop or fill per configurable rules)
  - [x] Normalize inconsistent formats (dates, numbers, encodings)
  - [x] Deduplicate rows
  - [x] Validate values against expected ranges/types; flag or reject invalid rows
  - [x] Produce a cleaning report: rows dropped, rows modified, warnings per column
- [x] CSV parser using Pandas: validate headers against expected schema, infer types
- [x] Excel parser using openpyxl: read sheets, validate headers, infer types — same pipeline as CSV
- [x] Store cleaned/validated rows linked to an `ImportJob`
- [x] Return import job status + row count + cleaning report + validation errors
- [x] Error handling: malformed file, missing columns, empty files, unrecoverable rows

---

## Phase 3.5 — Upsert Support for Data Imports

**Goal:** Re-uploading a file updates existing records instead of silently skipping them.

> Currently `on_conflict_do_nothing()` is used — records with matching business keys are discarded. This phase switches to upsert semantics.

- [x] Replace `on_conflict_do_nothing()` with `on_conflict_do_update()` targeting business unique keys (e.g. `refund_order_no`)
- [x] On conflict, update all non-key, non-timestamp columns with values from the new row
- [x] Decide `imported_at` behavior: reset to current timestamp on update
- [x] Track upsert stats in import job report: `rows_inserted`, `rows_updated`, `rows_skipped`
- [x] Tests: verify existing record fields are updated, new records inserted, business keys unchanged
- [x] WalletWithdrawal dedup via `content_hash` (SHA-256 of all business columns) — table without natural unique key

---

## Phase 4 — App Shell & CSV/Excel Upload UI

**Goal:** A navigable app shell with upload capability so users can get real data into the system.

- [x] App layout: responsive sidebar nav (collapsible on mobile) + main content area (shadcn/ui)
  - Sidebar links: Upload Data, Dashboard (placeholder), Import History
- [x] Upload page: drag-and-drop zone, file picker (accepts .csv and .xlsx), upload button
- [x] Upload progress indicator
- [x] Post-upload result: row count, cleaning report, errors (if any), link to view imported data
- [x] Import history page: table of past imports with status badges and source file type
- [x] TanStack Query hooks for `POST /api/imports` and `GET /api/imports`

**Extended scope** (redesigned 2026-08-28, delivered as a small standalone change):

- [x] Upload page redesigned into a generic 数据导入 hub — a top panel switches the import method: 上传文件 | 数据抓取 | 导入历史
- [x] 导入历史 moved from a standalone sidebar page into a tab of the 数据导入 hub (standalone route and nav item removed)
- [x] 数据抓取 tab rendered as a "coming soon" placeholder (the scraper itself is deferred — see Phase 15)

---

## Phase 4.5 — Data Browser

**Goal:** Browse raw data in any database table with pagination, column value filtering, sorting, and date filtering.

- [x] Backend: `GET /api/tables` — list all tables in the database
- [x] Backend: `GET /api/tables/{name}/schema` — return column names and types for a table
- [x] Backend: `GET /api/tables/{name}/data` — paginated rows (`?page=&size=`), optional `?datetime_col=&start=&end=` date filter, `?filter_col=&filter_value=&filter_mode=` column value filter (positional repeated, supports 包含/精确 modes), `?sort_col=&sort_dir=` sort
- [x] Frontend: Table selector (listbox) populated from `/api/tables`
- [x] Frontend: Paginated data grid — 20 rows per page, Previous/Next buttons, page number input
- [x] Frontend: DateTime range filter — column picker + date range inputs
- [x] Frontend: Column value filter — multi-row filter UI (column dropdown + 包含/精确 toggle + value input), "添加筛选条件" button, AND-combined with date filter
- [x] Frontend: Sortable column headers — click to cycle asc (▲) → desc (▼) → none, arrow indicators
- [x] Sidebar: Add "Data Browser" nav item

---

## Phase 5 — Data View Builder

**Goal:** Build comprehensive data views (joins, columns, filters, grouping, aggregation) and store both the JSON config and the generated SQL.

- [x] Backend: View definition model — `name`, `description`, `config_json` (join specs, column selections, filters, groupings, aggregations, computed columns), `generated_sql` (the compiled SQL), `created_at`, `updated_at`
- [x] Backend: SQL generation engine — translate JSON config into valid parameterized SQL from the table schema (ViewSQLBuilder with COALESCE for null-safe arithmetic, INTERVAL for datetime shifts, chained expressions)
- [x] Backend: `POST /api/views` — create a view (accept config, validate table/column references, generate SQL, store both)
- [x] Backend: `PUT /api/views/{id}` — update a view definition (SQL regenerated on config change, preserved on name-only change)
- [x] Frontend: Table selector — pick source table(s) for the view (multi-select with join support)
- [x] Frontend: Join builder — select join type (INNER/LEFT/RIGHT), join key columns between selected tables, self-join support with alias disambiguation
- [x] Frontend: Column picker — select which columns to include in the result (checkbox list with alias input, integrated computed column selection)
- [x] Frontend: Filter builder — add WHERE conditions with column, operator (type-aware: numeric/date vs text), and value
- [x] Frontend: Grouping & aggregation — select GROUP BY columns (badge toggle incl. computed columns) and aggregation functions (SUM, COUNT, AVG, MIN, MAX) on any column
- [x] Frontend: Live preview — run the generated SQL against a small sample (20 rows) and show the result + generated SQL
- [x] **Computed columns** — chained arithmetic (+, -, *, /) with COALESCE null-safety, datetime shift (± days/months/years), collapsible config card with confirm button, type-filtered column selectors
- [x] State persistence via React Context (ViewBuilderContext) across navigation

---

## Phase 6 — Saved Data Views Management

**Goal:** List, preview, edit, and delete saved views.

- [x] Backend: `GET /api/views` — list all saved views with metadata
- [x] Backend: `GET /api/views/{id}` — full view definition + generated SQL
- [x] Backend: `GET /api/views/{id}/data` — execute the stored SQL and return results (paginated)
- [x] Backend: `DELETE /api/views/{id}` — delete a view
- [x] Frontend: Views list page — table of saved views with name, description, created date
- [x] Frontend: Preview dialog — execute the view's SQL and display results in a paginated table
- [x] Frontend: Edit button — navigate to Phase 5 builder pre-filled with the view's config
- [x] Frontend: Delete button with confirmation
- [x] Sidebar: Add "Data Views" nav item

---

## Phase 7 — Visualization Builder

**Goal:** Build and save visualizations by selecting a data view, a chart type, and configuring it.

- [x] Backend: Visualization model — `name`, `view_id` (FK), `chart_type` (table/kpi_card/bar/line/pie/scatter/histogram/boxplot), `config_json` (axis mappings, colors, labels, etc.), `created_at`, `updated_at`
- [x] Backend: `POST /api/visualizations` — create a visualization
- [x] Backend: `PUT /api/visualizations/{id}` — update a visualization
- [x] Frontend: View selector — pick from saved views (Phase 6) to use as data source
- [x] Frontend: Chart type selector — Table, KPI Card, Bar Chart, Line Chart, Pie Chart, Scatter Plot, Histogram, Boxplot
- [x] Frontend: Configuration panel — per chart type:
  - **Table:** column visibility toggles, sort column
  - **KPI Card:** value column, label, optional comparison/target
  - **Bar / Line / Pie / Scatter:** X-axis column, Y-axis column(s), color/group-by column, title
  - **Histogram:** numeric column(s) with overlaid semi-transparent bins, configurable bin count
  - **Boxplot:** numeric value column, optional categorical split, five-number summary
- [x] Frontend: Live preview — render the visualization with sample data from the selected view

---

## Phase 8 — Saved Visualizations Management

**Goal:** List, view, edit, and delete saved visualizations.

- [x] Backend: `GET /api/visualizations` — list all saved visualizations with metadata
- [x] Backend: `GET /api/visualizations/{id}` — full visualization definition + rendered data
- [x] Backend: `DELETE /api/visualizations/{id}` — delete a visualization
- [x] Frontend: Visualizations list page — table of saved visualizations with name, chart type, source view, created/updated date (sortable); chart types show a clickable zoomed-out thumbnail whose data is fetched once and cached across tab navigation (no re-query when switching away and back), re-rendered on manual refresh; visualization names unique with name-conflict save/update flow mirroring data views
- [x] Frontend: View button — render the visualization full-size with live data
- [x] Frontend: Manual refresh button — re-fetch visualization data on demand (auto-refresh/polling intentionally dropped)
- [x] Frontend: Edit button — navigate to Phase 7 builder pre-filled
- [x] Frontend: Delete button with confirmation
- [x] Sidebar: Add "Visualizations" nav item

---

## Phase 9 — Dashboard Builder & Management

**Goal:** Compose, view, and manage dashboards from saved visualizations with flexible grid positioning and sidebar navigation.

- [x] Backend: Dashboard model — `name` (unique), `description`, `layout_json` (array of tiles: `{i, tile_type, visualization_id?, x, y, w, h, content?, config?}`), `created_at`, `updated_at`
- [x] Backend: `POST /api/dashboards` — create a dashboard (409 on duplicate name, 422 on invalid visualization/view references)
- [x] Backend: `GET /api/dashboards` — list all dashboards (incl. tile count)
- [x] Backend: `GET /api/dashboards/{id}` — full dashboard config with layout_json
- [x] Backend: `PUT /api/dashboards/{id}` — update dashboard name/description/layout
- [x] Backend: `DELETE /api/dashboards/{id}` — delete a dashboard
- [x] Backend: Time-profile overrides on `GET /api/visualizations/{id}/data` — optional `start`/`end`/`granularity`/`agg` params, parameterized, active only when the visualization declares `config_json.date_column` (date filter narrows rows; granularity re-buckets with SUM/COUNT/AVG/MIN/MAX)
- [x] Frontend: Visualization Builder 时间配置 section — date_column picker (datetime columns of the view) + default granularity (年/月/日) + default aggregation
- [x] Frontend: Dashboard builder page — grid canvas using `react-grid-layout` (v2) with drag/resize; three tile types: visualization, text/markdown (inline editor + preview), ad-hoc KPI card (view + value column + label + aggregation, aggregated client-side)
- [x] Frontend: "添加可视化" panel — pick from saved visualizations (Phase 8) and add onto the grid
- [x] Frontend: Remove tile, adjust tile dimensions via resize handles
- [x] Frontend: Save dashboard — persist layout to backend; name-conflict flow (overwrite confirmation + rename-on-409 dialog) mirroring views/visualizations
- [x] Frontend: DashboardBuilderContext above the router — builder state survives navigation
- [x] Frontend: Sidebar — collapsible "仪表盘" parent section linking to the list page; each saved dashboard is a child nav item by name; explicit isLinkActive so `/dashboards/builder*` does not highlight the parent
- [x] Frontend: Dashboard display page — read-only grid with live tile data, per-tile manual refresh, full-screen single-tile view, 编辑/删除 buttons
- [x] Frontend: Global time controls — date range + granularity (年/月/日/不重分桶/按可视化默认) + aggregation selector; apply only to tiles whose visualization has `date_column`; others show a "不响应时间筛选" hint
- [x] Frontend: Dashboard list/manage page — name, description, tile count, sortable created/updated, 新建仪表盘, per-row 查看 / 编辑 / 重命名 / 删除 (unique-name enforcement)
- [x] Frontend: Responsive — desktop-first grid; below `lg` tiles stack read-only in a single column; builder editing gated behind a desktop-viewport hint

---

## Phase 10 — Database Schema Management

**Goal:** Inspect, create, edit, and delete database tables through a dedicated UI — no manual SQL or migration files needed.

- [x] Backend: Schema inspection endpoint — list all tables with column details (name, type, nullable, unique, comment/Chinese label, constraints)
- [x] Backend: Table creation endpoint — accepts table name, Chinese display name, column definitions (name, type, Chinese label, nullable, unique); generates SQLAlchemy model + Alembic migration + runs migration
- [x] Backend: CSV schema inference endpoint — accepts a CSV file, infers column names/types, suggests Chinese labels from headers, returns proposed schema for user review before creation
- [x] Backend: Table edit endpoint — add column, drop column, modify column type; generates Alembic migration for each operation
- [x] Backend: Table deletion endpoint — drops table with confirmation, generates Alembic migration
- [x] Backend: Dynamic model registry — newly created tables auto-register into `schema_validator._MODEL_REGISTRY` and `TABLE_DISPLAY_NAMES` so they appear in Data Browser / View Builder without restart
- [x] Backend: Column type system — supported types: String(N), Text, Integer, Numeric(12,2), DateTime, Boolean; type mapping between SQLAlchemy and frontend picker
- [x] Frontend: Sidebar — "Schema Manager" nav item under a database/admin section
- [x] Frontend: Table list page — all tables with Chinese names, column count, row count, created date; actions per table: inspect, edit, delete
- [x] Frontend: Table detail/inspect page — full column listing with types, constraints, Chinese labels, sample data preview
- [x] Frontend: Create table wizard — two paths: (a) manual: define columns one-by-one with type picker and Chinese label input; (b) CSV import: upload CSV, review inferred schema, adjust types/labels, confirm creation
- [x] Frontend: Edit table dialog — add new column, remove column, change column type (with warning about data loss for incompatible casts)
- [x] Frontend: Delete table confirmation — type-to-confirm pattern, warning about cascading effects on views/visualizations
- [x] Frontend: All UI text in Chinese per project convention

**Extended scope** (requested during implementation, delivered in the same phase):

- [x] Upload robustness & matching — multi-BOM stripping; Chinese-label-first header matching with column-name fallback; strict gate rejecting files with unmapped headers or missing required columns (422 with missing/unexpected lists); runtime migrations relocated outside the reload watch tree
- [x] Table & column renaming — physical table rename with dependency protection (409 when views/visualizations reference it), display-name editing via table comment, edit-page caveat tooltips (opaque InfoTooltip)
- [x] Foreign keys to unique keys — FK targets extended from PK-only to PK or unique column, with picker markers (…・主键 / …・唯一)
- [x] Column metadata — description + default value per column (column_meta), comprehensive per-column editing in a single migration
- [x] Ingestion settings — per-table upsert key (optional, composite, defaults to PK) + dedup toggle stored in table_meta; dedup disable only allowed without PK/unique/upsert key; keyless dedup-on tables get content_hash
- [x] Import counter semantics — authoritative 新增/更新/跳过/拒绝 definitions with full fetch-compare-write upsert for keyed tables; partial uploads never null omitted columns; counters increment only after successful writes

---

## Phase 11 — Legacy Business Table Removal & System Reset

**Goal:** Remove the three hardcoded legacy business tables (退费单, 服务退款工单, 钱包提现操作) and all table-specific cleansing pipelines, resetting the system to a fully generic state where all business tables are created dynamically via Schema Manager.

> The general architecture must not break: users create a table schema via Schema Manager, data comes from a data source, goes through a data cleansing pipeline (table-specific if available + general), then lands in the database. The only difference is that no preset tables or hardcoded rules ship with the system.

### Database Cleanup

- [x] Generate Alembic migration: drop `refund_orders`, `service_refund_work_orders`, `wallet_withdrawals` tables
- [x] Cascade-delete all dependent objects: saved views, visualizations, and dashboards that reference any of the three tables (scan `generated_sql` and `config_json` for table name matches; delete matching rows from `views`, `visualizations`, `dashboards`)
- [x] Delete related `ImportJob` and `DataSource` records tied to the three tables
- [x] Verify no orphaned `column_meta` or `table_meta` rows remain for the dropped tables

### Code Cleanup — Models & Registry

- [x] Delete `app/models/refund_order.py`, `app/models/service_refund_work_order.py`, `app/models/wallet_withdrawal.py`
- [x] Remove the three model imports from `app/models/__init__.py`
- [x] Remove `READ_ONLY_TABLES` frozenset from `app/services/schema_manager.py` (no longer needed — all tables are dynamic)
- [x] Remove the three hardcoded entries from `TABLE_DISPLAY_NAMES` in `app/services/schema_validator.py`
- [x] Remove `READ_ONLY_TABLES` guard from `app/routers/schema.py::_get_editable_model()`

### Code Cleanup — Table-Specific Cleansing Rules

- [x] Delete `app/services/table_specific/refund_order.py`
- [x] Delete `app/services/table_specific/service_refund.py`
- [x] Delete `app/services/table_specific/wallet_withdrawal.py`
- [x] Verify `table_specific/__init__.py` registry still works correctly (empty registry = no table-specific rules for any table)

### Seed Script & Sample Data

- [x] Delete `seed.py` entirely
- [x] Remove or archive the three legacy CSV sample files (`服务退款工单0601~0721.csv`, `退费单0601~0721.csv`, `钱包提现操作0601~0721.csv`) from the project root

### Test Updates

- [x] Update `tests/test_views.py` — replace `refund_orders` references with a dynamically created test table
- [x] Update `tests/test_visualizations.py` — same replacement
- [x] Update `tests/test_view_sql_builder.py` — same replacement
- [x] Update `tests/test_imports.py` — remove legacy-table-specific import tests, keep generic pipeline tests
- [x] Update `frontend/src/test/SchemaManager.test.tsx` — remove `退费单` / `read_only` assertions tied to legacy tables
- [x] Add new test: verify that a fresh database starts with zero business tables and the Schema Manager table list is empty

### Validation

- [x] Fresh database: `alembic upgrade head` creates only system tables (`datasources`, `import_jobs`, `views`, `visualizations`, `dashboards`, `column_meta`, `table_meta`, `alembic_version`)
- [x] Schema Manager UI shows zero tables on first launch
- [x] Create a new table via Schema Manager → upload CSV → data flows through general cleaning pipeline → lands in DB correctly
- [x] Data Browser, View Builder, Visualization Builder, Dashboard Builder all work with dynamically created tables
- [x] No import errors or registry warnings on backend startup

---

## Phase 12 — Auth & Multi-User

**Goal:** Only authorized team members can access the dashboard.

> Redesigned during spec (2026-08-28): three-level hierarchy (root / admin / user) instead of the original admin/viewer split; full app lockdown with httpOnly-cookie JWT sessions.

- [x] Simple JWT-based auth (FastAPI dependency + React context)
- [x] Login page, logout, token refresh (httpOnly cookies, 2-hour access + 7-day refresh, silent refresh-and-retry in the API client)
- [x] User model (root seeded from `.env` via `scripts/seed_root.py` — no self-registration; root immutable via API)
- [x] Role-based access: root (超级管理员， full rights, creates admins/users), admin (管理员， all operational rights, manages plain users only, never sees root accounts), user (用户， read-only)
- [x] Hierarchy-enforced user management API + 用户管理 UI (create user / reset password / change role / enable-disable), root account rendered without actions
- [x] Full lockdown: all API endpoints and pages require authentication; `/api/health` stays public; admin-only nav items and edit/delete actions hidden for L3 users (server-side 403 remains authoritative)

---

## Phase 13 — Polish & Deploy

**Goal:** Production-ready — the app runs in Docker on the local machine, publicly reachable through an Alibaba Cloud server acting as a reverse-proxy entry, with a CI/CD pipeline for fast iteration.

> **Deployment topology (decided 2026-09-01):** The full stack (FastAPI + React SPA + PostgreSQL) runs in Docker containers on the **local machine**. The **Alibaba Cloud server** is only a stateless public entry point: Nginx there reverse-proxies traffic into an **frp tunnel** (frps on the cloud server, frpc on the local machine). The cloud server is configured once and does not change with app releases.

> **Access:** Public IP over HTTP for now; domain + HTTPS is a later upgrade (flip `cookie_secure` to `True` when HTTPS lands).

### Local Production Stack (Docker Compose on the local machine)

- [x] Docker multi-stage build for the backend (FastAPI + uvicorn)
- [x] Docker multi-stage build for the frontend (Vite build → static assets served by an Nginx container, which also proxies `/api` to the backend container)
- [x] Extend `docker-compose.yml` into a production compose file: `db` (postgres:16, existing) + `backend` + `frontend-nginx` services on an internal network; only the Nginx port exposed to the host
- [x] Environment-based config: production `.env` (DATABASE_URL pointing at the `db` service, strong SECRET_KEY, ROOT_USERNAME/ROOT_PASSWORD); `.env.example` updated with the new variables
- [x] Alembic migrations run automatically on backend container start (entrypoint: `alembic upgrade head` before uvicorn)
- [x] Schema migration lifecycle: squash the Schema Manager's runtime migrations (`runtime_migrations/`) into a version-controlled baseline migration (checkpoint), so redeployments and DB restores never depend on machine-local files; startup guard when `alembic_version` references a missing revision
- [x] Comprehensive error handling and user-friendly error pages
- [x] Logging: structured logs (JSON) from FastAPI
- [x] README with setup instructions for new developers

### Public Access via Alibaba Cloud (one-time manual setup, documented)

- [x] frps deployed on the Alibaba Cloud server; frpc running as a service on the local machine (docker-compose service or Windows service) exposing the local Nginx port through the tunnel
- [x] Nginx on the Alibaba Cloud server reverse-proxies public HTTP (IP-only for now) to the frp tunnel port
- [x] Cloud-side config documented in the README/deploy doc — it does not change with app releases

### CI/CD Pipeline (GitHub Actions)

- [x] Workflow on push to `main`: Ruff + Pytest (backend), ESLint + tsc + Vitest (frontend)
- [x] Build backend + frontend Docker images and push to a container registry (GHCR or Alibaba ACR — decided at implementation time)
- [x] Local machine pulls and restarts: a `deploy` script (`docker compose pull && docker compose up -d`) run manually, or watchtower for auto-pull
- [x] Production compose file references registry images (with `build:` fallback for local dev)

---

## Phase 14 — MCP Server for External AI Agents

**Goal:** External AI agents (Claude Desktop, etc.) can interact with YKMMgmt through a Model Context Protocol (MCP) server, starting with visualization export and designed for extensibility.

> **Architecture:** A persistent HTTP service (`ykmmgmt/mcp_server/`) using the `mcp` SDK over streamable HTTP transport, deployed as a Docker Compose service alongside the backend/frontend. It communicates with the FastAPI backend over the Docker internal network using a dedicated service account for authentication; incoming MCP client connections are authenticated with an API key. The service is exposed to external agents via the frpc tunnel.
>
> **Decision history (transport):** the spec originally chose stdio transport (the MCP client launches the server as a local subprocess). It was replanned to streamable HTTP because a persistent, network-reachable service better fits remote agents and the existing Docker/frpc deploy topology.

### Scalable Tool Framework

- [x] MCP server project scaffold (`ykmmgmt/mcp_server/`) with `mcp` Python SDK, streamable HTTP transport
- [x] Tool registry pattern — each tool is a self-contained module that registers its name, description, input schema, and handler; adding a new tool = dropping a new file into `tools/`
- [x] Shared HTTP client for backend API calls with auth (service account JWT from env var)
- [x] Structured error responses — tool errors return `{error: "..."}` JSON, never raw tracebacks
- [x] API-key guard on the MCP endpoint — clients send `Authorization: Bearer <YKM_MCP_API_KEY>`; requests without a valid key are rejected (401)
- [x] Configuration via environment variables: `YKM_BACKEND_URL`, service account credentials, `YKM_MCP_API_KEY`, listen host/port

### Deployment

- [x] `ykmmgmt/mcp_server/Dockerfile` — Python 3.12 image that installs the package and runs the HTTP server
- [x] `mcp_server` service in `docker-compose.prod.yml` (GHCR image with `build:` fallback) and dev `docker-compose.yml`, on the internal network, `depends_on: backend`
- [x] frpc `[[proxies]]` entry tunneling the MCP port to the cloud entry, so external agents reach it over the tunnel (same pattern as the frontend)
- [x] CI builds/pushes `ghcr.io/fizzking9/ykmmgmt-mcp`; `scripts/deploy.ps1` pulls it

### Backend: CSV Export Endpoint for Table Visualizations

- [x] `GET /api/visualizations/{id}/export` — new endpoint that returns a file download response
  - For **table** chart type: returns CSV (UTF-8 with BOM for Excel compatibility), `Content-Disposition: attachment`
  - For all other chart types: returns 422 with a message directing the caller to use the data endpoint + client-side rendering
  - Accepts the same optional time-profile params as the data endpoint (`start`/`end`/`granularity`/`agg`)
- [x] Frontend change: table-type visualization export button switches from html2canvas PNG capture to downloading from `GET /api/visualizations/{id}/export` (CSV)

### Initial Tool: Export Visualizations (Server-Rendered)

- [x] Tool name: `export_visualizations`
- [x] Input: `output_dir` (string, path to local folder), optional `visualization_ids` (list of UUIDs to export a subset; omit for all)
- [x] Behavior (server-side rendering — deterministic chart images produced by the MCP server):
  - Fetch all saved visualizations from `GET /api/visualizations`
  - **Table charts** → download CSV from `GET /api/visualizations/{id}/export`
  - **All other chart types** (bar, line, pie, scatter, histogram, boxplot, kpi_card) → fetch data from `GET /api/visualizations/{id}/data`, render a chart image with the MCP server's matplotlib renderer, write `{sanitized_name}.png` — no raw data files, nothing for the agent to misinterpret
  - File naming: `{sanitized_visualization_name}.{csv|png}` in the output directory
  - Return a compact summary: `{exported: N, failed: M, files: [...]}` with per-file preview (chart type, columns, row count) — never full datasets inline, to protect the agent's context window
- [x] matplotlib renderer module in the MCP server: per-chart-type interpretation of `config_json` (x_column/y_columns, label_column/value_column, bins, category_column…), Chinese font handling (Microsoft YaHei/SimHei fallbacks), style conventions (Chinese titles/axis labels, sorted time axes, descending pie sectors)

> **Decision history:** the spec initially chose agent-side rendering (raw JSON + rendering SKILL). Manual testing with a third-party agent showed non-deterministic output, misinterpreted chart variables, and a fresh .py script per run — reverted to deterministic server-side rendering (the original Phase 14 design).

### Testing

- [x] Unit tests for the tool registry and each tool handler
- [x] Integration test: over streamable HTTP, the MCP server lists tools, enforces the API key (rejects missing/invalid keys with 401), calls `export_visualizations`, and produces files in a temp directory
- [ ] Test with an MCP client (Inspector / Claude Desktop HTTP transport) connecting to `http://localhost:8001/mcp` with the API key to verify end-to-end connectivity, including through the frpc tunnel

---

## Phase 15 — Platform Data Scraping (Future, Post-Deployment)

**Goal:** Pull data from our own platform — configurable as one-time or scheduled scrapes.

> ⚠️ **Deferred:** This phase is a future feature, planned AFTER deployment (Phase 13). The 数据抓取 tab in the 数据导入 page (Phase 4 extended scope) already ships as a "coming soon" placeholder and will become the entry point for this feature.

> ⚠️ **Dependency:** Details about the platform (API endpoints, page structure, auth) will be provided when we reach this phase.

- [ ] Scraping source configuration: target URL/endpoint, auth credentials, schedule (cron or one-time)
- [ ] Scraping engine integrated into FastAPI (APScheduler for scheduled runs)
- [ ] Scraped data flows through the same cleaning pipeline as file imports (Phase 3)
- [ ] Scrape job tracked as an `ImportJob` — status, rows ingested, errors
- [ ] Manual "Scrape Now" trigger per source
- [ ] Scrape history viewable alongside file import history (in the 导入历史 tab of the 数据导入 page)
