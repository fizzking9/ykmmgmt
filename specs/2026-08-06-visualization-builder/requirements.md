# Phase 7 — Visualization Builder: Requirements

## Scope

Deliver a full-stack visualization builder that lets users pick a saved data view, choose a chart type, configure chart-specific options, preview the result with live data, and save it. The builder supports eight chart types: Table, KPI Card, Bar Chart, Line Chart, Pie Chart, Scatter Plot, Histogram, and Boxplot.

Users can enter the builder from two paths:
- **Views list page** — click the "可视化" button on any saved view to open the builder with that view pre-selected
- **Visualization builder page** — select a view from the dropdown at any time during configuration

Beyond the core roadmap items, this phase includes:
- Chart title and axis label customization
- Color theme picker with preset palettes
- Number formatting options (decimal places, thousands separator, currency prefix)
- PNG export of the preview area
- Shareable link copying
- Distribution analysis charts (Histogram, Boxplot) for exploring numeric variable distributions
- Semantically correct bar charts: X-axis and grouping restricted to categorical columns, with a user-selected aggregation function (SUM/AVG/COUNT/MIN/MAX) applied to the Y values per category

The live preview uses the **full dataset** from the selected view (not a 20-row sample), since the visualization is built on the view's data and should reflect the complete picture at configuration time. Auto-refresh / polling is deferred to Phase 8.

## Context (from mission.md)

YKMMgmt exists to "surface what matters" — presenting key performance indicators through interactive metric cards, charts, and filterable data tables. Phase 7 is the first phase that delivers on this promise. The visualization builder transforms raw data views into visual artifacts that make trends, outliers, and KPIs immediately visible to internal teams.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Charting library | Evaluate Recharts vs alternatives (visx, Nivo) before committing | Recharts is in tech-stack.md but we should verify it handles all six chart types well, especially scatter plots and theming. If it falls short, we switch early rather than mid-implementation. Histogram/Boxplot were added later and are composed from Recharts primitives (bars for bins; range-bar + custom shape for the box). |
| Histogram rendering | Shared bins across selected columns, overlaid semi-transparent bars (full bin width per column) | Histograms compare distributions, so multiple columns must layer on top of each other rather than sit side-by-side; recharts' default grouped bars are overridden with a custom bar shape that spans the whole bin. Bin count is user-configurable (default 20). |
| Boxplot rendering | Client-side five-number summary (linear-interpolation quartiles, 1.5×IQR whiskers, explicit outliers) drawn as a range-bar with a custom SVG shape | Recharts has no native boxplot; the custom shape keeps the standard statistical definition and works with an optional categorical split. |
| Preview data source | Full dataset from view (not paginated sample) | The visualization should reflect the complete data at configuration time. The view's SQL already handles filtering/aggregation, so the result set should be manageable. |
| Auto-refresh | Deferred to Phase 8 | Keeps Phase 7 focused on the builder experience. Phase 8 (Saved Visualizations Management) is a better place for live data refresh since that's where visualizations are displayed standalone. |
| State persistence | React Context (VisualizationBuilderContext) above router | Same pattern as ViewBuilderContext — preserves builder state across navigation so users don't lose work. |
| Config validation | Backend validates config_json keys per chart_type | Prevents invalid configurations from being saved. Each chart type has a defined set of required keys. |
| Export approach | html2canvas or chart library built-in export | PNG export captures the rendered preview area. Simple and works across all chart types. |
| UI language | Chinese | All user-facing text in Chinese per project convention. |

## Constraints

- Must use existing `GET /api/views` and `GET /api/views/{id}/data` endpoints for view selection and data fetching
- The `view_id` FK links visualizations to views — deleting a view should be handled gracefully (either cascade or restrict)
- Chart config_json schema varies per chart_type; backend must validate required keys on create/update
- Full dataset fetch for preview may need a new query param on the view data endpoint (e.g. `size=0` for all rows) or a high page size limit
- Responsive layout: configuration panel + preview must stack on mobile viewports
- All existing tests must continue to pass

## Out of Scope

- Auto-refresh / polling for live data updates (Phase 8)
- Dashboard composition or grid layout (Phase 9)
- Visualizations list page, edit-from-list, delete-from-list (Phase 8)
- Sidebar "Visualizations" section with saved items (Phase 8)
- Sharing visualizations outside the app (public URLs, embedding)
- Custom color picker (only preset palettes in this phase)
- Drill-down or interactive chart features (click to filter, zoom, etc.)
