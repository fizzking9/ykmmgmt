# Phase 4.5 — Data Browser: Requirements

## Scope

Deliver a Data Browser page where users can select a business data table, browse its rows with pagination, filter by column values, sort by columns, and filter by a datetime column.

**Included:**
- Backend APIs to list tables, expose column schemas, and serve paginated/filtered/sorted data
- Frontend page with table selector, paginated data grid, datetime range filter, column value filter, and sortable column headers
- Chinese display names for table names and column headers throughout the UI
- Sidebar navigation item linking to the Data Browser

**Explicitly excluded:**
- Editing, deleting, or adding rows (read-only browser)
- Export or download functionality
- Full-text search across all columns

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. The Data Browser lets operations and finance teams inspect imported data directly — verifying uploads, checking recent entries, and filtering by time period — without needing to query the database manually. It turns raw database tables into an accessible, browsable view within the same dashboard they already use.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Table discovery | SQLAlchemy model reflection | Uses existing models as source of truth; no need to maintain a separate table registry |
| Column display names | Chinese aliases from model `comment` attributes | Consistent with the existing import pipeline which already uses column comments for Chinese header validation |
| Datetime filter UX | Dropdown to pick column, then date range inputs | Gives user explicit control over which time dimension to filter; avoids ambiguity when multiple datetime columns exist |
| Column value filter UX | Dropdown to pick column, match mode toggle (包含/精确), value input; supports multiple simultaneous filters | Reuses the familiar column+value pattern from the datetime filter; multiple filters allow narrowing down on combinations like "status=已完成 AND operator contains 张" |
| Column value filter backend | `contains` → SQL `LIKE %value%`; `exact` → SQL `=` | Users choose the match semantics per filter; both are simple to implement on any column type |
| Sort UX | Click column header to cycle: none → ascending (▲) → descending (▼) → none. Arrow indicator shows current state | Standard spreadsheet-like UX; 3-state toggle avoids modal dialogs |
| Sort backend | Single `sort_col` + `sort_dir` parameter; sorts by one column at a time | Multi-column sort adds complexity with little UX benefit for this use case |
| Filter + sort interaction | Filters and sort compose — filter first, then sort the filtered results | Both narrow and order the result set; composing them is the expected behavior |
| Internal column visibility | Hide `id`, `imported_at`, `content_hash` | These are infrastructure columns with no business meaning; hiding them reduces clutter |
| Pagination | Default 20 rows, max 200, page number input + Prev/Next | Standard pagination pattern familiar to users; 200-row cap prevents excessive payloads |
| Table whitelist | Hardcoded list of business table names | Simple, explicit, easy to audit; excludes internal/system tables by design |

## Constraints

- Backend: FastAPI + SQLAlchemy 2.0 async + Pydantic v2 (per tech-stack.md)
- Frontend: React + TypeScript + Vite + shadcn/ui + TanStack Query (per tech-stack.md)
- Data queries must use existing SQLAlchemy models for schema metadata; raw SQL is acceptable for dynamic data queries since table names are not known at compile time
- Chinese UI text only — all labels, buttons, placeholders, and messages must be in Chinese
- No new database tables or migrations needed — this phase is read-only on existing data

## Out of Scope

- Multi-column sort (single column sort only)
- Inline editing or row deletion
- CSV/Excel export of browsed data
- Saved filters or bookmarks
- Column visibility toggles
