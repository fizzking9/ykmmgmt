# Phase 7 — Visualization Builder: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend: Visualization Model & Migration

1. Create `Visualization` SQLAlchemy model in `app/models/visualization.py` with fields: `id` (UUID PK), `name` (String 255), `view_id` (UUID FK → views.id), `chart_type` (String 50 — one of `table`, `kpi_card`, `bar`, `line`, `pie`, `scatter`, `histogram`, `boxplot`), `config_json` (JSONB — chart-specific configuration), `created_at`, `updated_at` (DateTime with timezone)
2. Add Chinese comments on all model fields (e.g. `comment="可视化名称"`)
3. Register the model in `app/models/__init__.py`
4. Generate Alembic migration for the new `visualizations` table
5. Verify migration applies cleanly: `alembic upgrade head`

## Group 2 — Backend: Pydantic Schemas & CRUD Endpoints

1. Create `app/schemas/visualization.py` with request/response models:
   - `VisualizationCreate` — name, view_id, chart_type, config_json
   - `VisualizationUpdate` — optional name, view_id, chart_type, config_json
   - `VisualizationResponse` — full detail including config_json
   - `VisualizationListResponse` — summary (id, name, chart_type, view_id, created_at, updated_at)
2. Create `app/routers/visualizations.py` with endpoints:
   - `POST /api/visualizations` — create; validate view_id exists, validate chart_type is in allowed set, validate config_json keys match chart_type requirements
   - `PUT /api/visualizations/{id}` — update; same validation
   - `GET /api/visualizations` — list all (summary)
   - `GET /api/visualizations/{id}` — full detail
   - `DELETE /api/visualizations/{id}` — delete
3. Register router in `main.py`
4. Add config validation logic: per chart_type, define required config_json keys (e.g. bar requires `x_column`, `y_columns`; kpi_card requires `value_column`, `label`)

## Group 3 — Backend: Visualization Data Endpoint

1. Add `GET /api/visualizations/{id}/data` — executes the associated view's stored SQL, returns full result set (not paginated) formatted for chart consumption
2. Response includes: `columns` (list of column names), `rows` (list of row dicts), `chart_type`, `config_json` (echoed back for convenience)
3. Handle datetime/UUID serialization (same pattern as views router)
4. Add error handling: view not found, visualization not found, SQL execution failure

## Group 4 — Backend: Tests

1. Create `tests/test_visualizations.py` with tests for:
   - Create visualization (success + invalid chart_type + invalid view_id + missing config keys)
   - Update visualization (success + not found)
   - List visualizations
   - Get visualization detail
   - Delete visualization
   - Get visualization data (verify rows returned from view SQL)
2. Ensure all existing tests still pass

## Group 5 — Frontend: Chart Library Evaluation & Installation

1. Evaluate Recharts vs alternatives (e.g. visx, Nivo) for the six chart types needed
2. Install chosen charting library and any peer dependencies
3. Verify library renders correctly with a smoke-test component

## Group 6 — Frontend: Visualization Builder Page — Core Layout

1. Create `VisualizationBuilderPage.tsx` with route `/visualizations/builder/:id?` (id optional for edit mode)
2. Add route to `App.tsx`
3. Layout: left panel for configuration, right panel for live preview (responsive — stacks on mobile)
4. Add "Visualization Builder" nav item to sidebar (or integrate into a "Visualizations" section)
5. Create `VisualizationBuilderContext` for state persistence across navigation (same pattern as ViewBuilderContext)

## Group 7 — Frontend: View Selection (Dual Entry Points)

1. **Entry point A — Views list page:** Enable the existing disabled "可视化" button on the views list page (`ViewsListPage.tsx`). Clicking it navigates to `/visualizations/builder?view_id={id}` — the builder opens with that view pre-selected.
2. **Entry point B — Visualization builder page:** View selector dropdown populated from `GET /api/views` — shows view name + description. User can switch views at any time during configuration.
3. On view selection (either entry point), fetch view data (`GET /api/views/{id}/data`) to get column list for config panel
4. If `view_id` query param is present on load, auto-select that view and skip the empty state
5. Chart type selector: card/tile grid showing 8 chart types with icons (Table, KPI Card, Bar Chart, Line Chart, Pie Chart, Scatter Plot, Histogram, Boxplot)
6. Selected chart type highlighted; switching chart type resets config_json to defaults for that type

## Group 8 — Frontend: Per-Chart Configuration Panel

