"""Tests for ViewSQLBuilder — datetime_trunc, date range filters, ORDER BY, LIMIT."""

import pytest

from app.schemas.view import (
    AggregationSpec,
    ColumnSpec,
    ComputedColumnSpec,
    ComputedOperand,
    FilterSpec,
    JoinSpec,
    OrderSpec,
    ViewConfig,
)
from app.services.view_sql_builder import SQLBuildError, ViewSQLBuilder


def _make_builder(config: ViewConfig, columns: dict[str, dict[str, object]]):
    """Create a ViewSQLBuilder with pre-populated _table_columns."""
    builder = ViewSQLBuilder.__new__(ViewSQLBuilder)
    builder._config = config
    builder._param_counter = 0
    builder._params = {}
    builder._table_columns = columns
    builder._all_tables = set(columns.keys())

    # Build computed column expressions
    builder._computed_exprs = {}
    for cc in config.computed_columns:
        builder._computed_exprs[cc.alias] = builder._build_computed_expr(cc)

    return builder


# ── Shared column fixtures ───────────────────────────────────────────────

REFUND_COLS = {
    "refund_orders": {
        "refund_order_no": object(),
        "refund_amount": object(),
        "status": object(),
        "created_at": object(),
    }
}

REFUND_SERVICE_COLS = {
    "refund_orders": {
        "refund_order_no": object(),
        "refund_amount": object(),
        "status": object(),
        "created_at": object(),
    },
    "service_refund_work_orders": {
        "work_order_no": object(),
        "order_no": object(),
        "status": object(),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# datetime_trunc
# ═══════════════════════════════════════════════════════════════════════════


def test_datetime_trunc_year():
    """DATE_TRUNC('year', col) is generated for year-level truncation."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="order_year",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
                trunc_unit="year",
            )
        ],
        selected_computed_columns=["order_year"],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, params = builder.build()
    assert "DATE_TRUNC('year'" in sql
    assert "order_year" in sql.lower()


def test_datetime_trunc_month():
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="order_month",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
                trunc_unit="month",
            )
        ],
        selected_computed_columns=["order_month"],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "DATE_TRUNC('month'" in sql
    assert "order_month" in sql.lower()


def test_datetime_trunc_day():
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="order_day",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
                trunc_unit="day",
            )
        ],
        selected_computed_columns=["order_day"],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "DATE_TRUNC('day'" in sql
    assert "order_day" in sql.lower()


def test_datetime_trunc_missing_column_raises():
    """Missing trunc_column raises SQLBuildError."""
    builder = ViewSQLBuilder.__new__(ViewSQLBuilder)
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="bad",
                expression_type="datetime_trunc",
            )
        ],
    )
    with pytest.raises(SQLBuildError, match="缺少截断列参数"):
        builder._build_datetime_trunc_expr(config.computed_columns[0])


def test_datetime_trunc_missing_unit_raises():
    """Missing trunc_unit raises SQLBuildError."""
    builder = ViewSQLBuilder.__new__(ViewSQLBuilder)
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="bad",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
            )
        ],
    )
    with pytest.raises(SQLBuildError, match="缺少截断单位"):
        builder._build_datetime_trunc_expr(config.computed_columns[0])


# ═══════════════════════════════════════════════════════════════════════════
# Date range filters
# ═══════════════════════════════════════════════════════════════════════════


def test_date_range_both_start_and_end():
    """Both date_start and date_end produce a combined WHERE clause."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_order_no")],
        filters=[
            FilterSpec(
                column="refund_orders.created_at",
                date_start="2026-01-01",
                date_end="2026-06-30",
            )
        ],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, params = builder.build()
    assert "WHERE" in sql
    assert ">=" in sql
    assert "::DATE" in sql  # column-side cast
    assert "INTERVAL" not in sql  # end date handled in Python
    assert len(params) == 2
    # start stays as date object, end is next day date object
    assert str(params["param_1"]) == "2026-01-01"
    assert str(params["param_2"]) == "2026-07-01"


