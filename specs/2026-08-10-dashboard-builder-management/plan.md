# Phase 9 — Dashboard Builder & Management: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Dashboard Data Model & Migration

1. Create `Dashboard` SQLAlchemy model in `backend/app/models/dashboard.py`:
   - `id` (UUID PK), `name` (String 255, unique, not null), `description` (String, nullable), `layout_json` (JSONB, not null — array of tile objects), `created_at`, `updated_at` (server-default now, onupdate now).
   - Chinese `comment=` on every column (project convention).
2. Register the model in `backend/app/models/__init__.py` so Alembic autogenerate picks it up.
3. Generate an Alembic migration (`add_dashboards_table`) including a unique constraint on `name` (mirroring `uq_visualizations_name` / views pattern). Verify `alembic upgrade head` and `downgrade -1` both succeed.

## Group 2 — Dashboard CRUD API

4. Add Pydantic schemas in `backend/app/schemas/dashboard.py`: `DashboardCreate`, `DashboardUpdate`, `DashboardResponse`, `DashboardListResponse`, and a `DashboardTile` model validating each `layout_json` entry (`tile_type`: `visualization` | `text` | `kpi_card`; `visualization_id` required when `tile_type == "visualization"`; `x`, `y`, `w`, `h` ints; `content`/`config` payload per type).
5. Implement `backend/app/routers/dashboards.py` with endpoints:
   - `POST /api/dashboards` — create; 409 on duplicate name (message in Chinese, e.g. `仪表盘名称 '...' 已存在`).
   - `GET /api/dashboards` — list all (id, name, description, tile count, created_at, updated_at).
   - `GET /api/dashboards/{id}` — full dashboard including `layout_json`.
   - `PUT /api/dashboards/{id}` — update name/description/layout; 409 on name conflict; 404 if missing.
   - `DELETE /api/dashboards/{id}` — delete; 204; 404 if missing.
6. Validate that every `visualization_id` referenced in `layout_json` exists; return 422 with Chinese detail otherwise.
7. Register the router in `backend/main.py`.
8. Write `backend/tests/test_dashboards.py` covering: create/list/get/update/delete happy paths, duplicate-name 409, missing dashboard 404, invalid `visualization_id` 422, and layout round-trip fidelity.

## Group 3 — Visualization Time-Profile & Parameterized Data Endpoint

9. Extend the Visualization Builder (frontend) with an optional "时间配置" (time profile) section stored in the visualization's `config_json`:
   - `date_column` — dropdown of datetime/date columns from the selected view (empty = not set).
   - `default_granularity` — 年 / 月 / 日 (year/month/day).
   - `default_agg` — aggregation function (SUM/COUNT/AVG/MIN/MAX) applied to the value column when re-bucketing.
10. Extend `GET /api/visualizations/{viz_id}/data` with optional query params `start`, `end`, `granularity`, `agg`:
    - Only applied when the visualization's `config_json.date_column` is set; otherwise ignored.
    - `start`/`end` inject an additional WHERE filter on `date_column` (parameterized, via the existing `_build_sql_from_config` regeneration path — do not string-interpolate).
    - `granularity` re-buckets rows by `date_trunc(granularity, date_column)` and applies `agg` to the configured value column(s).
    - Response shape unchanged (`columns`, `rows`, `chart_type`, `config_json`).
11. Backend tests: date filter narrows rows, granularity re-buckets correctly (e.g. daily → monthly sums), params ignored when no `date_column`, invalid granularity/agg rejected with 422.

## Group 4 — Dashboard Builder Page (Grid Canvas)

12. Add `react-grid-layout` (+ `@types/react-grid-layout`) to the frontend; vendor its CSS.
13. Create `DashboardBuilderPage` (`/dashboards/builder` and `/dashboards/builder/:id` for edit):
    - Grid canvas rendering tiles from local state; drag to reposition, resize handles to change `w`/`h` (desktop only — see Group 6 for mobile).
    - "添加可视化" panel listing saved visualizations (from `GET /api/visualizations`); clicking/dragging adds a tile.
    - "添加文本" button adding a text/markdown tile with an inline editor (textarea + preview).
    - "添加 KPI 卡" button adding an ad-hoc KPI tile (pick a view + value column + label + aggregation).
    - Per-tile remove button; tile dimensions adjustable via resize.
    - Name + description inputs; 保存 button persisting via POST/PUT with the raw `react-grid-layout` layout array mapped into `layout_json`.
    - Name-conflict flow mirroring views/visualizations: on 409 show a dialog prompting for a new name and retry.
14. State persistence via a `DashboardBuilderContext` above the router so builder state survives navigation (mirrors ViewBuilder/VisualizationBuilder pattern).
15. Sidebar: add collapsible "仪表盘" parent section. Parent links to the dashboard list page; each saved dashboard appears as a child nav item (by name). Use explicit `isLinkActive` logic (not NavLink prefix matching) so `/dashboards/builder*` does not highlight the parent list item.

## Group 5 — Dashboard Display Page & Interactivity

16. Create `DashboardDisplayPage` (`/dashboards/:id`):
    - Render the saved grid read-only; each visualization tile fetches `GET /api/visualizations/{id}/data` (optionally with global filter params) and renders via the existing chart renderer.
    - Text tiles render markdown; ad-hoc KPI tiles fetch their view data and compute the configured aggregation client-side (or via a small endpoint if simpler).
    - Per-tile manual refresh button (re-fetch that tile only), consistent with Phase 8's manual-refresh decision.
    - Full-screen single-tile view: a maximize button per tile opening a dialog/route rendering that tile large.
    - Global controls bar: date-range picker + granularity picker (年/月/日) + aggregation function selector. These apply only to tiles whose visualization has `date_column` set; other tiles are unaffected and show a subtle "不响应时间筛选" hint.
    - 编辑 button navigating to the builder pre-filled; 删除 button with confirmation dialog returning to the list.
17. TanStack Query hooks for all dashboard endpoints; cache tile data and avoid refetch on tab-switch (consistent with Phase 8 thumbnails), refetch only on manual refresh or global-filter change.

## Group 6 — Dashboard List/Manage Page & Responsive Behavior

18. Create `DashboardsListPage` (`/dashboards`): table of dashboards (name, description, tile count, created/updated, sortable), with 新建仪表盘 button, and per-row 查看 / 编辑 / 重命名 / 删除 actions (rename + delete with confirmation, unique-name enforcement).
19. Responsive: grid is desktop-first. On viewports below `lg`, render tiles stacked vertically in a read-only single column (no drag/resize); builder editing controls are disabled/hidden on small screens with a Chinese hint that editing requires a desktop viewport.
20. All UI text in Chinese (labels, buttons, empty states, toasts, dialogs, placeholders).

## Group 7 — Validation & Polish

21. Run backend gates: `ruff check`, `pytest` (all green, incl. new dashboard + time-profile tests).
22. Run frontend gates: `tsc --noEmit`, `eslint`, `prettier --check`, `vitest run` for new components/hooks.
23. Manual end-to-end pass per `validation.md`: build a dashboard from real saved visualizations, exercise global date/granularity/agg filter, per-tile refresh, full-screen tile, edit round-trip, rename conflict, delete, and mobile stacking.
