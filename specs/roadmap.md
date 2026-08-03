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

## Phase 5 — Dashboard API

**Goal:** The backend serves dashboard-ready data.

- [ ] `GET /api/metrics` — paginated, filterable (by source, date range, dimension)
- [ ] `GET /api/metrics/summary` — aggregate endpoint: totals, counts, latest values per metric
- [ ] `GET /api/imports` — list recent import jobs with status
- [ ] Auto-generated OpenAPI docs at `/docs` (Swagger) and `/redoc`

---

## Phase 6 — Dashboard UI: Metric Cards

**Goal:** Dashboard page with live metric cards from the backend, built on the existing app shell.

- [ ] Dashboard page with a responsive grid of **metric cards**
  - Each card: title, current value, delta/trend indicator, sparkline
- [ ] TanStack Query hooks for `/api/metrics/summary` and `/api/metrics`
- [ ] Loading skeletons and error states per card

---

## Phase 7 — Dashboard UI: Charts & Tables

**Goal:** Rich interactive data exploration.

- [ ] Time-series line/area chart (e.g., metric value over time, filterable by source)
- [ ] Bar chart for dimension breakdowns (e.g., by category, by source)
- [ ] Filterable, sortable, paginated data table (all metric records)
- [ ] Date range picker that drives all dashboard widgets
- [ ] Source filter dropdown to toggle which data sources appear

---

## Phase 8 — Platform Data Scraping

**Goal:** Pull data from our own platform — configurable as one-time or scheduled scrapes.

> ⚠️ **Dependency:** Details about the platform (API endpoints, page structure, auth) will be provided when we reach this phase.

- [ ] Scraping source configuration: target URL/endpoint, auth credentials, schedule (cron or one-time)
- [ ] Scraping engine integrated into FastAPI (APScheduler for scheduled runs)
- [ ] Scraped data flows through the same cleaning pipeline as file imports (Phase 3)
- [ ] Scrape job tracked as an `ImportJob` — status, rows ingested, errors
- [ ] Manual "Scrape Now" trigger per source
- [ ] Scrape history viewable alongside file import history

---

## Phase 9 — Auth & Multi-User

**Goal:** Only authorized team members can access the dashboard.

- [ ] Simple JWT-based auth (FastAPI dependency + React context)
- [ ] Login page, logout, token refresh
- [ ] User model (admin seeded manually or via script — no self-registration)
- [ ] Role-based access: admin (manage sources, trigger scrapes), viewer (dashboard only)

---

## Phase 10 — Polish & Deploy

**Goal:** Production-ready.

- [ ] Docker multi-stage builds for backend and frontend
- [ ] Nginx serving the React SPA + proxying `/api` to FastAPI
- [ ] Environment-based config (`.env` for secrets, connection strings)
- [ ] Comprehensive error handling and user-friendly error pages
- [ ] Logging: structured logs (JSON) from FastAPI
- [ ] README with setup instructions for new developers
