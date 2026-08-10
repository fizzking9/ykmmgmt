# Phase 7 — Visualization Builder: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Backend linting

```bash
cd ykmmgmt/backend && ruff check app/ tests/
```

**Expected:** Zero errors, zero warnings.

**Status: PASS** (2026-08-10) — `All checks passed!`

---

## Gate 2 — Backend tests

```bash
cd ykmmgmt/backend && python -m pytest tests/ -v
```

**Expected:** All test suites pass, zero failures. Includes new `test_visualizations.py` covering CRUD, validation, and data endpoint.

**Status: PASS** (2026-08-10) — 83 passed, 0 failures.

---

## Gate 3 — Frontend linting

```bash
cd ykmmgmt/frontend && npm run lint
```

**Expected:** Zero errors, zero warnings.

**Status: PASS** (2026-08-10) — `eslint src --max-warnings=0` clean.

---

## Gate 4 — Frontend formatting

```bash
cd ykmmgmt/frontend && npm run format
```

**Expected:** Zero unformatted files (no diff after running).

**Status: PASS** (2026-08-10) — `prettier --check src` all clean.

---

## Gate 5 — Frontend tests

```bash
cd ykmmgmt/frontend && npm run test
```

**Expected:** All test suites pass, zero failures. Includes new visualization builder component tests.

**Status: PASS** (2026-08-10) — 24 tests passed (3 files).

---

## Gate 6 — Database migration

```bash
cd ykmmgmt/backend && alembic upgrade head
```

**Expected:** Migration applies cleanly. `visualizations` table exists with correct columns and FK to `views`.

**Status: PASS** (2026-08-10) — `alembic upgrade head` at revision `4f11ac803470`.

---

## Gate 7 — Visualization CRUD round-trip

Manual steps:
1. Start backend (`uvicorn main:app --reload`) and frontend (`npm run dev`)
2. Create a visualization via API or UI with a valid view_id, chart_type, and config
3. Verify it appears in `GET /api/visualizations`
4. Update its name via `PUT /api/visualizations/{id}`
5. Fetch it via `GET /api/visualizations/{id}` — verify updated name
6. Delete it via `DELETE /api/visualizations/{id}`
7. Verify it's gone from `GET /api/visualizations`

**Expected:** All operations succeed with correct responses. Invalid chart_type or missing config keys return 422.

**Status: PASS** (2026-08-10) — full round-trip scripted: CREATE 201 → LIST found → UPDATE 200 → GET 200 (updated name) → DELETE 204 → gone. Invalid chart_type 422, missing config keys 422.

---

## Gate 8 — Visualization data endpoint

Manual steps:
1. Create a visualization linked to a saved view
2. Call `GET /api/visualizations/{id}/data`
3. Verify response contains `columns`, `rows`, `chart_type`, `config_json`
4. Verify rows match the view's data

**Expected:** Full result set returned (not paginated). Datetime and UUID values serialized as strings.

**Status: PASS** (2026-08-10) — returns `columns`, `rows`, `chart_type`, `config_json`; filtered view test1 returned all 7,071 rows. Note: a bug was found and fixed during validation — the endpoint executed the stored `generated_sql` without bind params, failing on filtered views; it now regenerates SQL + params from the view's stored config (same as `/api/views/{id}/data`).

---

## Gate 9 — Dual entry points for view selection

Manual steps:
1. Navigate to `/views` (views list page)
2. Click the "可视化" button on any saved view
3. Verify the builder opens at `/visualizations/builder?view_id={id}` with that view pre-selected and its columns loaded
4. Switch to a different view using the dropdown in the builder — verify config panel updates with new columns
5. Navigate directly to `/visualizations/builder` (no query param)
6. Select a view from the dropdown — verify it works the same as entry point A

**Expected:** Both entry points work. The "可视化" button on the views list page is enabled and navigates correctly. The builder's view selector dropdown works independently.

**Status: PASS** (2026-08-10) — views-list "可视化" button navigated to `/visualizations/builder?view_id={id}` with test1 pre-selected; direct navigation + dropdown selection also verified.

---

## Gate 10 — Builder page renders and configures

Manual steps:
1. Navigate to `/visualizations/builder`
2. Select a view from the dropdown — column list populates
3. Click each chart type tile — config panel updates with type-specific fields
4. For Bar chart: select X-axis and Y-axis columns — preview renders a bar chart
5. For KPI Card: select value column and enter label — preview renders a KPI card
6. For Pie chart: select label and value columns — preview renders a pie chart

**Expected:** All eight chart types render in the preview. Config panel shows correct fields per type. All UI text in Chinese.

