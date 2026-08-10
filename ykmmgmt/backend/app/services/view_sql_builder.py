"""Parameterized SQL generation from ViewConfig JSON.

Produces safe, parameterized SELECT statements with joins, filters,
grouping, and aggregation. Values are never interpolated — all user
input is passed via named placeholders (:param_N).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import inspect as sa_inspect
from sqlalchemy.orm import DeclarativeBase

from app.schemas.view import (
    AggregationSpec,
    ComputedColumnSpec,
    ComputedOperand,
    FilterSpec,
    ViewConfig,
)

# ── Operator mapping ────────────────────────────────────────────────────────

_OPERATOR_SQL: dict[str, str] = {
    "eq": "=",
    "neq": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "contains": "LIKE",
    "startswith": "LIKE",
    "endswith": "LIKE",
}

_AGG_FUNCTIONS: set[str] = {"SUM", "COUNT", "AVG", "MIN", "MAX"}

# Regex to check for valid SQL identifiers
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
# Regex to strip auto-generated suffix from aliased table names (e.g. refund_orders_1 → refund_orders)
_ALIAS_SUFFIX_RE = re.compile(r"_\d+$")


def _quote_ident(name: str) -> str:
    """Double-quote a SQL identifier if needed, otherwise return as-is."""
    if _IDENTIFIER_RE.match(name):
        return name
    return f'"{name}"'


def _base_table_name(alias: str) -> str:
    """Strip auto-generated numeric suffix to get the base table name.

    >>> _base_table_name("refund_orders_1")
    "refund_orders"
    >>> _base_table_name("refund_orders")
    "refund_orders"
    """
    return _ALIAS_SUFFIX_RE.sub("", alias)


# ── Builder ─────────────────────────────────────────────────────────────────


class SQLBuildError(ValueError):
    """Raised when the config cannot produce valid SQL."""


class ViewSQLBuilder:
    """Compiles a ViewConfig into parameterized SQL.

    Usage::

        builder = ViewSQLBuilder(config, model_registry)
        sql, params = builder.build()
    """

    def __init__(
        self,
        config: ViewConfig,
        model_registry: dict[str, type[DeclarativeBase]],
    ) -> None:
        self._config = config
        self._registry = model_registry
        self._param_counter = 0
        self._params: dict[str, Any] = {}

        # Build a lookup: {logical_name: {column_name: column_info}}
        # Logical names may include aliases (e.g. refund_orders_1);
        # schema lookup uses the base name (strips _N suffix).
        self._table_columns: dict[str, dict[str, Any]] = {}
        self._all_tables: set[str] = set()

        for t in config.from_tables:
            self._all_tables.add(t)
        for j in config.joins:
            self._all_tables.add(j.left_table)
            alias = j.right_alias or j.right_table
            self._all_tables.add(alias)

        seen_bases: set[str] = set()
        for logical_name in self._all_tables:
            base = _base_table_name(logical_name)
            if base in seen_bases:
                continue
            seen_bases.add(base)
            model = self._registry.get(base)
            if model is None:
                raise SQLBuildError(f"数据表 '{base}' 不存在")
            mapper = sa_inspect(model)
            cols = {c.name: c for c in mapper.columns}
            # Map both the base name and any aliases to the same columns
            self._table_columns[logical_name] = cols
            for other in self._all_tables:
                if _base_table_name(other) == base:
                    self._table_columns[other] = cols

        # Build computed column expression map: {alias: full_sql_expression}
        self._computed_exprs: dict[str, str] = {}
        for cc in self._config.computed_columns:
            self._computed_exprs[cc.alias] = self._build_computed_expr(cc)

    # ── Public API ───────────────────────────────────────────────────────

    def build(self, *, apply_limit: bool = True) -> tuple[str, dict[str, Any]]:
        """Build the complete parameterized SQL.

        Args:
            apply_limit: If True, include ORDER BY. LIMIT is never included
                         (applied at runtime by endpoints).

        Returns:
            (sql_string, params_dict)
        """
        self._param_counter = 0
        self._params = {}

        select_clause = self._build_select()
        from_clause = self._build_from()
        join_clause = self._build_joins()
        where_clause = self._build_where()
        group_clause = self._build_group_by()
        order_clause = self._build_order_by() if apply_limit else ""

        parts = [select_clause, from_clause]
        if join_clause:
            parts.append(join_clause)
        if where_clause:
            parts.append(where_clause)
        if group_clause:
            parts.append(group_clause)
        if order_clause:
            parts.append(order_clause)

        sql = "\n".join(parts)
        return sql, dict(self._params)

    # ── SELECT ──────────────────────────────────────────────────────────

    def _build_select(self) -> str:
        """Build SELECT clause from columns + aggregations + computed columns.

        If no columns, no aggregations, and no computed columns, use SELECT *.
        """
        select_parts: list[str] = []
        # Track which qualified names are already in SELECT to avoid duplicates
        seen_select: set[str] = set()

        # Group BY columns (if any) — skip computed columns (handled below)
        if self._config.group_by:
            for col_name in self._config.group_by:
                if col_name in self._computed_exprs:
                    continue  # handled by computed columns section below
                qualified = self._resolve_column(col_name)
                select_parts.append(qualified)
                seen_select.add(qualified)

        # Regular columns (dedup against GROUP BY)
        if self._config.columns:
            for col_spec in self._config.columns:
                qualified = self._resolve_column(col_spec.column, col_spec.table)
                alias = col_spec.alias
                key = alias or qualified
                if key in seen_select:
                    continue
                seen_select.add(key)
                if alias:
                    select_parts.append(f"{qualified} AS {_quote_ident(alias)}")
                else:
                    select_parts.append(qualified)

        # Computed columns: only those explicitly selected OR in GROUP BY
        cc_to_select: set[str] = set(self._config.selected_computed_columns)
        # GROUP BY computed columns must also be in SELECT for alias reference
        for col_name in self._config.group_by:
            if col_name in self._computed_exprs:
                cc_to_select.add(col_name)
        for alias in cc_to_select:
            if alias in self._computed_exprs:
                key = alias
                if key in seen_select:
                    continue
                seen_select.add(key)
                select_parts.append(
                    f"{self._computed_exprs[alias]} AS {_quote_ident(alias)}"
                )

        # Aggregations
        if self._config.aggregations:
            for agg in self._config.aggregations:
                agg_expr = self._build_aggregation_expr(agg)
                select_parts.append(agg_expr)

        if not select_parts:
            return "SELECT *"

        return "SELECT " + ", ".join(select_parts)

    def _build_aggregation_expr(self, agg: AggregationSpec) -> str:
        func_upper = agg.function.upper()
        if func_upper not in _AGG_FUNCTIONS:
            raise SQLBuildError(f"不支持的聚合函数: '{agg.function}'")

        if func_upper == "COUNT" and agg.column == "*":
            expr = "COUNT(*)"
        else:
            # Check if the aggregation column is a computed column alias
            if agg.column in self._computed_exprs:
                qualified = self._computed_exprs[agg.column]
            else:
                qualified = self._resolve_column(agg.column)
            expr = f"{func_upper}({qualified})"

        if agg.alias:
            expr += f" AS {_quote_ident(agg.alias)}"
        return expr

    # ── FROM ────────────────────────────────────────────────────────────

    def _build_from(self) -> str:
        """Build FROM clause using the first table (no alias needed for primary)."""
        primary = self._config.from_tables[0]
        base = _base_table_name(primary)
        if primary != base:
            # Aliased primary table (shouldn't normally happen, but handle it)
            return f"FROM {_quote_ident(base)} AS {_quote_ident(primary)}"
        return f"FROM {_quote_ident(primary)}"

    # ── JOIN ────────────────────────────────────────────────────────────

    def _build_joins(self) -> str:
        """Build JOIN clauses in listed order."""
        if not self._config.joins:
            return ""

        clauses: list[str] = []
        for join in self._config.joins:
            jt = join.join_type.upper()
            if jt not in ("INNER", "LEFT", "RIGHT"):
                raise SQLBuildError(f"不支持的连接类型: '{join.join_type}'")
            if jt == "INNER":
                jt = "INNER JOIN"
            elif jt == "LEFT":
                jt = "LEFT JOIN"
            else:
                jt = "RIGHT JOIN"

            left_col = self._resolve_column(join.left_key, join.left_table)
            right_table_alias = join.right_alias or join.right_table
            right_col = self._resolve_column(join.right_key, right_table_alias)
            base_right = _base_table_name(join.right_table)
            if join.right_alias:
                clause = (
                    f"{jt} {_quote_ident(base_right)} AS {_quote_ident(join.right_alias)} "
                    f"ON {left_col} = {right_col}"
                )
            else:
                clause = (
                    f"{jt} {_quote_ident(join.right_table)} "
                    f"ON {left_col} = {right_col}"
                )
            clauses.append(clause)

        return "\n".join(clauses)

    # ── WHERE ───────────────────────────────────────────────────────────

    def _build_where(self) -> str:
        """Build WHERE clause with parameterized filters."""
        if not self._config.filters:
            return ""

        conditions: list[str] = []
        for f in self._config.filters:
            cond = self._build_filter_condition(f)
            conditions.append(cond)

        if not conditions:
            return ""

        return "WHERE " + " AND ".join(conditions)

    def _build_filter_condition(self, f: FilterSpec) -> str:
        """Build a single parameterized filter condition."""
        # Check if the filter column references a computed column alias
        col: str
        if f.column in self._computed_exprs:
            col = self._computed_exprs[f.column]
        else:
            col = self._resolve_column(f.column)

        # Date range filter: takes precedence over operator-based filtering
        if f.date_start or f.date_end:
            # Import here to avoid top-level import overhead
            from datetime import date as dt_date
            from datetime import timedelta
            conditions: list[str] = []
            if f.date_start:
                p = self._next_param()
                try:
                    self._params[p] = dt_date.fromisoformat(f.date_start)
                except (ValueError, TypeError) as err:
                    raise SQLBuildError(f"无效的日期格式: '{f.date_start}'") from err
                conditions.append(f"{col}::DATE >= :{p}")
            if f.date_end:
                try:
                    end_date = dt_date.fromisoformat(f.date_end) + timedelta(days=1)
                except (ValueError, TypeError) as err:
                    raise SQLBuildError(f"无效的日期格式: '{f.date_end}'") from err
                p = self._next_param()
                self._params[p] = end_date
                conditions.append(f"{col} < :{p}")
            return "(" + " AND ".join(conditions) + ")"

        # Operator-based filter (original logic)
        op = f.operator

        # Null checks
        if op == "is_null":
            return f"{col} IS NULL"
        if op == "is_not_null":
            return f"{col} IS NOT NULL"

        sql_op = _OPERATOR_SQL.get(op)
        if sql_op is None:
            raise SQLBuildError(f"不支持的操作符: '{op}'")

        param_name = self._next_param()

        if op == "contains":
            self._params[param_name] = f"%{f.value}%"
        elif op == "startswith":
            self._params[param_name] = f"{f.value}%"
        elif op == "endswith":
            self._params[param_name] = f"%{f.value}"
        else:
            self._params[param_name] = f.value

        return f"{col} {sql_op} :{param_name}"

    # ── GROUP BY ────────────────────────────────────────────────────────

    def _build_group_by(self) -> str:
        """Build GROUP BY clause."""
        if not self._config.group_by:
            return ""

        cols: list[str] = []
        for col_name in self._config.group_by:
            # Computed column alias — PostgreSQL allows aliases in GROUP BY
            if col_name in self._computed_exprs:
                cols.append(_quote_ident(col_name))
            else:
                qualified = self._resolve_column(col_name)
                cols.append(qualified)

        return "GROUP BY " + ", ".join(cols)

    # ── Computed columns ────────────────────────────────────────────────

    def _build_computed_expr(self, cc: ComputedColumnSpec) -> str:
        """Build the SQL expression (without alias) for a computed column."""
        if cc.expression_type == "arithmetic":
            return self._build_arithmetic_expr(cc)
        if cc.expression_type == "datetime_shift":
            return self._build_datetime_shift_expr(cc)
        if cc.expression_type == "datetime_trunc":
            return self._build_datetime_trunc_expr(cc)
        raise SQLBuildError(f"不支持的计算列类型: '{cc.expression_type}'")

    def _build_arithmetic_expr(self, cc: ComputedColumnSpec) -> str:
        """Build a chained numeric arithmetic expression with COALESCE for +/-."""
        if len(cc.operands) < 2:
            raise SQLBuildError(f"计算列 '{cc.alias}' 至少需要两个操作数")
        if len(cc.operators) != len(cc.operands) - 1:
            raise SQLBuildError(f"计算列 '{cc.alias}' 操作符数量不匹配")

        # Resolve all operands to SQL
        resolved = [self._resolve_computed_operand(op) for op in cc.operands]

        # Build expression with COALESCE for +/- and left-to-right parentheses
        # Wrap each operand in COALESCE(x, 0) if adjacent to + or -
        parts: list[str] = []
        for i in range(len(resolved)):
            expr = f"{resolved[i]}::NUMERIC"
            # Check if this operand is adjacent to a + or - operator
            needs_coalesce = False
            if i > 0 and cc.operators[i - 1] in ("+", "-"):
                needs_coalesce = True
            if i < len(cc.operators) and cc.operators[i] in ("+", "-"):
                needs_coalesce = True
            if needs_coalesce:
                expr = f"COALESCE({expr}, 0)"
            parts.append(expr)

        # Build left-to-right parenthesized expression
        result = parts[0]
        for i, op in enumerate(cc.operators):
            result = f"({result} {op} {parts[i + 1]})"

        return result

    def _build_datetime_shift_expr(self, cc: ComputedColumnSpec) -> str:
        """Build a datetime shift expression using PostgreSQL INTERVAL."""
        if not cc.base_column or cc.shift_value is None or not cc.shift_unit:
            raise SQLBuildError(f"计算列 '{cc.alias}' 缺少日期偏移参数")
        base = self._resolve_computed_operand(cc.base_column)
        # Use PostgreSQL INTERVAL syntax: base + INTERVAL 'N unit'
        # Normalize unit name (years→year, months→month, days→day) for valid INTERVAL
        unit_map = {"days": "day", "months": "month", "years": "year"}
        pg_unit = unit_map.get(cc.shift_unit, cc.shift_unit)
        # Parse shift_value; support negative values for subtraction
        try:
            val = float(cc.shift_value)
        except ValueError as err:
            raise SQLBuildError(f"计算列 '{cc.alias}' 的偏移值 '{cc.shift_value}' 不是有效数字") from err
        abs_val = abs(int(val)) if val == int(val) else abs(val)
        if val < 0:
            return f"({base} - INTERVAL '{abs_val} {pg_unit}')"
        display_val = int(val) if val == int(val) else val
        return f"({base} + INTERVAL '{display_val} {pg_unit}')"

    def _resolve_computed_operand(self, operand: ComputedOperand) -> str:
        """Resolve a ComputedOperand to its SQL representation."""
        if operand.type == "column":
            if not operand.column:
                raise SQLBuildError("计算列操作数缺少列名")
            if operand.table:
                return self._resolve_column(operand.column, operand.table)
            return self._resolve_column(operand.column)
        if operand.type == "constant":
            if operand.value is None:
                raise SQLBuildError("计算列常量操作数缺少值")
            # Return the value as-is; it will be cast via ::NUMERIC in arithmetic
            return operand.value
        raise SQLBuildError(f"不支持的计算列操作数类型: '{operand.type}'")

    def _build_datetime_trunc_expr(self, cc: ComputedColumnSpec) -> str:
        """Build a datetime truncation expression using PostgreSQL DATE_TRUNC."""
        if not cc.trunc_column:
            raise SQLBuildError(f"计算列 '{cc.alias}' 缺少截断列参数")
        if not cc.trunc_unit:
            raise SQLBuildError(f"计算列 '{cc.alias}' 缺少截断单位")
        base = self._resolve_computed_operand(cc.trunc_column)
        return f"DATE_TRUNC('{cc.trunc_unit}', {base})"

    def _build_order_by(self) -> str:
        """Build ORDER BY clause."""
        if not self._config.order_by:
            return ""
        # Collect aggregation aliases for ORDER BY reference
        agg_aliases: set[str] = {
            a.alias for a in self._config.aggregations if a.alias
        }
        cols: list[str] = []
        for o in self._config.order_by:
            if o.column in self._computed_exprs or o.column in agg_aliases:
                col = _quote_ident(o.column)
            else:
                col = self._resolve_column(o.column)
            direction = "DESC" if o.direction == "desc" else "ASC"
            cols.append(f"{col} {direction}")
        return "ORDER BY " + ", ".join(cols)

    def _build_limit(self) -> str:
        """Build LIMIT clause."""
        if self._config.limit and self._config.limit > 0:
            return f"LIMIT {self._config.limit}"
        return ""

    # ── Helpers ─────────────────────────────────────────────────────────

    def _next_param(self) -> str:
        """Generate the next parameter placeholder name."""
        self._param_counter += 1
        return f"param_{self._param_counter}"

    def _resolve_column(self, column: str, table: str | None = None) -> str:
        """Resolve a column reference to a fully qualified identifier.

        If ``column`` contains a dot, it is treated as ``table.column``.
        Otherwise ``table`` is used if provided; if not, we search all
        known tables.
        """
        if "." in column:
            parts = column.split(".", 1)
            tbl, col = parts[0], parts[1]
            self._validate_column(tbl, col)
            return f"{_quote_ident(tbl)}.{_quote_ident(col)}"

        if table:
            self._validate_column(table, column)
            return f"{_quote_ident(table)}.{_quote_ident(column)}"

        # Search all tables for the column
        found: list[str] = []
        for tbl, cols in self._table_columns.items():
            if column in cols:
                found.append(tbl)

        if not found:
            raise SQLBuildError(f"列 '{column}' 在任何表中都不存在")
        if len(found) > 1:
            raise SQLBuildError(
                f"列 '{column}' 在多个表中存在 ({', '.join(found)})，"
                f"请使用 '表名.列名' 格式指定"
            )

        tbl = found[0]
        return f"{_quote_ident(tbl)}.{_quote_ident(column)}"

    def _validate_column(self, table: str, column: str) -> None:
        """Validate that a column exists in a table."""
        cols = self._table_columns.get(table)
        if cols is None:
            raise SQLBuildError(f"数据表 '{table}' 不存在")
        if column not in cols:
            available = ", ".join(list(cols.keys())[:10])
            raise SQLBuildError(
                f"列 '{column}' 在表 '{table}' 中不存在。"
                f"可用列: {available}"
            )
