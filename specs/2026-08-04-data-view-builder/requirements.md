# Phase 5 — Data View Builder: Requirements

## Scope

Deliver a Data View Builder where users first pick a single source table, optionally add joins to additional tables, pick and rename columns, add type-aware filters, and apply groupings with aggregations. The backend stores both the JSON config and the generated parameterized SQL. A live preview with tabbed interface (data preview + SQL) lets users verify their view before saving.

**Included:**
- Backend: `View` model with JSON config and generated SQL, Alembic migration
- Backend: SQL generation engine that compiles JSON config into parameterized SQL with joins, filters, groupings, and aggregations
- Backend: `POST /api/views` and `PUT /api/views/{id}` endpoints with config→SQL generation on save
- Backend: `POST /api/views/preview` endpoint for live preview without saving
- Frontend: View builder page with split layout (config panel + tabbed preview panel)
- Frontend: Single source table selector, then dedicated "添加关联表" join section (INNER/LEFT/RIGHT)
- Frontend: Column picker with editable aliases (user can rename output columns)
- Frontend: Type-aware filter builder — operators and value inputs adapt to column type (text/number/date/datetime)
- Frontend: Grouping & aggregation builder (SUM/COUNT/AVG/MIN/MAX) with editable aliases
- Frontend: Computed columns builder — arithmetic (+, -, *, /) between numeric columns/constants and datetime shifts (days/months/years) with mandatory output alias
- Frontend: Live preview (up to 20 rows) with tabbed interface: 数据预览 | SQL语句
- Frontend: Save (新建/更新) with client-side validation

**Explicitly excluded:**
- Listing, browsing, or managing saved views (Phase 6)
- Executing saved views to return data (Phase 6)
- Deleting views (Phase 6)
- Sidebar navigation item for views (Phase 6)
- Charting or visualization (Phase 7)
- ORDER BY clause in SQL generation (sorting is a display concern, handled in Phase 6)
- HAVING clause (aggregation filtering not in scope)
- DISTINCT or subqueries
- Export of view SQL or results

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. The Data View Builder empowers operations and finance teams to create reusable query definitions across multiple tables — joining refund orders with service work orders, grouping by operator, and aggregating amounts — all through a visual interface. Instead of writing SQL or asking a developer, business users configure views themselves and immediately preview the results. These views become the foundation for visualizations (Phase 7) and dashboards (Phase 9–10).

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| SQL generation | Server-side, on save | Backend is the single source of truth. Config is always the canonical representation; SQL is always regenerated from config. Prevents drift between what the user configured and what the database executes. |
| Config storage | JSONB column in PostgreSQL | Flexible schema for evolving config structures without migrations. PostgreSQL JSONB supports indexing and querying if needed later. |
| Parameterized SQL | Named placeholders (`:param_name`) | Prevents SQL injection. Values are never interpolated into the SQL string. The generated SQL is safe to review and execute. |
| SQL validation | `EXPLAIN` on generation | Catches syntax errors, missing tables/columns, and type mismatches at save time rather than at execution time. Fast and safe — EXPLAIN does not execute the query. |
| Join flexibility | No hard cap on table count | User requested flexible number of tables. The builder validates that all join references are valid; PostgreSQL's own limits apply naturally. |
| Filter operators | 11 operators covering comparison, text matching, and null checks | Covers all common WHERE clause patterns. 包含/开头是/结尾是 use SQL LIKE; null operators handle the NULL = NULL problem correctly. |
| Grouping & aggregation interaction | GROUP BY columns must be selected in the column picker; non-aggregated, non-grouped columns are dropped from SELECT | Standard SQL semantics. Prevents confusing results where MySQL would silently pick arbitrary values. |
| Preview endpoint | Separate `POST /api/views/preview`, does not store anything | Separation of concerns: preview is transient exploration, save is persistent. Avoids creating orphaned views during experimentation. |
| Default column selection | `SELECT *` if no columns explicitly picked | Simplifies initial exploration. Users can then refine by picking specific columns. |
| Table selection flow | Single source table first, then add joins via "添加关联表" | Reduces initial cognitive load. Most views start from one primary table; joins are an explicit opt-in step. Matches tools like Metabase and Tableau. |
| Type-aware filtering | Operators and value inputs adapt to column type (text/number/date/datetime) | Prevents invalid filter combinations (e.g., "包含" on a number). Date columns show date pickers; numeric columns show number inputs. Improves data entry accuracy. |
| Column renaming | Editable alias inputs on selected columns and aggregation outputs | Users control output column names for readability. Aliases flow into the generated SQL `AS` clause and appear in the preview table headers. |
| Preview row limit | 20 rows | Sufficient to verify join logic and aggregation results. Keeps the preview panel compact and fast. |
| Preview SQL display | Tabbed interface: 数据预览 (default) | SQL语句 | Saves vertical space compared to inline display. Users switch tabs to inspect the generated SQL when needed.
| Computed columns | Simple binary expressions: arithmetic on numeric columns/constants via `::NUMERIC` casts, datetime shifts via PostgreSQL `INTERVAL`. Aliases are mandatory — computed columns appear as selectable options in filters, GROUP BY, and aggregations. | Covers the most common derived-column use cases (e.g. `total = amount + tax`, `due_date = created_at + 30 days`) without introducing a full expression language. Mandatory aliases ensure predictable output column names. |

## Constraints

- Backend: FastAPI + SQLAlchemy 2.0 async + Pydantic v2 (per tech-stack.md)
- Frontend: React + TypeScript + Vite + shadcn/ui + TanStack Query (per tech-stack.md)
- SQL generation must use parameterized queries — no string interpolation of user values
- All UI text in Chinese — labels, buttons, error messages, operator names, function names
- Table and column discovery uses existing `GET /api/tables` and `GET /api/tables/{name}/schema` endpoints from Phase 4.5
- Internal columns (`id`, `imported_at`, `content_hash`) must not appear in the column picker
- The generated SQL must be valid PostgreSQL 16+ syntax
- No charting library usage in this phase — that is Phase 7

## Out of Scope

- View listing, browsing, deletion (Phase 6)
- Executing saved views to return paginated data (Phase 6)
- Sidebar navigation for views (Phase 6)
- Visualization building (Phase 7)
- ORDER BY in generated SQL
- HAVING clause support
- DISTINCT, subqueries, UNION, CTEs
- View versioning or change history
- View sharing or permissions
- Export to CSV/Excel from preview
