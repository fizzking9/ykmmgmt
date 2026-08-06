# Phase 6 — Saved Data Views Management: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend View CRUD APIs

1. Create `GET /api/views` endpoint that lists all saved views. Return `id`, `name`, `description`, `created_at`, `updated_at` for each view. Order by `created_at` descending (newest first). Do NOT include `config_json` or `generated_sql` in the list response — those are only returned by the detail endpoint.

2. Create `GET /api/views/{id}` endpoint that returns the full view definition: `id`, `name`, `description`, `config_json`, `generated_sql`, `created_at`, `updated_at`. Return 404 if the view does not exist.

3. Create `GET /api/views/{id}/data` endpoint that executes the view's stored `generated_sql` and returns paginated results. Query parameters: `page` (default 1), `size` (default 20, max 100). Return `{rows, total, page, size}`. Return 404 if the view does not exist. Return 400 if the SQL execution fails.

4. Create `DELETE /api/views/{id}` endpoint that permanently deletes a view. Return 204 No Content on success, 404 if not found.

5. Add Pydantic response schemas for all four endpoints. Register routes in the FastAPI app. Verify OpenAPI docs at `/docs`.

## Group 2 — Frontend Views List Page

6. Add "数据视图" nav item to the sidebar (below "数据浏览", using a `LayoutGrid` or views icon). Wire up routing at `/views` in `App.tsx`.

7. Create `ViewsListPage.tsx`: table displaying all saved views fetched from `GET /api/views`. Columns: 名称 (name), 描述 (description), 创建时间 (created_at). Each row has four action buttons: 可视化 (placeholder, disabled with tooltip "即将推出"), 预览 (opens preview dialog), 编辑 (navigates to builder), 删除 (opens confirmation dialog).

8. Implement the Preview dialog: clicking 预览 on a view row opens a popup/dialog window. The dialog calls `GET /api/views/{id}/data` with pagination (page & size). Render the result in a paginated data grid reusing the same grid component pattern from Phase 4.5 Data Browser (Chinese column headers derived from the view's schema, Previous/Next pagination with page number input). Max 100 rows per page. Dialog has a close button and a title showing the view name.

9. Implement the Edit button: clicking 编辑 navigates to `/views/builder?id={view_id}`. The Phase 5 View Builder page must detect the `id` query parameter, fetch the full view config via `GET /api/views/{id}`, and pre-fill all builder sections (table selection, joins, columns, filters, groupings, computed columns) from the stored `config_json`. The builder's save action becomes an update (PUT) instead of create (POST) when editing an existing view.

10. Implement the Delete button: clicking 删除 opens a shadcn/ui AlertDialog with message "确定要删除视图「{name}」吗？此操作不可撤销。" Confirm calls `DELETE /api/views/{id}`, on success removes the row from the list (optimistic update via TanStack Query invalidation). Cancel closes the dialog.

11. Implement the Visualisation placeholder button: disabled state, uses a tooltip or title attribute reading "可视化功能将在后续版本中推出". No navigation or action on click.

## Group 3 — Integration & Polish

12. Create TanStack Query hooks: `useViews` (list all views), `useView` (single view by id), `useViewData` (paginated preview data), `useDeleteView` (delete with mutation invalidation). Add to `ykmmgmt/frontend/src/hooks/`.

13. Handle all states on the list page: loading skeleton (shadcn/ui Skeleton rows), empty state ("暂无保存的视图，请先创建数据视图"), error state with retry button.

14. Backend tests: add tests in `test_data_browser.py` (or a new `test_views.py`) covering list, detail, data execution, 404 handling, and delete.
