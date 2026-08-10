# Phase 5 — Data View Builder: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend: View Model & Migration

1. Create `View` SQLAlchemy model in `ykmmgmt/backend/app/models/view.py` with fields: `id` (UUID primary key), `name` (String, required), `description` (Text, nullable), `config_json` (JSONB — stores join specs, column selections, filters, groupings, aggregations), `generated_sql` (Text — the compiled parameterized SQL), `created_at` (DateTime, server default), `updated_at` (DateTime, onupdate).

2. Generate and apply an Alembic migration for the `views` table. Verify it appears in the database and is listed in `ykmmgmt/backend/alembic/versions/`.

3. Create Pydantic schemas for view CRUD in `ykmmgmt/backend/app/schemas/view.py`: `ViewConfig` (the JSON structure), `ViewCreate`, `ViewUpdate`, `ViewResponse` (includes `id`, `name`, `description`, `config_json`, `generated_sql`, `created_at`, `updated_at`), `ViewListResponse` (id, name, description, created_at, updated_at — summary only, no SQL/config). Include `ComputedOperand` (type: column|constant) and `ComputedColumnSpec` (alias, expression_type: arithmetic|datetime_shift, operands, operator, datetime shift fields). Add `computed_columns` field to `ViewConfig`.

---

## Group 2 — Backend: SQL Generation Engine

4. Create `ykmmgmt/backend/app/services/view_sql_builder.py` with a `ViewSQLBuilder` class that accepts a `ViewConfig` and the database table metadata (from SQLAlchemy inspector) and produces valid parameterized SQL.

5. Implement join SQL generation: accept a list of join specs `{left_table, right_table, join_type, left_key, right_key}`. Generate `INNER JOIN` / `LEFT JOIN` / `RIGHT JOIN` clauses. Join order must be determined by the builder, not the user — start from the first table in `from_tables`, then chain joins in the order they are listed. Flexible number of tables (no hard cap), but validate that every join references tables present in `from_tables`.

6. Implement column selection SQL: accept a list of `{table, column, alias}`. Generate `SELECT t1.col1 AS alias1, t2.col2 AS alias2, ...`. If no columns specified, default to `SELECT *` from all joined tables.

