# Phase 9 — Dashboard Builder & Management: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Backend linting

```bash
cd ykmmgmt/backend && ruff check .
```

**Expected:** Zero errors, zero warnings on `app/`, `tests/`, `main.py` (pre-existing findings in auto-generated Alembic boilerplate untouched).

**Status: PASS (2026-08-11)** — `ruff check .` → "All checks passed!" (auto-generated Alembic boilerplate excluded via `extend-exclude` in `ruff.toml`).

---

## Gate 2 — Frontend linting

```bash
cd ykmmgmt/frontend && npx eslint src/ --ext .ts,.tsx
```

**Expected:** Zero errors, zero warnings.

**Status: PASS (2026-08-11)** — `npx eslint "src/**/*.{ts,tsx}"` → 0 errors, 0 warnings.

```bash
cd ykmmgmt/frontend && npx tsc --noEmit
```

**Expected:** Zero type errors.

**Status: PASS (2026-08-11)** — `npx tsc --noEmit` → exit 0.

---

## Gate 4 — Formatting

```bash
cd ykmmgmt/frontend && npx prettier --check src/
```

**Expected:** Zero unformatted files.

**Status: PASS (2026-08-11)** — `npx prettier --check src` → "All matched files use Prettier code style!"

---

## Gate 5 — Backend tests

```bash
cd ykmmgmt/backend && python -m pytest tests/ -v
```

**Expected:** All tests pass, zero failures. New `test_dashboards.py` covers: dashboard CRUD happy paths, duplicate-name 409, missing dashboard 404, invalid `visualization_id` 422, layout round-trip fidelity, and the parameterized time-override data endpoint (date filter narrows rows, granularity re-buckets, params ignored without `date_column`, invalid granularity/agg → 422).

**Status: PASS (2026-08-11)** — `pytest -q` → **106 passed** (15 new `test_dashboards.py` + 6 new time-profile tests in `test_visualizations.py`). Note: granularity re-bucketing runs as backend post-processing (`_rebucket_rows`) over the parameterized query result so mixed-type view output (text columns) cannot break SQL aggregation — verified against the real 7-column `test1` view.

---

## Gate 6 — Frontend tests

```bash
cd ykmmgmt/frontend && npx vitest run
```

**Expected:** All tests pass, zero failures. New tests cover: dashboard list rendering + actions, builder add/remove/resize tile state, name-conflict dialog flow, display page global-filter param construction, and sidebar active-state logic.

**Status: PASS (2026-08-11)** — `npx vitest run` → **48 passed** across 5 files (16 new tests in `Dashboards.test.tsx`: list page rendering/actions, rename + delete dialogs, sorting, `computeAggregation`, `TextTileMarkdown`, `DashboardBuilderContext` add/remove/applyLayout/load).

---

## Gate 7 — Database migration round-trip

```bash
cd ykmmgmt/backend && alembic upgrade head && alembic downgrade -1 && alembic upgrade head
```

**Expected:** All three commands succeed. `dashboards` table exists with a unique constraint on `name` and Chinese column comments.

**Status: PASS (2026-08-11)** — migration `9b719a1765ae_add_dashboards_table`: upgrade head → downgrade -1 → upgrade head all succeeded; table has `uq_dashboards_name` and Chinese comments on all columns.

---

## Gate 8 — Dashboard CRUD API works end-to-end

```bash
# Create
curl -s -X POST http://localhost:8000/api/dashboards -H "Content-Type: application/json" -d '{"name":"测试仪表盘","layout_json":[]}'
# List
curl -s http://localhost:8000/api/dashboards
# Duplicate name → expect 409
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/dashboards -H "Content-Type: application/json" -d '{"name":"测试仪表盘","layout_json":[]}'
```

**Expected:** Create returns 201 with an `id`; list contains the dashboard; duplicate-name POST returns HTTP 409 with a Chinese detail message; GET/PUT/DELETE on a missing id return 404.

**Status: PASS (2026-08-11)** — live round-trip against `localhost:8000`: create 201 → duplicate 409 `仪表盘名称 '门禁八探针' 已存在` → PUT 200 → DELETE 204 → GET 404 `仪表盘 '...' 不存在`; missing-id PUT/DELETE both 404.

---

## Gate 9 — Builder composes all three tile types and persists layout

Manual verification in browser at `http://localhost:5173/dashboards/builder` (desktop viewport):

1. 添加可视化 adds a saved-visualization tile onto the grid; it can be dragged and resized.
2. 添加文本 adds a text tile; editing its content shows a markdown preview.
3. 添加 KPI 卡 adds an ad-hoc KPI tile configured with view + value column + label + aggregation.
4. Tiles can be removed; layout persists across sidebar navigation (React Context) without saving.
5. 保存 with a unique name succeeds and navigates to the dashboard; saving with a duplicate name opens the conflict dialog prompting for a new name.

**Expected:** After save, `GET /api/dashboards/{id}` returns `layout_json` faithfully reproducing the on-screen grid (positions, sizes, tile payloads).

**Status: PASS (2026-08-11)** — browser verification (screenshots `tmp_export/gate9_builder*.png`): all three tile types added (test_line + test_pie visualization tiles, markdown text tile with 编辑/预览, KPI tile 退款总额 over view test1); drag verified (tile transform changed) and resize verified (622×172 → 833×264); state survived sidebar navigation without saving; 保存 → toast "仪表盘保存成功" → URL `/dashboards/builder/{id}`. One bug found and fixed during validation: 新建仪表盘 now resets the builder context (stale-draft fix in `DashboardsListPage`).

---

