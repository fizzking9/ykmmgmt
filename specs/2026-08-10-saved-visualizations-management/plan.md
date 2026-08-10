# Phase 8 — Saved Visualizations Management: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

> Backend CRUD + data endpoints (`GET /api/visualizations`, `GET /api/visualizations/{id}`, `GET /api/visualizations/{id}/data`, `DELETE /api/visualizations/{id}`) and the TanStack Query hooks in `useVisualizations.ts` already exist. This phase is frontend-only; backend work is limited to regression testing.

---

## Group 1 — Sidebar & Visualizations List Page

1. Add "可视化" nav item to the sidebar (below "数据视图", using a `BarChart3` icon). Wire up routing at `/visualizations` in `App.tsx`.

2. Create `VisualizationsListPage.tsx`: table displaying all saved visualizations fetched via `useVisualizations()`. Columns: 缩略图 (thumbnail, chart types only), 名称 (name), 图表类型 (chart_type shown as Chinese badge: 表格/KPI 卡片/柱状图/折线图/饼图/散点图/直方图/箱线图), 来源视图 (source view name, resolved from `GET /api/views`), 创建时间 (formatted `created_at`). Each row has three action buttons: 查看, 编辑, 删除.

3. Implement static chart thumbnails: for chart-type visualizations (bar/line/pie/scatter/histogram/boxplot), render a small non-interactive Recharts preview using data from `GET /api/visualizations/{id}/data`. Table and KPI card types show NO thumbnail (show a type badge/placeholder instead). Thumbnail data is cached in TanStack Query with a long `staleTime` (e.g. `Infinity`) so it is fetched ONCE and survives tab navigation — switching to another page (sidebar tab) and coming back must NOT re-query or re-render thumbnails. Only the manual 刷新 button invalidates the cache and re-fetches.

4. Add a page-level 刷新 button: invalidates the thumbnail data cache and the visualization list, re-fetching and re-rendering thumbnails with possibly new data. Show a loading indicator while refreshing. This is the ONLY path that re-fetches thumbnail data.

5. Handle all list-page states: loading skeleton, empty state ("暂无保存的可视化，请先创建可视化"), error state with retry. Client-side pagination (20 rows/page) following the existing data grid pattern — pagination is purely client-side over the already-loaded list and never triggers data fetches.

## Group 2 — Full-Size View Page

6. Create `VisualizationViewPage.tsx` routed at `/visualizations/:id`. Fetch the visualization definition (`useVisualization`) and its live data (`useVisualizationData`), render full-size reusing the Phase 7 chart rendering component (extract a shared `VisualizationRenderer` from the builder preview if not already separated). Table charts render a paginated table; KPI cards render the metric card.

7. Add a 刷新 button on the view page: invalidates the `["visualizationData", id]` query to re-fetch live data on demand. NO auto-refresh / polling — data is only re-fetched when the user clicks 刷新.

8. Handle view-page states: 404/not-found message ("可视化不存在"), loading skeleton, SQL execution error shown as a Chinese error message with retry. Show the visualization name as page title and a 返回 link back to `/visualizations`.

## Group 3 — Edit & Delete Flows

9. Edit button: navigate to `/visualizations/builder/{id}`. Verify `VisualizationBuilderPage` detects the `:id` param, fetches the full definition via `GET /api/visualizations/{id}`, and pre-fills all builder sections (view selector, chart type, per-chart-type config). Saving an existing visualization issues PUT (update) instead of POST (create); after save, navigate back to `/visualizations`.

10. Delete button: shadcn/ui AlertDialog with message "确定要删除可视化「{name}」吗？此操作不可撤销。" Confirm calls `useDeleteVisualization`; on success the row disappears (query invalidation) and a success toast is shown. Cancel closes the dialog.

## Group 4 — Integration & Tests

11. Frontend tests (Vitest + RTL) in `src/test/`: list page renders rows and action buttons; thumbnail only rendered for chart types; refresh button triggers re-fetch; delete confirmation dialog behavior.

12. Backend regression: run existing `tests/test_visualizations.py` — no new backend changes expected, all existing tests must still pass.
