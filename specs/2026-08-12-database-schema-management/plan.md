# Phase 10 — Database Schema Management: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Schema inspection backend

1. Add a schema inspection service (`app/services/schema_manager.py`) that uses SQLAlchemy `inspect()` against the live async engine to enumerate all user tables and, per table, column name, SQL type, nullable, primary-key, unique, server default, and the column comment (Chinese label).
2. Expose `GET /api/schema/tables` — return every table with its English name, Chinese display name (falling back to the English name when absent from `TABLE_DISPLAY_NAMES`), column count, and row count.
3. Expose `GET /api/schema/tables/{name}` — return full column detail (name, type, nullable, unique, primary key, comment/Chinese label) plus a small sample of rows for preview.
4. Mark the three pre-existing business tables (`refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`) as `read_only: true` in the inspection response so the frontend can gate edit/delete actions.

## Group 2 — Column type system & dynamic registry

5. Define the supported column-type system in the schema manager: `String(N)`, `Text`, `Integer`, `BigInteger`, `Numeric(12,2)`, `Boolean`, `DateTime`, `Date`, `JSON` — the six roadmap types plus commonly used additions (`BigInteger`, `Date`, `JSON`). Provide a single mapping table between the frontend picker key, the SQLAlchemy type, and the generated DDL.
6. Expose `GET /api/schema/column-types` — return the allowed type list (key, label, whether it takes a length/precision) so the frontend picker is driven by the backend.
7. Extend `schema_validator` with a runtime registration path: after a new table is created, call `register_model()` and add the English→Chinese entry to `TABLE_DISPLAY_NAMES` (and rebuild `CHINESE_TO_ENGLISH_TABLE`) so the new table appears in Data Browser / View Builder without a server restart.
8. Build a dynamic model factory that constructs a SQLAlchemy model class at runtime from a column-definition payload (name, type, nullable, unique, comment) using `type()` + `Table`/`Column` metadata, registered under a unique generated class name.

## Group 3 — Table creation backend (manual + CSV inference)

9. Expose `POST /api/schema/tables` — accept table name (English, validated as a safe identifier), Chinese display name, and a list of column definitions; validate identifier safety and reserved names; create the table via the dynamic model + generated DDL.
10. Generate an Alembic migration for the new table programmatically (write a migration file into `alembic/versions/` and run `upgrade head`) so the change is captured in migration history.
11. On successful creation, invoke the Group 2 runtime registration so the table is immediately usable.
12. Expose `POST /api/schema/infer-from-csv` — accept an uploaded CSV, run Pandas-based header + type inference, suggest Chinese labels from the headers, and return a proposed schema (columns with inferred type + suggested label) for user review before creation. Does NOT create the table.
13. Validate that a proposed table name does not collide with an existing table or a reserved/system name; return 409 on conflict.

## Group 4 — Table edit & delete backend

14. Expose `POST /api/schema/tables/{name}/columns` — add a column (name, type, nullable, Chinese label); generate + run an Alembic `add_column` migration; refresh the runtime registry.
15. Expose `DELETE /api/schema/tables/{name}/columns/{col}` — drop a column; generate + run a migration; refresh the registry.
16. Expose `PUT /api/schema/tables/{name}/columns/{col}` — modify column type; generate + run an `alter_column` migration; return a warning when the cast may lose data.
17. Expose `DELETE /api/schema/tables/{name}` — drop the table; generate + run a migration; remove it from the runtime registry and `TABLE_DISPLAY_NAMES`.
18. Enforce the read-only guard: reject edit/delete operations on the three pre-existing business tables with a 403 and a clear message.
19. Before dropping a table or column, scan saved views (`views.generated_sql` / `config_json`) and visualizations for references and return a dependency list so the frontend can warn the user.

## Group 5 — Frontend: Schema Manager navigation & table list

20. Add a "Schema Manager" (数据库管理) nav item in the sidebar under a database/admin section.
21. Build the table list page — all tables with Chinese name, English name, column count, row count; per-row actions: 查看 (inspect), 编辑, 删除 (edit/delete hidden or disabled for read-only tables).
22. Add TanStack Query hooks for the schema endpoints (`useSchemaTables`, `useSchemaTableDetail`, `useColumnTypes`, mutations for create/edit/delete).

## Group 6 — Frontend: table detail & create wizard

23. Build the table detail/inspect page — full column listing (name, type, nullable, unique, Chinese label) and a paginated sample-data preview.
24. Build the create-table wizard with two paths:
    - (a) Manual: add columns one-by-one, each with a name, a type picker (driven by `GET /api/schema/column-types`), a Chinese label input, nullable/unique toggles.
    - (b) CSV import: upload a CSV, show the inferred schema from `POST /api/schema/infer-from-csv`, allow adjusting types/labels, then confirm creation.
25. Wire the wizard's confirm to `POST /api/schema/tables`; on success invalidate the tables query and navigate to the new table's detail page.

## Group 7 — Frontend: edit & delete

26. Build the edit-table dialog — add a new column, remove a column, change a column's type (show a data-loss warning for incompatible casts), all gated to non-read-only tables.
27. Build the delete-table confirmation — type-to-confirm pattern; surface the dependency warning (views/visualizations referencing the table) returned by the backend.
28. Ensure all UI text is in Chinese per project convention.

## Group 8 — Tests & validation