def test_date_range_start_only():
    """Only date_start produces a >= condition."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_order_no")],
        filters=[
            FilterSpec(
                column="refund_orders.created_at",
                date_start="2026-01-01",
            )
        ],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, params = builder.build()
    assert "WHERE" in sql
    assert "::DATE" in sql  # column-side cast
    assert "INTERVAL" not in sql  # end date handled in Python
    assert len(params) == 1
    assert str(params["param_1"]) == "2026-01-01"


def test_date_range_end_only():
    """Only date_end produces a < condition with INTERVAL."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_order_no")],
        filters=[
            FilterSpec(
                column="refund_orders.created_at",
                date_end="2026-06-30",
            )
        ],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, params = builder.build()
    assert "WHERE" in sql
    assert "<" in sql
    assert "INTERVAL" not in sql  # end date handled in Python
    assert len(params) == 1
    # param should be next day: 2026-07-01 (as date object)
    assert str(params["param_1"]) == "2026-07-01"


def test_date_range_combined_with_operator_filter():
    """Date range filter coexists with an operator-based filter via AND."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_order_no")],
        filters=[
            FilterSpec(column="refund_orders.status", operator="eq", value="已完成"),
            FilterSpec(
                column="refund_orders.created_at",
                date_start="2026-01-01",
                date_end="2026-06-30",
            ),
        ],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, params = builder.build()
    assert "WHERE" in sql
    assert " AND " in sql
    assert "status =" in sql
    assert "::DATE" in sql  # column-side date cast
    assert len(params) == 3  # 1 for status, 2 for date range
    # date params are date objects


# ═══════════════════════════════════════════════════════════════════════════
# ORDER BY
# ═══════════════════════════════════════════════════════════════════════════


def test_order_by_single_column():
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_amount")],
        order_by=[OrderSpec(column="refund_orders.refund_amount", direction="desc")],
        limit=10,
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "ORDER BY" in sql
    assert "refund_amount DESC" in sql
    assert "LIMIT" not in sql  # LIMIT is applied at runtime, not in stored SQL


def test_order_by_multiple_columns():
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="status")],
        order_by=[
            OrderSpec(column="refund_orders.status", direction="asc"),
            OrderSpec(column="refund_orders.refund_amount", direction="desc"),
        ],
        limit=5,
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "ORDER BY" in sql
    assert "status ASC" in sql
    assert "refund_amount DESC" in sql
    assert "LIMIT" not in sql


def test_order_by_without_limit_skips_order():
    """ORDER BY is skipped when apply_limit=False (e.g. for counts)."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="status")],
        order_by=[OrderSpec(column="refund_orders.refund_amount", direction="desc")],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build(apply_limit=False)
    assert "ORDER BY" not in sql


def test_order_by_no_limit():
    """ORDER BY appears even without LIMIT set."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="status")],
        order_by=[OrderSpec(column="refund_orders.status", direction="asc")],
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "ORDER BY" in sql
    assert "status ASC" in sql


def test_order_by_computed_column():
    """ORDER BY can reference a computed column alias."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        computed_columns=[
            ComputedColumnSpec(
                alias="order_year",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
                trunc_unit="year",
            )
        ],
        selected_computed_columns=["order_year"],
        order_by=[OrderSpec(column="order_year", direction="desc")],
        limit=10,
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "ORDER BY" in sql
    assert "order_year DESC" in sql