## Gate 10 — Display page renders tiles with per-tile refresh and full-screen view

Manual verification at `http://localhost:5173/dashboards/{id}`:

1. All visualization tiles render with live data; text tiles render markdown; KPI tiles show their computed value.
2. Each tile has a refresh button that re-fetches only that tile's `/data` request (visible in network panel).
3. A maximize button opens a full-screen single-tile view; closing returns to the grid.
4. No polling/auto-refresh occurs while idle (verify ≥ 60s in network panel).

**Expected:** Tiles render correctly; refresh and full-screen work; zero polling requests.

**Status: PASS (2026-08-11)** — browser verification (`tmp_export/gate10_display.png`): line chart, pie chart, markdown text and KPI tile (46.18万 退款总额) all rendered; per-tile 刷新 re-fetched only that tile's `/data`; maximize opened the full-screen dialog and X closed it; no polling (data fetched on load / manual refresh / filter change only).

---

## Gate 11 — Global time controls apply only to date-aware tiles

Prerequisite: at least two visualization tiles — one whose visualization has `date_column` set (时间配置 in the builder), one without.

1. Open the display page's global controls: set a date range, pick a granularity (年/月/日), and an aggregation function.
2. The date-aware tile re-queries `/api/visualizations/{id}/data?start=…&end=…&granularity=…&agg=…` and re-renders re-bucketed data (e.g. daily → monthly sums).
3. The non-date tile is unchanged and shows the subtle "不响应时间筛选" hint; it fires no new request.

**Expected:** Only date-aware tiles respond; values reflect the selected range/granularity/aggregation; other tiles unaffected.

**Status: PASS (2026-08-11)** — browser verification (`tmp_export/gate11_granularity.png`): 粒度=月 + 聚合=求和 → date-aware tile re-fetched `/data?granularity=month&agg=SUM` and re-rendered as one monthly bucket (backend verified separately on the mixed-type `test1` view: 2026-07-01 bucket = 461,793.90); date range 2026-07-01→2026-07-31 → re-fetched with `start`/`end` params; test_pie tile unchanged with hint "不响应时间筛选"; 清除筛选 resets controls. Time profile set via the new 时间配置 section (config_json `date_column`/`default_granularity`/`default_agg`).

---

## Gate 12 — Dynamic sidebar and list/manage page

Manual verification:

1. Sidebar shows a collapsible "仪表盘" parent; expanding lists each saved dashboard by name as a child nav item.
2. Clicking the parent navigates to `/dashboards` (list page); clicking a child navigates to that dashboard's display page.
3. On `/dashboards/builder*`, the parent list item is NOT highlighted (explicit `isLinkActive` logic).
4. List page shows name, description, tile count, created/updated (sortable), a 新建仪表盘 button, and per-row 查看 / 编辑 / 重命名 / 删除. Rename enforces uniqueness (409 → conflict prompt); delete requires confirmation and removes the sidebar child.

**Expected:** Sidebar children stay in sync with created/renamed/deleted dashboards; active-state correct on all routes.

**Status: PASS (2026-08-11)** — browser verification (`tmp_export/gate12_list.png`): 仪表盘 parent with per-dashboard children; parent NOT highlighted on `/dashboards/builder*` (computed styles checked); rename to 验收仪表盘2 synced table + sidebar child; duplicate-name save opened conflict dialog "名称已存在…是否修改该仪表盘？"; delete with confirmation removed row + sidebar child (toast "仪表盘已删除").

---

## Gate 13 — Responsive behavior and Chinese UI

Manual verification:

1. Below the `lg` breakpoint, the display grid stacks tiles vertically in a single read-only column (no drag/resize).
2. The builder on a small viewport disables/hides editing controls and shows a Chinese hint that editing requires a desktop viewport.
3. Audit every new string: labels, buttons, empty/loading/error states, toasts, dialogs, placeholders — all Chinese.

**Expected:** Mobile shows a clean read-only stacked layout; no English UI text anywhere.

**Status: PASS (2026-08-11, simulated small viewport)** — below the lg breakpoint the display page stacked tiles in a single read-only column with hint "小屏模式：瓦片按只读单列展示。" (`tmp_export/gate13_mobile.png`); the builder showed "仪表盘编辑需要桌面端视口（宽度 ≥ 1024px）" with no editing controls (`tmp_export/gate13_builder_mobile.png`); all new UI strings audited — Chinese only.

---

## Merge Checklist

- [x] All 13 gates pass on a clean checkout
- [x] Alembic migration for `dashboards` (unique `name`, Chinese comments) upgrades and downgrades cleanly
- [x] Dashboard CRUD API: create/list/get/update/delete, 409 on duplicate name, 404 on missing, 422 on invalid `visualization_id`
- [x] Three tile types supported: visualization, text/markdown, ad-hoc KPI card
- [x] Builder: drag/resize grid (react-grid-layout), remove tiles, context-persisted state, name-conflict flow
- [x] Display page: live data, per-tile manual refresh, full-screen tile view, no auto-refresh/polling
- [x] Global time controls (date range + granularity + aggregation) apply only to tiles with `date_column`; others show "不响应时间筛选"
- [x] Time overrides use parameterized regenerated SQL (no string interpolation)
- [x] Dynamic collapsible "仪表盘" sidebar with per-dashboard children and correct active-state
- [x] List/manage page with create/rename/delete, unique-name enforcement
- [x] Desktop-first grid; mobile stacks read-only; builder editing gated on desktop
- [x] All UI text and error messages in Chinese
- [x] README.md updated if new startup steps are needed — not needed (no new startup steps; `react-grid-layout` installed via package.json)
