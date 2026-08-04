# Phase 4.5 — Data Browser: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend Table Discovery API

1. Create `GET /api/tables` endpoint that lists business data tables only (`refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`). Each entry returns the English table name and its Chinese display name (from a hardcoded mapping). Exclude internal tables (`datasources`, `import_jobs`, `alembic_version`).

2. Create `GET /api/tables/{name}/schema` endpoint that returns column metadata for a given table. Inspect the SQLAlchemy model: for each column return the column name (`key`), Python type, and its Chinese alias (from the column's `comment` attribute). Hide internal-only columns (`id`, `imported_at`, `content_hash`).

3. Create `GET /api/tables/{name}/data` endpoint that returns paginated, filtered, and sorted rows. Query parameters:
   - `page` (default 1), `size` (default 20, max 200)
   - Date filter: `datetime_col`, `start`, `end` (existing)
   - Column value filter: `filter_col` (repeated), `filter_value` (repeated), `filter_mode` (repeated, "contains"|"exact"). Positional pairing — filter_col[0] with filter_value[0] and filter_mode[0].
   - Sort: `sort_col` (column name), `sort_dir` ("asc"|"desc", default "asc")
   - Apply column filters as AND conditions. Apply sort as ORDER BY after filtering. Return `{rows, total, page, size}`.

4. Add Pydantic response schemas for all three endpoints. Add route registration in the FastAPI app. Verify the OpenAPI docs auto-generate correctly at `/docs`.

## Group 2 — Frontend Data Browser UI

5. Add "数据浏览" nav item to the sidebar (below "导入历史", using a `Table` or database icon).

6. Create `DataBrowserPage.tsx`: table selector dropdown populated from `GET /api/tables`. Dropdown shows Chinese table names. Selecting a table triggers schema fetch and data fetch.

7. Implement paginated data grid: fixed 20 rows per page, Previous/Next buttons, page number input. Use TanStack Query for data fetching with `keepPreviousData` for smooth page transitions. Display Chinese column headers from schema response.

8. Implement sortable column headers: clicking a column header cycles through no-sort → ascending (▲) → descending (▼) → no-sort. Sort indicator arrow displayed next to the column name. Sorting combines with active filters.

9. Implement column value filter: below the datetime filter card, add a "筛选条件" section. Each filter row has a column dropdown (all non-hidden columns), match mode toggle (包含/精确), value text input, and a remove button. An "添加筛选条件" button appends a new filter row. All column filters AND together with the datetime filter.

10. Wire up routing: add `/data-browser` route in `App.tsx`. Add TanStack Query hook (`useTables.ts`) for table listing.

11. Display total row count above the data grid. Show a "loading" skeleton while data fetches. Handle empty states (no tables, no data matching filters/sort).