1. **Table config:** column visibility toggles (checkbox per column), default sort column dropdown, sort direction toggle
2. **KPI Card config:** value column dropdown (numeric columns only), label text input, optional comparison/target value input
3. **Bar / Line / Scatter config:** X-axis column dropdown, Y-axis column(s) multi-select, optional color/group-by column dropdown. For Bar charts, X-axis and group-by are restricted to categorical (non-numeric, non-date) columns and an aggregation selector (SUM/AVG/COUNT/MIN/MAX) is applied to the Y values per category
4. **Pie config:** label column dropdown, value column dropdown (numeric columns only)
5. **Histogram config:** numeric column(s) multi-select, configurable bin count, title/axis label inputs
6. **Boxplot config:** optional categorical column dropdown, numeric value column dropdown, title/axis label inputs
7. All dropdowns populated from the selected view's column list
8. Chart title input, axis label inputs (for applicable chart types)
9. Color theme picker — preset palette selector (4-6 built-in themes)
10. Number formatting options — decimal places, thousands separator toggle, currency prefix (for KPI Card and axis labels)
11. All UI text in Chinese

## Group 9 — Frontend: Live Preview with Full Data

1. Preview panel renders the configured chart using the full dataset from the selected view (not limited to 20 rows)
2. Fetch full view data via `GET /api/views/{id}/data?page=1&size=100` (or add a `size=0` / `all=true` param for full fetch)
3. Show loading skeleton while data is fetching
4. Show error state if view data fetch fails
5. Preview updates in real-time as config changes (debounced)

## Group 10 — Frontend: Save / Update & Navigation

1. Name input (required) and description input (optional) at top of builder
2. Save button — creates visualization via `POST /api/visualizations`
3. If editing (id param present), load existing visualization config and pre-fill all panels; Save becomes Update via `PUT /api/visualizations/{id}`
4. After save, navigate to `/visualizations` list page (Phase 8 will build this; for now navigate back or show toast)
5. TanStack Query hooks: `useVisualizations`, `useVisualization`, `useCreateVisualization`, `useUpdateVisualization`, `useDeleteVisualization`, `useVisualizationData`

## Group 11 — Frontend: Export / Share

1. Export chart as PNG — use html2canvas or chart library's built-in export to capture the preview area
2. Copy shareable link — copies the visualization builder URL with id param to clipboard
3. Export button and share button in the builder toolbar

## Group 12 — Frontend: Tests

1. Component tests for visualization builder page (rendering, view selection, chart type switching)
2. Test config panel renders correct fields per chart type
3. Test preview renders with mock data
4. Ensure all existing tests pass

## Group 13 — Integration & Polish

1. Verify full flow: select view → pick chart type → configure → preview → save
2. Verify edit flow: load existing visualization → modify → update
3. Verify responsive layout on mobile viewport
4. Verify all Chinese UI text
5. Run linting and formatting checks

## Group 14 — Distribution Charts (Histogram & Boxplot) and Bar Semantics

Added after the initial release to support distribution analysis:

1. Backend: extend `CHART_TYPES` / `ChartType` in `app/schemas/visualization.py` with `histogram` and `boxplot`; add required config keys (`histogram`: `columns`, `bins`; `boxplot`: `category_column`, `value_column`)
2. Frontend context: add the two chart types plus default configs (`histogram`: columns/bins/title/labels; `boxplot`: category_column/value_column/title/labels)
3. **Bar chart semantics:** X-axis and group-by dropdowns list only categorical columns; a 聚合方式 selector drives per-category aggregation (`aggregateCategoricalRows`); legacy date-X configs keep the time-series bucketing path
4. **Scatter fix:** normalize points to numeric x/y and give the YAxis an explicit `dataKey` so numeric scatter plots render (previously nothing was drawn and the Y axis was absent)
5. **Line class encoding:** legend shows the class name only (single Y column); solid lines with visible points; per-class point symbols (circle/square/triangle/diamond/cross/star) replace dash patterns
6. **Histogram preview:** shared bins across selected numeric columns, Y = count per bin, configurable bin count; multiple columns are overlaid (not side-by-side) via a custom bar shape spanning the full bin width with semi-transparent fills so distributions can be compared; click-to-toggle legend
7. **Boxplot preview:** per-category five-number summary (linear-interpolation quartiles, 1.5×IQR whiskers, outlier dots) rendered via a q1–q3 range bar with a custom SVG shape; optional categorical X (top-N by frequency); tooltip shows the full summary
8. Tests: frontend config-panel tests for the new types and bar aggregation selector; backend CRUD tests accepting `histogram`/`boxplot` and rejecting missing required keys