def test_limit_not_in_generated_sql():
    """User LIMIT is never in the generated SQL — applied at runtime."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        columns=[ColumnSpec(table="refund_orders", column="refund_order_no")],
        limit=50,
    )
    builder = _make_builder(config, REFUND_COLS)
    sql, _ = builder.build()
    assert "LIMIT" not in sql


# ═══════════════════════════════════════════════════════════════════════════
# Integration: all features together
# ═══════════════════════════════════════════════════════════════════════════


def test_full_pipeline_join_filter_order_limit():
    """All new features work together in a realistic query."""
    config = ViewConfig(
        from_tables=["refund_orders"],
        joins=[
            JoinSpec(
                left_table="refund_orders",
                right_table="service_refund_work_orders",
                join_type="INNER",
                left_key="refund_order_no",
                right_key="order_no",
            )
        ],
        columns=[
            ColumnSpec(table="refund_orders", column="refund_order_no", alias="退费单号"),
            ColumnSpec(table="refund_orders", column="status", alias="状态"),
        ],
        filters=[
            FilterSpec(
                column="refund_orders.created_at",
                date_start="2026-01-01",
                date_end="2026-12-31",
            ),
            FilterSpec(column="refund_orders.status", operator="eq", value="已完成"),
        ],
        aggregations=[
            AggregationSpec(function="SUM", column="refund_amount", alias="总金额"),
            AggregationSpec(function="COUNT", column="*", alias="数量"),
        ],
        computed_columns=[
            ComputedColumnSpec(
                alias="order_month",
                expression_type="datetime_trunc",
                trunc_column=ComputedOperand(type="column", table="refund_orders", column="created_at"),
                trunc_unit="month",
            )
        ],
        selected_computed_columns=["order_month"],
        group_by=["refund_orders.status", "order_month"],
        order_by=[OrderSpec(column="总金额", direction="desc")],
        limit=100,
    )
    builder = _make_builder(config, REFUND_SERVICE_COLS)
    sql, params = builder.build()

    # Structural assertions
    assert "SELECT" in sql
    assert "FROM refund_orders" in sql
    assert "INNER JOIN" in sql
    assert "WHERE" in sql
    assert "GROUP BY" in sql
    # LIMIT is not in stored SQL (applied at runtime)
    assert "ORDER BY" in sql
    assert "LIMIT" not in sql
    assert "DATE_TRUNC('month'" in sql
    assert "SUM(" in sql
    assert "COUNT(*)" in sql

    # Date range params: start stays, end is next day (as date objects)
    assert len(params) == 3
    assert str(params.get("param_1")) == "2026-01-01"
    assert str(params.get("param_2")) == "2027-01-01"  # next day after 2026-12-31


# ═══════════════════════════════════════════════════════════════════════════
# Integration: date filter against live API
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_date_filter_preview_integration():
    """Date range filter executes successfully via preview API."""
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/views/preview",
            json={
                "config_json": {
                    "from_tables": ["service_refund_work_orders"],
                    "joins": [],
                    "columns": [
                        {
                            "table": "service_refund_work_orders",
                            "column": "work_order_no",
                            "alias": "工单号",
                        }
                    ],
                    "filters": [
                        {
                            "column": "service_refund_work_orders.registered_at",
                            "date_start": "2026-01-01",
                        }
                    ],
                    "group_by": [],
                    "aggregations": [],
                    "computed_columns": [],
                    "selected_computed_columns": [],
                    "order_by": [],
                    "limit": None,
                }
            },
        )
        assert resp.status_code == 200, f"Preview failed: {resp.text}"
        data = resp.json()
        assert "sql" in data
        assert "rows" in data
        assert "columns" in data
        # Verify the SQL contains the date filter
        assert "::DATE" in data["sql"]
        assert "registered_at" in data["sql"]


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_get_view_data_with_params_integration():
    """get_view_data passes filter params correctly — no 'param_1' bind error."""
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a view with a date range filter (generates :param_N placeholders)
        create_resp = await client.post(
            "/api/views",
            json={
                "name": "_test_view_data_params",
                "description": "Integration test — delete me",
                "config_json": {
                    "from_tables": ["service_refund_work_orders"],
                    "joins": [],
                    "columns": [
                        {
                            "table": "service_refund_work_orders",
                            "column": "work_order_no",
                            "alias": "工单号",
                        }
                    ],
                    "filters": [
                        {
                            "column": "service_refund_work_orders.registered_at",
                            "date_start": "2026-01-01",
                            "date_end": "2026-12-31",
                        }
                    ],
                    "group_by": [],
                    "aggregations": [],
                    "computed_columns": [],
                    "selected_computed_columns": [],
                    "order_by": [],
                    "limit": None,
                },
            },
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        view_id = create_resp.json()["id"]

        try:
            # 2. Fetch view data — this was the buggy path (missing params)
            data_resp = await client.get(
                f"/api/views/{view_id}/data",
                params={"page": 1, "size": 10},
            )
            assert data_resp.status_code == 200, f"get_view_data failed (bind param bug?): {data_resp.text}"
            data = data_resp.json()
            assert "rows" in data
            assert "total" in data
            assert "columns" in data
        finally:
            # 3. Cleanup
            await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_get_view_data_with_operator_filter_integration():
    """get_view_data with text-operator filter passes params correctly."""
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a view with a text operator filter
        create_resp = await client.post(
            "/api/views",
            json={
                "name": "_test_view_data_op_filter",
                "description": "Integration test — delete me",
                "config_json": {
                    "from_tables": ["service_refund_work_orders"],
                    "joins": [],
                    "columns": [
                        {
                            "table": "service_refund_work_orders",
                            "column": "work_order_no",
                            "alias": "工单号",
                        },
                        {
                            "table": "service_refund_work_orders",
                            "column": "status",
                            "alias": "状态",
                        },
                    ],
                    "filters": [
                        {
                            "column": "service_refund_work_orders.status",
                            "operator": "eq",
                            "value": "已完成",
                        }
                    ],
                    "group_by": [],
                    "aggregations": [],
                    "computed_columns": [],
                    "selected_computed_columns": [],
                    "order_by": [],
                    "limit": None,
                },
            },
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        view_id = create_resp.json()["id"]

        try:
            # 2. Fetch view data — verify operator filter params are passed
            data_resp = await client.get(
                f"/api/views/{view_id}/data",
                params={"page": 1, "size": 10},
            )
            assert data_resp.status_code == 200, f"get_view_data failed (bind param bug?): {data_resp.text}"
            data = data_resp.json()
            assert "rows" in data
            assert "total" in data
            assert "columns" in data
        finally:
            # 3. Cleanup
            await client.delete(f"/api/views/{view_id}")


@pytest.mark.asyncio
@pytest.mark.usefixtures("_dispose_engine_after_test")
async def test_get_view_data_limit_caps_total_and_pages():
    """When config.limit is set, total is capped and pagination is consistent."""
    from httpx import ASGITransport, AsyncClient

    from main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create a view with limit=5 (small cap to test pagination)
        create_resp = await client.post(
            "/api/views",
            json={
                "name": "_test_view_limit_cap",
                "description": "Integration test — delete me",
                "config_json": {
                    "from_tables": ["service_refund_work_orders"],
                    "joins": [],
                    "columns": [
                        {
                            "table": "service_refund_work_orders",
                            "column": "work_order_no",
                            "alias": "工单号",
                        }
                    ],
                    "filters": [],
                    "group_by": [],
                    "aggregations": [],
                    "computed_columns": [],
                    "selected_computed_columns": [],
                    "order_by": [],
                    "limit": 5,
                },
            },
        )
        assert create_resp.status_code == 201, f"Create failed: {create_resp.text}"
        view_id = create_resp.json()["id"]

        try:
            # 2. Page 1: size=3 — should get rows, total capped at 5
            data_resp = await client.get(
                f"/api/views/{view_id}/data",
                params={"page": 1, "size": 3},
            )
            assert data_resp.status_code == 200, f"Page 1 failed: {data_resp.text}"
            page1 = data_resp.json()
            assert page1["total"] <= 5, f"total ({page1['total']}) must be capped at 5"
            assert len(page1["rows"]) <= 3
            assert page1["page"] == 1

            # 3. Page 2: should return remaining rows (≤ 2)
            data_resp = await client.get(
                f"/api/views/{view_id}/data",
                params={"page": 2, "size": 3},
            )
            assert data_resp.status_code == 200, f"Page 2 failed: {data_resp.text}"
            page2 = data_resp.json()
            assert page2["total"] <= 5
            assert len(page2["rows"]) <= 2  # remaining from cap of 5
            assert page2["page"] == 2

            # 4. Verify total and size are consistent:
            #    totalPages = ceil(total / size)
            import math

            expected_pages = max(1, math.ceil(page1["total"] / page1["size"]))
            # With total=5, size=3: pages = ceil(5/3) = 2
            assert expected_pages == 2, (
                f"Expected 2 pages for total={page1['total']} size={page1['size']}, got {expected_pages}"
            )
        finally:
            await client.delete(f"/api/views/{view_id}")
