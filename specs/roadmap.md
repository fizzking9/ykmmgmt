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

## Phase 10 — Platform Data Scraping

**Goal:** Pull data from our own platform — configurable as one-time or scheduled scrapes.

> ⚠️ **Dependency:** Details about the platform (API endpoints, page structure, auth) will be provided when we reach this phase.

- [ ] Scraping source configuration: target URL/endpoint, auth credentials, schedule (cron or one-time)
- [ ] Scraping engine integrated into FastAPI (APScheduler for scheduled runs)
- [ ] Scraped data flows through the same cleaning pipeline as file imports (Phase 3)
- [ ] Scrape job tracked as an `ImportJob` — status, rows ingested, errors
- [ ] Manual "Scrape Now" trigger per source
- [ ] Scrape history viewable alongside file import history

---

## Phase 11 — Auth & Multi-User

**Goal:** Only authorized team members can access the dashboard.

- [ ] Simple JWT-based auth (FastAPI dependency + React context)
- [ ] Login page, logout, token refresh
- [ ] User model (admin seeded manually or via script — no self-registration)
- [ ] Role-based access: admin (manage sources, trigger scrapes), viewer (dashboard only)

---

## Phase 12 — Polish & Deploy

**Goal:** Production-ready.

- [ ] Docker multi-stage builds for backend and frontend
- [ ] Nginx serving the React SPA + proxying `/api` to FastAPI
- [ ] Environment-based config (`.env` for secrets, connection strings)
- [ ] Comprehensive error handling and user-friendly error pages
- [ ] Logging: structured logs (JSON) from FastAPI
- [ ] README with setup instructions for new developers
