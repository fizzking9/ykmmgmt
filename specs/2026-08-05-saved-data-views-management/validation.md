# Phase 6 — Saved Data Views Management: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Backend linting

```bash
cd ykmmgmt/backend && ruff check .
```

**Expected:** Zero errors, zero warnings.

---

## Gate 2 — Frontend linting

```bash
cd ykmmgmt/frontend && npx eslint src/ --ext .ts,.tsx
```

**Expected:** Zero errors, zero warnings.

---

## Gate 3 — Frontend type-check

```bash
cd ykmmgmt/frontend && npx tsc --noEmit
```

**Expected:** Zero type errors.

---

## Gate 4 — Backend tests

```bash
cd ykmmgmt/backend && python -m pytest tests/ -v
```

**Expected:** All existing tests pass. New tests for view CRUD endpoints (list, detail, data execution, 404, delete) pass.

---

## Gate 5 — Frontend tests

```bash
cd ykmmgmt/frontend && npx vitest run
```

**Expected:** All existing tests pass, zero failures.

---

## Gate 6 — GET /api/views returns saved views list

✅ PASS

```bash
curl -s http://localhost:8000/api/views | python -m json.tool
```

**Expected:** JSON array of view objects. Each object has `id`, `name`, `description`, `created_at`, `updated_at`. Must NOT include `config_json` or `generated_sql`. Ordered by `created_at` descending (newest first).

---

## Gate 7 — GET /api/views/{id} returns full view definition

✅ PASS

```bash
curl -s http://localhost:8000/api/views/1 | python -m json.tool
```

**Expected:** JSON object with `id`, `name`, `description`, `config_json`, `generated_sql`, `created_at`, `updated_at`. Both `config_json` and `generated_sql` are present and non-empty. Requesting a non-existent id returns 404.

---

## Gate 8 — GET /api/views/{id}/data returns paginated executed results

✅ PASS

```bash
curl -s "http://localhost:8000/api/views/1/data?page=1&size=10" | python -m json.tool
```

**Expected:** JSON object with `rows` (array, max 10 items), `total` (integer), `page` (1), `size` (10). `rows` contains the result of executing the view's `generated_sql`. Requesting a non-existent id returns 404.

Verify max size enforcement:
```bash
curl -s "http://localhost:8000/api/views/1/data?page=1&size=200" | python -m json.tool
```
**Expected:** Either `size` is capped at 100 or returns 422 validation error.

---

## Gate 9 — DELETE /api/views/{id} permanently removes a view

✅ PASS

```bash
curl -s -o /dev/null -w "%{http_code}" -X DELETE http://localhost:8000/api/views/1
```

**Expected:** HTTP 204 No Content. A subsequent `GET /api/views/1` returns 404. Deleting a non-existent id returns 404.

---

## Gate 10 — Views list page renders with action buttons

✅ PASS

Manual verification in browser at `http://localhost:5173/views`:

1. Page loads showing a table with columns: 名称, 描述, 创建时间
2. If views exist in the database, each row shows the view's name, description, and formatted creation date
3. Each row has four action buttons: 可视化 (disabled), 预览, 编辑, 删除
4. The 可视化 button is visually disabled and shows a tooltip "即将推出" on hover
5. If no views exist, an empty state message "暂无保存的视图，请先创建数据视图" is displayed

---

## Gate 11 — Preview dialog shows paginated data

✅ PASS

Manual verification in browser at `http://localhost:5173/views`:

1. Click 预览 on a view row → a dialog/popup opens with the view name as the title
2. The dialog contains a paginated data grid with data from the view's SQL execution
3. Column headers are displayed (derived from the query result)
4. Previous/Next pagination buttons and page number input work within the dialog
5. Maximum 100 rows per page
6. Close button (✕ or 关闭) dismisses the dialog

---

## Gate 12 — Edit navigates to builder pre-filled

✅ PASS

Manual verification in browser at `http://localhost:5173/views`:

1. Click 编辑 on a view row → browser navigates to `/views/builder?id=<view_id>`
2. The Phase 5 View Builder page loads with all sections pre-filled from the saved view's `config_json`:
   - Selected table(s) match the saved config
   - Joins (if any) are populated
   - Selected columns are checked/configured
   - Filters are populated
   - Groupings and aggregations are set
   - Computed columns (if any) are shown
3. Changing config and clicking save triggers a PUT (update) instead of POST (create)
4. After saving, the view's `updated_at` timestamp changes

---

## Gate 13 — Delete with confirmation works

✅ PASS

Manual verification in browser at `http://localhost:5173/views`:

1. Click 删除 on a view row → a confirmation dialog appears with the view name in the message: "确定要删除视图「{name}」吗？此操作不可撤销。"
2. Clicking "取消" closes the dialog, the view remains in the list
3. Clicking "确定" sends the DELETE request, the dialog closes, and the view row is removed from the list
4. Refreshing the page confirms the view is gone

---

## Gate 14 — Sidebar navigation

✅ PASS

Manual verification in browser:

1. Sidebar shows "数据视图" nav item (below "数据浏览")
2. Clicking "数据视图" navigates to `/views`
3. The nav item is highlighted/active when on the Views List page
4. On mobile, the sidebar can be toggled open and "数据视图" is visible and clickable

---

## Merge Checklist

- [x] All 14 gates pass on a clean checkout
- [x] No new database migrations introduced (views table already exists)
- [x] All UI text is in Chinese (no English labels visible on the views list page or preview dialog)
- [x] Four action buttons per view row: 可视化 (disabled placeholder), 预览, 编辑, 删除
- [x] Preview dialog shows paginated data (max 100 rows/page) in a popup
- [x] Edit navigates to `/views/builder/{id}` and pre-fills the Phase 5 builder
- [x] Delete shows confirmation dialog and permanently removes the view
- [x] GET /api/views list response excludes config_json and generated_sql
- [x] Empty state shows Chinese message when no views exist
- [x] README.md updated if new startup steps are needed