29. Backend tests: schema inspection, column-type listing, manual create, CSV inference, add/drop/modify column, delete table, read-only guard on business tables, runtime registry visibility (new table appears in `get_registered_tables()`).
30. Backend test fixtures: create a real sample CSV file on disk (via pytest `tmp_path`) containing Chinese headers and mixed-type columns (text, integer, decimal, date) and use it to exercise the full flow end-to-end — `POST /api/schema/infer-from-csv` returns the inferred schema, then `POST /api/schema/tables` with that schema creates the table, and the new table is queryable. Add a second sample CSV with edge cases (blank rows, whitespace in headers, a column of all-null values) to verify inference robustness.
31. Frontend tests (Vitest + RTL): table list renders, create wizard manual path, create wizard CSV path (upload a real `File` built from CSV text and assert the inferred schema is rendered), edit dialog, delete confirmation with dependency warning.
32. Full-lifecycle integration test — a single pytest module that walks a brand-new table through its entire real-world lifecycle using actual sample CSV files, asserting cross-feature integration at every step:
    1. **Create** — write `lifecycle_v1.csv` (Chinese headers, mixed types) to `tmp_path`; call `POST /api/schema/infer-from-csv` then `POST /api/schema/tables`; assert the table exists and a migration was generated.
    2. **Upload data** — import `lifecycle_v1.csv` into the new table via the existing import engine (`POST /api/imports`); assert rows land and the cleaning report is returned.
    3. **Integrate** — assert the new table appears in `GET /api/tables` (Data Browser) and its schema is served by `GET /api/tables/{name}/schema`; build a data view on it via `POST /api/views` and execute `GET /api/views/{id}/data`; build a visualization on that view via `POST /api/visualizations`.
    4. **Edit schema** — add a column and modify a column type via the schema endpoints; assert new migrations were generated and the runtime registry reflects the change.
    5. **Upload edited-schema data** — write `lifecycle_v2.csv` matching the edited schema (with the new column) and import it; assert the new column is populated.
    6. **Features respond to change** — assert Data Browser schema now shows the new column, the view still executes (or reports the changed column), and the visualization data endpoint reflects the updated shape.
    7. **Delete** — `DELETE /api/schema/tables/{name}`; assert the table is gone from the registry and `GET /api/tables`, the dependent view/visualization are flagged, and a drop migration was generated.
33. Run the full validation gates in `validation.md`.

---

# Extended Scope (added during implementation)

Groups 9–12 were requested after the original plan and delivered within the same phase.

## Group 9 — Upload robustness & matching rule

34. Strip multiple leading UTF-8 BOMs in the CSV parser (double-BOM files glued `\ufeff` to the first header and broke matching for required-PK tables); strip stray BOMs per header defensively.
35. Header matching: Chinese label (column comment) first, real column name as fallback. Enforce a strict validation gate — every file header must map to a table column AND every required (NOT NULL, no default) column must be covered; otherwise reject the whole upload with 422 listing missing/unexpected columns.
36. Relocate runtime-generated migrations from `alembic/versions/` to `runtime_migrations/` (outside the `uvicorn --reload` watch tree; wired via `version_locations`) so schema changes never kill in-flight requests. (Supersedes item 10's file location.)

## Group 10 — Renaming, FK-to-unique, column metadata & caveat tooltips

37. `PUT /api/schema/tables/{name}` — rename the English table name (physical `ALTER TABLE ... RENAME`, blocked with 409 + dependency list when views/visualizations reference it) and/or the Chinese display name (table comment); resync registry + meta stores.
38. Allow foreign keys to target another table's **unique** column, not just its PK; expose a `unique` flag in `fk-options` and mark picker entries as …・主键 / …・唯一.
39. Column description + default value support: persisted in `column_meta`, rendered as server defaults, applied on upload when a column is omitted; comprehensive per-column editing (rename, label, type, nullable, unique, description, default, FK) compiled into a single migration with correct op ordering.
40. Frontend: rename section in the edit dialog; a reusable opaque `InfoTooltip` component carrying two caveats — table names bind table-specific cleansing rules (rename with care; display name is free to change), and Chinese labels drive upload column matching (changing them can break uploads).

## Group 11 — Ingestion settings (upsert key + dedup toggle)

41. New `table_meta` table storing per-table `upsert_key` (comma-joined, optional — defaults to the user PK; composite allowed) and `dedup_enabled`; mirrored by an in-memory settings registry + model attributes, restored on restart.
42. DDL support: `uq_{table}_key` unique constraint for explicit keys (skipped when equal to the PK); `content_hash` + unique constraint for keyless dedup-on tables; pure insert for keyless dedup-off tables.
43. Validation rule enforced in UI and backend: dedup may only be disabled when the table has no PK, no unique column, and no upsert key (toggle locked otherwise). Settings editable at creation and via `PUT /api/schema/tables/{name}`; the new key must not collide with existing data (checked on a separate connection to avoid a DDL lock deadlock).
44. Sensible defaults for the three preset business tables (explicit `__upsert_key__ = []` → unchanged legacy insert-only hash-dedup behavior).

## Group 12 — Import counter semantics

45. Implement the authoritative four counters: 新增 (valid, no match, added), 更新 (matched, ≥1 value changed), 跳过 (matched, identical — includes duplicate collapses), 拒绝 (invalid/unwritable). Counters increment only after a successful write; failed rows (e.g. FK violation) count as 拒绝 only.
46. Keyed tables (explicit upsert key or PK fallback) get full fetch-compare-write upsert (`ON CONFLICT DO UPDATE`); partial uploads compare/write only file-present columns and never null omitted ones; temporal/Decimal comparisons normalized so identical re-uploads count as 跳过.
47. Dedicated mock-data tests per situation: insert/skip/update/partial-update/reject tuples, composite keys, keyless dedup on/off duplicate scenarios, DATE/NUMERIC re-upload regression, FK-violation double-count regression.
48. Re-run the full validation gates (backend 147 / frontend 63 tests, lint, format, lifecycle module).
