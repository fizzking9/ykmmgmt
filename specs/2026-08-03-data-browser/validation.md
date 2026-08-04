# Phase 4.5 — Data Browser: Validation

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

**Expected:** All existing tests pass. New tests for the Data Browser endpoints (optional but encouraged) pass.

---

## Gate 5 — Frontend tests

```bash
cd ykmmgmt/frontend && npx vitest run
```

**Expected:** All existing tests pass, zero failures.

---

## Gate 6 — GET /api/tables returns business tables only

```bash
curl -s http://localhost:8000/api/tables | python -m json.tool
```

**Expected:** JSON array containing exactly these tables with English names and Chinese display names:
- `refund_orders` → `退费单`
- `service_refund_work_orders` → `服务退款工单`
- `wallet_withdrawals` → `钱包提现操作`

Must NOT include `datasources`, `import_jobs`, or `alembic_version`.

---

## Gate 7 — GET /api/tables/{name}/schema returns Chinese column headers

```bash
curl -s http://localhost:8000/api/tables/refund_orders/schema | python -m json.tool
```

**Expected:** JSON array of column objects, each with `name` (English), `type`, and `label` (Chinese from model comment). Columns `id`, `imported_at`, `content_hash` must be absent. For example, `refund_order_no` must have label `退费单号`.

---

## Gate 8 — GET /api/tables/{name}/data with pagination

```bash
curl -s "http://localhost:8000/api/tables/refund_orders/data?page=1&size=10" | python -m json.tool
```

**Expected:** JSON object with `rows` (array, max 10 items), `total` (integer), `page` (1), `size` (10). If the database has fewer than 10 rows, `rows` length equals the actual row count.

---

## Gate 9 — GET /api/tables/{name}/data with column value filter

```bash
curl -s "http://localhost:8000/api/tables/refund_orders/data?page=1&size=20&datetime_col=record_created_at&start=2026-06-01&end=2026-07-31&filter_col=status&filter_value=已完成&filter_mode=exact&filter_col=operator&filter_value=张&filter_mode=contains" | python -m json.tool
```

**Expected:** `rows` contains only records where `record_created_at` falls within June–July 2026 AND `status` equals "已完成" AND `operator` contains "张". `total` reflects the combined filter count.

---

## Gate 10 — GET /api/tables/{name}/data with sorting

```bash
curl -s "http://localhost:8000/api/tables/refund_orders/data?page=1&size=20&sort_col=refund_amount&sort_dir=desc" | python -m json.tool
```

**Expected:** `rows` ordered by `refund_amount` descending (largest first). Verify the first few rows have higher or equal amounts compared to later rows.

---

## Gate 11 — Data Browser page renders and navigates tables

Manual verification in browser at `http://localhost:5173/data-browser`:

1. Page loads with a table selector dropdown showing Chinese table names (`退费单`, `服务退款工单`, `钱包提现操作`)
2. Selecting `退费单` populates a data grid with Chinese column headers and paginated rows
3. Prev/Next buttons and page number input navigate between pages
4. If the table has datetime columns, a datetime filter section appears with a column picker and date range inputs
5. Applying a date range filter re-fetches and displays filtered data

## Gate 12 — Column value filter UI

Manual verification in browser at `http://localhost:5173/data-browser`:

1. Below the datetime filter card, a "筛选条件" section is visible
2. Each filter row contains: column dropdown (all visible columns), match mode toggle (包含/精确), value text input, and a remove button
3. "添加筛选条件" button adds a new filter row
4. Applying a filter re-fetches and displays filtered data
5. Multiple filters combine with AND logic (both with each other and with the datetime filter)

---

## Gate 13 — Sortable column headers

Manual verification in browser at `http://localhost:5173/data-browser`:

1. Clicking a column header sorts ascending (▲ arrow appears next to the column name)
2. Clicking again sorts descending (▼ arrow appears)
3. Clicking a third time clears the sort (no arrow)
4. Sorting combines correctly with active filters (filtered results are sorted)
5. Changing pages preserves the sort order

---

## Gate 14 — Sidebar navigation

Manual verification in browser:

1. Sidebar shows "数据浏览" nav item (between "导入历史" and "Dashboard")
2. Clicking "数据浏览" navigates to `/data-browser`
3. The nav item is highlighted/active when on the Data Browser page
4. On mobile, the sidebar can be toggled open and "数据浏览" is visible and clickable

---

## Merge Checklist

- [x] All 14 gates pass on a clean checkout
- [x] No new database migrations introduced
- [x] All UI text is in Chinese (no English labels visible on the Data Browser page)
- [x] Business tables only — no internal/system tables exposed in the table selector
- [x] Chinese column headers displayed in the data grid (not English column names)
- [x] Pagination works correctly (page number, Prev/Next, row count)
- [x] Datetime filter works for tables that have datetime columns
- [x] Column value filter works with contains and exact modes, supports multiple simultaneous filters
- [x] Sortable headers work with 3-state cycling and arrow indicators
- [x] Filters and sort compose correctly (filter first, then sort)
- [x] README.md updated if new startup steps are needed