**Status: PASS** (2026-08-10) — all 8 tiles present; bar (服务项 × 退款金额), KPI card (461,793.90 over 7,071 records), and pie (6 sectors) previews rendered live.

---

## Gate 11 — Preview uses full data

Manual steps:
1. Select a view that returns more than 20 rows
2. Configure a bar chart
3. Inspect the preview — count distinct X-axis values or check data point count

**Expected:** Preview renders all rows from the view, not limited to 20.

**Status: PASS** (2026-08-10) — KPI computed over all 7,071 rows of test1; scatter capped only for rendering performance (2,000-point stride sample), data fetch is full.

---

## Gate 12 — Save and edit flow

Manual steps:
1. Configure a visualization, enter a name, click Save
2. Verify success toast appears
3. Navigate to `/visualizations/builder/{id}` (use the saved ID)
4. Verify all fields are pre-filled with the saved config
5. Modify the chart type or config, click Save (Update)
6. Verify update succeeds

**Expected:** Create and update both work. Edit mode pre-fills all configuration correctly.

**Status: PASS** (2026-08-10) — saved from builder (toast + redirect to `/visualizations/builder/{id}`); reload pre-filled name/chart type/columns; 更新 succeeded.

---

## Gate 13 — Export and share

Manual steps:
1. Configure a visualization with any chart type
2. Click Export PNG — a PNG file downloads
3. Click Share / Copy Link — clipboard contains the builder URL with the visualization ID

**Expected:** PNG export captures the chart preview. Share link is a valid URL that loads the builder pre-filled.

**Status: PASS** (2026-08-10) — export toast "PNG 导出成功"; clipboard captured `/visualizations/builder/{id}` link. Bottom-edge caption clipping fixed earlier (padding on capture target).

---

## Gate 14 — Responsive layout

Manual steps:
1. Open the visualization builder on a mobile viewport (375px width)
2. Verify config panel and preview stack vertically
3. Verify all controls are usable (dropdowns, inputs, buttons)

**Expected:** Layout adapts to mobile. No horizontal overflow. All interactive elements accessible.

**Status: PASS** (2026-08-10) — layout grid is `grid-cols-1` stacking below the `lg` breakpoint (`lg:grid-cols-2`), viewport meta present, no horizontal overflow measured.

---

## Gate 15 — Distribution charts and bar semantics

Manual steps:
1. Bar chart: open the X-axis dropdown — only categorical (non-numeric, non-date) columns are listed; group-by follows the same restriction
2. Change the 聚合方式 selector (求和/平均值/计数/最小值/最大值) — bar heights update per category
3. Scatter plot: pick two numeric columns (X and Y) — points render and the Y axis is present
4. Line chart with a group-by column: legend shows class names only, points are visible, and each class has a distinct marker shape
5. Histogram: select one numeric column — bins render with counts on Y; select a second column — both distributions overlay in the same bins with distinct semi-transparent colors (not side-by-side); change 分箱数 — bin count updates
6. Boxplot: select a numeric column — one box with whiskers, median line, and outlier dots renders; add a categorical column — one box per category; hover shows the five-number summary

**Expected:** All behaviors above work on the full view dataset. Saving histogram/boxplot visualizations succeeds via `POST /api/visualizations`.

**Status: PASS** (2026-08-10) — all six behaviors verified in-browser on full datasets: categorical-only bar X/group dropdowns + 聚合方式 cross-checked against direct DB aggregation; scatter renders numeric X/Y with both axes (plus per-category shapes, matching legend icons, and category-aware tooltips); line legend shows class names with distinct symbols; histogram overlays distributions (full-bin-width semi-transparent bars) with configurable 分箱数; boxplot quartiles matched PostgreSQL `percentile_cont`. Histogram/boxplot accepted by `POST /api/visualizations` (backend tests).

---

## Merge Checklist

- [x] All 15 gates pass on a clean checkout
- [x] `visualizations` table migration applies cleanly
- [x] Visualization CRUD endpoints work with validation (including histogram/boxplot config keys)
- [x] Visualization data endpoint returns full result set
- [x] Dual entry points work: views list "可视化" button and builder view selector
- [x] Builder page renders all eight chart types with per-type config panels
- [x] Bar charts aggregate categorical X values with the selected aggregation function
- [x] Scatter plots render numeric X/Y data with both axes
- [x] Histogram and Boxplot previews render distributions correctly
- [x] Preview uses full view data (not 20-row sample)
- [x] Save and edit flows work end-to-end
- [x] PNG export and share link work
- [x] Responsive layout verified on mobile viewport
- [x] All UI text in Chinese
- [x] Backend and frontend linting, formatting, and tests pass