7. Implement filter (WHERE) SQL: accept a list of `{column, operator, value}`. Supported operators: `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `contains`, `startswith`, `endswith`, `is_null`, `is_not_null`. Combine all filters with `AND`. Use parameterized placeholders (`:param_name`) — never interpolate values directly.

8. Implement grouping & aggregation SQL: accept a list of `{column}` for GROUP BY and a list of `{function, column, alias}` for aggregations. Supported functions: `SUM`, `COUNT`, `AVG`, `MIN`, `MAX`. Generate `GROUP BY col1, col2` and aggregate expressions in SELECT.

9. Implement `ViewSQLBuilder.build()` that composes all clauses into a complete parameterized `SELECT ... FROM ... JOIN ... WHERE ... GROUP BY ...` statement. Return both the SQL string and the parameter dict. Validate the generated SQL by executing `EXPLAIN` on it — reject if PostgreSQL reports a syntax error.

### Group 2a — Backend: Computed Column SQL Generation

9a. Add `_build_computed_expr()` method: dispatches to `_build_arithmetic_expr()` or `_build_datetime_shift_expr()` based on `expression_type`.

9b. Arithmetic expressions: cast both operands to `::NUMERIC`, apply the operator (`+`, `-`, `*`, `/`), wrap in parentheses. Operands resolved via `_resolve_computed_operand()` (column → `table.col`, constant → raw value).

9c. Datetime shift expressions: use PostgreSQL `INTERVAL` syntax — `(base_column + INTERVAL 'N unit')` or subtraction for negative values. Unit normalization: days→day, months→month, years→year.

9d. Datetime truncation expressions: use PostgreSQL `DATE_TRUNC` — `DATE_TRUNC('unit', column)`. Supported units: year, quarter, month, week, day, hour, minute. Missing `trunc_column` or `trunc_unit` raises `SQLBuildError`.

9e. Computed columns in SELECT: appended as `expression AS alias` items in `_build_select()`. Computed columns in WHERE: resolved by alias lookup in `_build_filter_condition()` (embed the full expression, not the alias). Computed columns in GROUP BY and ORDER BY: referenced by alias (PostgreSQL allows this).

---

## Group 3 — Backend: View CRUD Endpoints

10. Create `ykmmgmt/backend/app/routers/views.py` with the following endpoints:

11. `POST /api/views` — accepts `ViewCreate` (name, description, config_json). Calls `ViewSQLBuilder` to generate SQL from config. Validates config against actual table schema (tables and columns must exist). Stores both config and generated SQL. Returns `ViewResponse`.

12. `PUT /api/views/{id}` — accepts `ViewUpdate` (partial update of name, description, config_json). If config_json is provided, regenerates SQL. If only name/description changed, leaves SQL unchanged. Returns updated `ViewResponse`. Returns 404 if view not found.

13. Register the views router in the FastAPI app (`ykmmgmt/backend/app/__init__.py` or main.py). Verify endpoints appear in OpenAPI docs at `/docs`.

---

## Group 4 — Frontend: View Builder Core UI

14. Create `ykmmgmt/frontend/src/pages/ViewBuilderPage.tsx` with the builder layout: a split view — configuration panel on the left, live preview panel on the right. Add route at `/views/builder` and `/views/builder/:id` (edit mode) in `App.tsx`.

15. Create TanStack Query hooks in `ykmmgmt/frontend/src/hooks/useViews.ts`: `useCreateView`, `useUpdateView`, hooks for schema fetching reuse existing `useTables` hook plus a new `useTableSchema(tableName)` hook (wraps `GET /api/tables/{name}/schema`).

---

## Group 5 — Frontend: Source Table & Join Builder

16. Implement source table selector: a single-select dropdown showing all business tables (Chinese names). User first picks one source table as the primary `FROM` table. After selection, the column picker and filter/aggregation sections become active for that table. A dedicated "添加关联表" section appears below, allowing the user to add joins to additional tables.

17. Implement join builder ("关联表" section): each added join row has: a table dropdown (remaining business tables not yet joined), join type selector (INNER/LEFT/RIGHT), source key column dropdown (columns of the source table), and target key column dropdown (columns of the added table). Users add join rows one at a time via "添加关联表" button. Display a visual diagram showing the source table box with joined tables branching from it. Validate that every join key column exists in the respective table schemas.

---

## Group 6 — Frontend: Column Picker & Filter Builder

18. Implement column picker: after the source table is selected, fetch its schema and display a checkbox list of its columns. Options are formatted as `表名.列名` using their Chinese aliases (e.g. `退费单.退费单号`, `服务退款工单.工单ID`). When joins are added, also show columns from joined tables in the same list with their respective table prefixes. Each selected column has an editable alias input (renaming the column in the output). Internal columns (id, imported_at, content_hash) are hidden from the list. If no columns are selected, defaults to `SELECT *`.

19. Implement type-aware filter builder: reuse the multi-row filter pattern from Data Browser but make the UI context-sensitive based on the selected column's type:
   - **Text columns:** operators 等于/不等于/包含/开头是/结尾是/为空/不为空, value input is a text field.
   - **Numeric columns:** operators 等于/不等于/大于/大于等于/小于/小于等于/为空/不为空, value input is a number field.
   - **Date/datetime columns:** **No operators** — replaced by a date range picker with start date and end date inputs. Both fields optional (one-sided ranges supported). Back end uses `date_start`/`date_end` fields with `>= :start` and `< :end::DATE + INTERVAL '1 day'` (inclusive end date).
   - "添加筛选条件" button adds rows. All filters AND together. Date range conditions combine with operator-based filters via AND.

---

### Group 7a — Frontend: Computed Columns Builder

20a. Add computed columns section UI as a Card between the column picker and filter sections. Expression type selector offers three options: 算术运算 (arithmetic), 日期偏移 (datetime_shift), and 日期截取 (datetime_trunc). Arithmetic: chained operands (column pickers filtered to numeric, or constant number inputs) with +/−/×/÷ operators between them. Datetime shift: base date column picker (filtered to date columns), offset amount, unit (天/月/年). Datetime trunc: base date column picker, granularity selector (年/季度/月/周/天/小时/分钟). Mandatory alias input on every expression. "添加计算列" button adds rows; X button removes.

20b. Add `ComputedColumnItem` type to `ViewBuilderContext` with flat UI fields: expression_type, operands/operators (arithmetic), base_table/base_column/shift_value/shift_unit (datetime_shift), trunc_table/trunc_column/trunc_unit (datetime_trunc), and mandatory alias. Add `computedColumns` state and `setComputedColumns` setter.

20c. Wire computed columns into `columnOptions` (as "计算: alias" entries) so they appear as selectable in filter, GROUP BY, and aggregation column pickers.

20d. Add `computed_columns` to `compileConfig`: map UI-flat `ComputedColumnItem` to API `ComputedColumnSpec` with nested `ComputedOperand` objects. Add to edit-mode loading (`existingView.config_json.computed_columns`).

20. Implement grouping & aggregation section: GROUP BY dropdown (multi-select of selected columns), aggregation rows — each with function dropdown (求和/计数/平均值/最小值/最大值), column dropdown, and editable alias input (user can rename the aggregated output column). "添加聚合" button adds rows. If GROUP BY is set, SELECT must include those columns; non-aggregated columns not in GROUP BY are excluded.

21. Implement save button: compiles all config (tables, joins, columns, filters, groupings, aggregations) into JSON. Calls `POST /api/views` (create) or `PUT /api/views/{id}` (update). Shows success/error toast. Validates that view has a name before saving. "保存" (save) and "保存并预览" (save and preview) buttons.

22. Add a name and description input at the top of the builder. Name is required (validated client-side before save).

---

### Group 7c — Frontend: ORDER BY & LIMIT

20e. Add "排序与限制" Card section between the aggregation section and save buttons. ORDER BY rows: each with a column picker (all columns + computed column aliases + aggregation aliases) and direction selector (升序/降序). "添加排序" button adds rows; X button removes. Multiple sort columns supported — order within the list determines SQL ordering.

20f. LIMIT input: numeric field accepting a positive integer row count. Empty/zero treated as no limit. Applied as `LIMIT n` in generated SQL.

20g. Backend: `_build_order_by()` resolves columns, computed column aliases, and aggregation aliases. `_build_limit()` emits `LIMIT n` for positive values. `build(apply_limit=True)` includes both; `build(apply_limit=False)` excludes them (used for total-count queries).

---

## Group 8 — Frontend: Live Preview

23. Create `POST /api/views/preview` endpoint in `ykmmgmt/backend/app/routers/views.py`. Accepts `ViewConfig` in request body. Generates SQL via `ViewSQLBuilder`, executes it with `LIMIT 20`, returns `{sql, rows, columns}`. Does NOT store anything.

24. Implement live preview panel: after the source table is selected and at least one column is picked, show a "预览" button. On click, calls `POST /api/views/preview` with current config. The preview panel uses a tabbed interface with two tabs:
   - **数据预览** (default): displays results in a table (up to 20 rows) with renamed/aliased column headers.
   - **SQL语句**: shows the generated parameterized SQL in a syntax-highlighted or monospaced code block for review.

25. Auto-refresh preview when config changes (debounced 500ms) after the first manual preview. Show a loading spinner during preview fetch.

---

## Group 9 — Integration & Polish

26. Add loading states, error boundaries, and empty states throughout the builder UI. Handle backend validation errors (invalid table/column names, SQL generation failures) with user-friendly Chinese error messages.

27. Wire the builder into edit flow: when navigating to `/views/builder/:id`, fetch the existing view config and pre-populate all builder sections. The save button calls PUT instead of POST.
