"""Tests for Schema Manager endpoints — /api/schema.

Covers schema inspection, column-type listing, manual create, CSV
inference (against real sample CSV files on disk), add/drop/modify
column, delete table, the read-only guard on business tables, and
runtime registry visibility.

Every test creates uniquely-named tables and purges them (table +
generated migrations + version chain) afterwards — tests run against
the shared dev database and must not accumulate artifacts.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.schema_cleanup import migration_exists, purge_dynamic_table, purge_dynamic_tables

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")

BUSINESS_TABLES = ["refund_orders", "service_refund_work_orders", "wallet_withdrawals"]


def _unique(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:6]}"


async def _create_table(client: AsyncClient, name: str, columns=None) -> None:
    payload = {
        "name": name,
        "display_name": "测试表",
        "columns": columns
        or [
            {"name": "title", "type": "String", "length": 100, "nullable": True, "label": "标题"},
            {"name": "amount", "type": "Numeric", "nullable": True, "label": "金额"},
        ],
    }
    resp = await client.post("/api/schema/tables", json=payload)
    assert resp.status_code == 201, resp.text


# ── Inspection & type system ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_schema_tables_lists_all_with_read_only_flags():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/schema/tables")
        assert resp.status_code == 200
        tables = {t["name"]: t for t in resp.json()}

        for name in BUSINESS_TABLES:
            assert name in tables
            assert tables[name]["read_only"] is True
            assert tables[name]["chinese_name"]
            assert "column_count" in tables[name]
            assert "row_count" in tables[name]


@pytest.mark.asyncio
async def test_column_types_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/schema/column-types")
        assert resp.status_code == 200
        types = {t["key"]: t for t in resp.json()}
        assert set(types) == {
            "String",
            "Text",
            "Integer",
            "BigInteger",
            "Numeric",
            "Boolean",
            "DateTime",
            "Date",
            "JSON",
        }
        assert types["String"]["has_length"] is True
        assert types["Integer"]["has_length"] is False


@pytest.mark.asyncio
async def test_table_detail_includes_columns_and_sample():
    name = _unique("detail")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)
            resp = await client.get(f"/api/schema/tables/{name}")
            assert resp.status_code == 200
            detail = resp.json()
            assert detail["name"] == name
            assert detail["read_only"] is False
            col_names = [c["name"] for c in detail["columns"]]
            assert "title" in col_names
            # Keyless tables dedup via content_hash (dedup defaults to on)
            assert "content_hash" in col_names
            assert "imported_at" in col_names
            title = next(c for c in detail["columns"] if c["name"] == "title")
            assert title["label"] == "标题"
            assert isinstance(detail["sample_rows"], list)
        finally:
            await purge_dynamic_table(name)


# ── Manual creation & runtime registry ──────────────────────────────────────


@pytest.mark.asyncio
async def test_manual_create_generates_migration_and_registers():
    name = _unique("manual")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)

            # A migration file was generated for the new table
            assert migration_exists(f"create_table_{name}")

            # Visible in Data Browser immediately (no restart)
            resp = await client.get("/api/tables")
            assert any(t["name"] == name for t in resp.json())

            # Registered in the runtime registry
            from app.services.schema_validator import get_registered_tables

            assert name in get_registered_tables()
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_create_rejects_duplicate_reserved_and_invalid_names():
    name = _unique("guard")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)

            # Duplicate → 409
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [{"name": "x", "type": "Text", "label": "x"}],
                },
            )
            assert resp.status_code == 409

            # Invalid identifier → 400
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": "Bad-Name",
                    "columns": [{"name": "x", "type": "Text", "label": "x"}],
                },
            )
            assert resp.status_code == 400

            # Reserved/system name → 400
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": "import_jobs",
                    "columns": [{"name": "x", "type": "Text", "label": "x"}],
                },
            )
            assert resp.status_code == 400
        finally:
            await purge_dynamic_table(name)


# ── CSV inference (real files on disk) ──────────────────────────────────────

SAMPLE_CSV = (
    "订单号,金额,下单日期,备注\nA001,199.50,2026-08-01,首单\nA002,250.00,2026-08-02,\nA003,99.99,2026-08-03,加急\n"
)

EDGE_CSV = " 名称 ,数量,空列\n甲,1,\n\n乙,2,\n丙,3,\n"


@pytest.mark.asyncio
async def test_csv_inference_from_real_sample_file(tmp_path):
    csv_file = tmp_path / "sample_phase10.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/schema/infer-from-csv",
            files={"file": ("sample_phase10.csv", csv_file.read_bytes(), "text/csv")},
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["row_count"] == 3
        columns = data["columns"]
        assert len(columns) == 4

        by_label = {c["label"]: c for c in columns}
        assert by_label["金额"]["type"] == "Numeric"
        assert by_label["下单日期"]["type"] in ("Date", "DateTime")
        assert by_label["订单号"]["type"] in ("String", "Text")
        assert by_label["备注"]["type"] in ("String", "Text")
        # Chinese labels suggested from the headers
        assert set(by_label) == {"订单号", "金额", "下单日期", "备注"}

        # No table was created by inference
        tables_resp = await client.get("/api/schema/tables")
        for col in columns:
            assert not any(t["name"] == col["name"] for t in tables_resp.json())


@pytest.mark.asyncio
async def test_csv_inference_edge_cases(tmp_path):
    csv_file = tmp_path / "edge.csv"
    csv_file.write_text(EDGE_CSV, encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/schema/infer-from-csv",
            files={"file": ("edge.csv", csv_file.read_bytes(), "text/csv")},
        )
        assert resp.status_code == 200, resp.text
        columns = resp.json()["columns"]
        assert len(columns) == 3

        # Whitespace in headers is stripped into the label
        assert columns[0]["label"] == "名称"
        # Integer column detected
        assert columns[1]["type"] == "Integer"
        # All-null column falls back to String without error
        assert columns[2]["type"] == "String"
        # Column names are unique, safe identifiers
        names = [c["name"] for c in columns]
        assert len(set(names)) == 3
        assert all(n.replace("_", "").isalnum() and n[0].islower() for n in names)


@pytest.mark.asyncio
async def test_infer_then_create_end_to_end(tmp_path):
    csv_file = tmp_path / "orders.csv"
    csv_file.write_text(SAMPLE_CSV, encoding="utf-8")
    name = _unique("inferred")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/infer-from-csv",
                files={"file": ("orders.csv", csv_file.read_bytes(), "text/csv")},
            )
            assert resp.status_code == 200
            proposed = resp.json()["columns"]

            resp = await client.post(
                "/api/schema/tables",
                json={"name": name, "display_name": "推断表", "columns": proposed},
            )
            assert resp.status_code == 201, resp.text

            detail = (await client.get(f"/api/schema/tables/{name}")).json()
            labels = [c["label"] for c in detail["columns"]]
            assert "金额" in labels
        finally:
            await purge_dynamic_table(name)


# ── Column add / drop / modify ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_modify_drop_column():
    name = _unique("coledit")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)

            # Add column
            resp = await client.post(
                f"/api/schema/tables/{name}/columns",
                json={"name": "remark", "type": "Text", "nullable": True, "label": "备注"},
            )
            assert resp.status_code == 201, resp.text
            assert migration_exists(f"add_column_{name}_remark")
            cols = [c["name"] for c in (await client.get(f"/api/schema/tables/{name}")).json()["columns"]]
            assert "remark" in cols

            # Registry reflects the change (Data Browser schema)
            schema = (await client.get(f"/api/tables/{name}/schema")).json()
            assert any(c["name"] == "remark" and c["label"] == "备注" for c in schema)

            # Modify column type — Numeric → String is safe, no warning
            resp = await client.put(
                f"/api/schema/tables/{name}/columns/amount",
                json={"type": "String", "length": 50},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["warning"] is None
            assert migration_exists(f"alter_column_{name}_amount")

            # Modify column type — String → Integer is lossy → warning
            resp = await client.put(
                f"/api/schema/tables/{name}/columns/title",
                json={"type": "Integer"},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["warning"]

            # Drop column
            resp = await client.delete(f"/api/schema/tables/{name}/columns/remark")
            assert resp.status_code == 200, resp.text
            assert migration_exists(f"drop_column_{name}_remark")
            cols = [c["name"] for c in (await client.get(f"/api/schema/tables/{name}")).json()["columns"]]
            assert "remark" not in cols
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_drop_missing_column_returns_404():
    name = _unique("missing")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)
            resp = await client.delete(f"/api/schema/tables/{name}/columns/nope")
            assert resp.status_code == 404
        finally:
            await purge_dynamic_table(name)


# ── Delete table ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_table_removes_from_registry():
    name = _unique("todelete")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await _create_table(client, name)

        resp = await client.delete(f"/api/schema/tables/{name}")
        assert resp.status_code == 200, resp.text
        assert migration_exists(f"drop_table_{name}")

        # Gone from Data Browser + registry
        tables = (await client.get("/api/tables")).json()
        assert not any(t["name"] == name for t in tables)
        resp = await client.get(f"/api/schema/tables/{name}")
        assert resp.status_code == 404

        await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_delete_with_dependencies_requires_confirm():
    name = _unique("dep")
    view_name = f"依赖视图_{uuid.uuid4().hex[:6]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = None
        try:
            await _create_table(client, name)
            view_resp = await client.post(
                "/api/views",
                json={
                    "name": view_name,
                    "description": "lifecycle dep test",
                    "config_json": {
                        "from_tables": [name],
                        "joins": [],
                        "columns": [{"table": name, "column": "title", "alias": None}],
                        "computed_columns": [],
                        "selected_computed_columns": [],
                        "filters": [],
                        "group_by": [],
                        "aggregations": [],
                    },
                },
            )
            assert view_resp.status_code == 201, view_resp.text
            view_id = view_resp.json()["id"]

            # Dependencies endpoint reports the view
            deps = (await client.get(f"/api/schema/tables/{name}/dependencies")).json()
            assert any(v["id"] == view_id for v in deps["views"])

            # Delete without confirm → 409 with dependency details
            resp = await client.delete(f"/api/schema/tables/{name}")
            assert resp.status_code == 409
            assert resp.json()["detail"]["dependencies"]["views"]

            # With confirm → succeeds
            resp = await client.delete(f"/api/schema/tables/{name}?confirm=true")
            assert resp.status_code == 200, resp.text
        finally:
            if view_id:
                await client.delete(f"/api/views/{view_id}")
            await purge_dynamic_table(name)


# ── Read-only guard on business tables ─────────────────────────────────────


@pytest.mark.asyncio
async def test_read_only_guard_on_business_tables():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for table in BUSINESS_TABLES:
            resp = await client.delete(f"/api/schema/tables/{table}")
            assert resp.status_code == 403

            resp = await client.post(
                f"/api/schema/tables/{table}/columns",
                json={"name": "hack", "type": "Text", "label": "hack"},
            )
            assert resp.status_code == 403

            resp = await client.delete(f"/api/schema/tables/{table}/columns/id")
            assert resp.status_code == 403

            resp = await client.put(f"/api/schema/tables/{table}/columns/id", json={"type": "Text"})
            assert resp.status_code == 403


# ── Primary key & foreign key support ───────────────────────────────────────


@pytest.mark.asyncio
async def test_create_with_user_primary_key():
    name = _unique("pk")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "display_name": "主键表",
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 100, "label": "部门名称"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            detail = resp.json()
            col_names = [c["name"] for c in detail["columns"]]
            assert "id" not in col_names  # no surrogate id when a user PK is set
            pk = next(c for c in detail["columns"] if c["name"] == "dept_id")
            assert pk["primary_key"] is True
            assert pk["nullable"] is False
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_only_one_primary_key_allowed():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/schema/tables",
            json={
                "name": _unique("badpk"),
                "columns": [
                    {"name": "a", "type": "Integer", "primary_key": True, "label": "a"},
                    {"name": "b", "type": "Integer", "primary_key": True, "label": "b"},
                ],
            },
        )
        assert resp.status_code == 400
        assert "主键" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_foreign_key_lifecycle_and_guards():
    dept = _unique("dept")
    emp = _unique("emp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            # Parent table with a user primary key
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": dept,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 100, "label": "部门"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # Child table with a foreign key to the parent PK
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": emp,
                    "columns": [
                        {"name": "emp_id", "type": "Integer", "primary_key": True, "label": "员工编号"},
                        {"name": "emp_name", "type": "String", "length": 100, "label": "姓名"},
                        {
                            "name": "dept_id",
                            "type": "Integer",
                            "foreign_key": f"{dept}.dept_id",
                            "label": "部门",
                        },
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            fk_col = next(c for c in resp.json()["columns"] if c["name"] == "dept_id")
            assert fk_col["foreign_key"] == f"{dept}.dept_id"

            # Deleting the parent is blocked by the FK — even with confirm
            resp = await client.delete(f"/api/schema/tables/{dept}?confirm=true")
            assert resp.status_code == 409
            deps = resp.json()["detail"]["dependencies"]
            assert any(t["table"] == emp for t in deps["tables"])

            # Dropping the referenced parent column is blocked too (PK or FK-referenced)
            resp = await client.delete(f"/api/schema/tables/{dept}/columns/dept_id")
            assert resp.status_code in (403, 409)

            # Delete the child first, then the parent succeeds
            resp = await client.delete(f"/api/schema/tables/{emp}")
            assert resp.status_code == 200, resp.text
            resp = await client.delete(f"/api/schema/tables/{dept}")
            assert resp.status_code == 200, resp.text
        finally:
            # Batch purge: emp/dept migrations interleave, so they must be
            # removed together to keep the revision chain intact
            await purge_dynamic_tables(emp, dept)


@pytest.mark.asyncio
async def test_dynamic_table_restored_after_restart():
    """Dynamic tables survive a server restart via the startup restore hook."""
    name = _unique("restore")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)

            # Simulate a restart: wipe the in-memory registries
            from app.core.database import engine
            from app.services import schema_manager as sm
            from app.services import schema_validator

            sm.unregister_dynamic_table(name)
            assert name not in schema_validator.get_registered_tables()

            # Startup restore re-registers the table with its display name
            async with engine.connect() as conn:
                restored = await sm.restore_dynamic_tables(conn)
            assert restored >= 1
            assert name in schema_validator.get_registered_tables()
            assert schema_validator.get_chinese_table_name(name) == "测试表"

            # Visible in Data Browser again
            resp = await client.get("/api/tables")
            assert any(t["name"] == name for t in resp.json())

            # Cleanup through the API still works on the restored model
            resp = await client.delete(f"/api/schema/tables/{name}")
            assert resp.status_code == 200, resp.text
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_foreign_key_validation_errors():
    name = _unique("fkbad")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, name)

            # Bad reference format
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": _unique("fkbad2"),
                    "columns": [{"name": "x", "type": "Integer", "foreign_key": "not-a-ref", "label": "x"}],
                },
            )
            assert resp.status_code == 400

            # Non-existent target table
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": _unique("fkbad3"),
                    "columns": [{"name": "x", "type": "Integer", "foreign_key": "nope.col", "label": "x"}],
                },
            )
            assert resp.status_code == 400

            # Target column that is not a PK/unique column
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": _unique("fkbad4"),
                    "columns": [{"name": "x", "type": "Numeric", "foreign_key": f"{name}.amount", "label": "x"}],
                },
            )
            assert resp.status_code == 400

            # Adding a primary key column to an existing table is rejected
            resp = await client.post(
                f"/api/schema/tables/{name}/columns",
                json={"name": "pk", "type": "Integer", "primary_key": True, "label": "pk"},
            )
            assert resp.status_code == 400
        finally:
            await purge_dynamic_table(name)


# ── Description, default values & comprehensive editing ────────────────


@pytest.mark.asyncio
async def test_create_with_description_and_default():
    name = _unique("descdef")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "display_name": "描述表",
                    "columns": [
                        {
                            "name": "status",
                            "type": "String",
                            "length": 20,
                            "label": "状态",
                            "description": "订单当前状态",
                            "default": "待处理",
                        },
                        {
                            "name": "qty",
                            "type": "Integer",
                            "label": "数量",
                            "default": "1",
                        },
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            detail = resp.json()
            status = next(c for c in detail["columns"] if c["name"] == "status")
            assert status["description"] == "订单当前状态"
            assert status["default"] == "待处理"
            qty = next(c for c in detail["columns"] if c["name"] == "qty")
            assert qty["default"] == "1"

            # Invalid default for the type is rejected
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": _unique("baddef"),
                    "columns": [
                        {"name": "n", "type": "Integer", "label": "n", "default": "abc"},
                    ],
                },
            )
            assert resp.status_code == 400
            assert "默认值" in resp.json()["detail"]
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_comprehensive_column_edit():
    parent = _unique("eparent")
    child = _unique("echild")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": parent,
                    "columns": [
                        {"name": "pid", "type": "Integer", "primary_key": True, "label": "父ID"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": child,
                    "columns": [
                        {"name": "title", "type": "String", "length": 100, "label": "标题"},
                        {"name": "code", "type": "Integer", "label": "编码", "unique": True},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # Rename + label + description in one edit
            resp = await client.put(
                f"/api/schema/tables/{child}/columns/title",
                json={"name": "title_new", "label": "新标题", "description": "改名后的标题"},
            )
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{child}")).json()
            col = next(c for c in detail["columns"] if c["name"] == "title_new")
            assert col["label"] == "新标题"
            assert col["description"] == "改名后的标题"

            # Description-only edit works without a migration
            resp = await client.put(
                f"/api/schema/tables/{child}/columns/title_new",
                json={"description": "仅更新描述"},
            )
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{child}")).json()
            col = next(c for c in detail["columns"] if c["name"] == "title_new")
            assert col["description"] == "仅更新描述"

            # Nullable flip + default set on the renamed column
            resp = await client.put(
                f"/api/schema/tables/{child}/columns/title_new",
                json={"nullable": False, "default": "未命名"},
            )
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{child}")).json()
            col = next(c for c in detail["columns"] if c["name"] == "title_new")
            assert col["nullable"] is False
            assert col["default"] == "未命名"

            # Remove unique from 'code', then add a foreign key
            resp = await client.put(
                f"/api/schema/tables/{child}/columns/code",
                json={"unique": False, "foreign_key": f"{parent}.pid"},
            )
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{child}")).json()
            col = next(c for c in detail["columns"] if c["name"] == "code")
            assert col["unique"] is False
            assert col["foreign_key"] == f"{parent}.pid"

            # Remove the foreign key again
            resp = await client.put(
                f"/api/schema/tables/{child}/columns/code",
                json={"foreign_key": ""},
            )
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{child}")).json()
            col = next(c for c in detail["columns"] if c["name"] == "code")
            assert col["foreign_key"] is None
        finally:
            await purge_dynamic_tables(child, parent)


@pytest.mark.asyncio
async def test_fk_options_endpoint():
    parent = _unique("fkopt")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": parent,
                    "columns": [
                        {"name": "pid", "type": "Integer", "primary_key": True, "label": "父ID"},
                        {"name": "plain", "type": "String", "length": 10, "label": "普通列"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            resp = await client.get("/api/schema/fk-options")
            assert resp.status_code == 200
            options = {o["table"]: o for o in resp.json()}
            assert parent in options
            col_names = [c["name"] for c in options[parent]["columns"]]
            assert "pid" in col_names
            assert "plain" not in col_names  # only PK/unique columns are eligible
        finally:
            await purge_dynamic_table(parent)


@pytest.mark.asyncio
async def test_import_matches_by_label_and_column_name(tmp_path):
    """Upload headers may match either the Chinese label or the real column name."""
    name = _unique("match")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "order_no", "type": "String", "length": 50, "label": "订单号"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # Headers mix Chinese labels and real column names
            csv_file = tmp_path / "mixed.csv"
            csv_file.write_text("订单号,amount\nA1,10.5\nA2,20.0\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("mixed.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["rows_inserted"] == 2
        finally:
            await purge_dynamic_table(name)


# ── BOM handling in uploads ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_strips_bom_from_first_header(tmp_path):
    """A leading BOM (even doubled) must not glue onto the first header."""
    name = _unique("bom")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        # First column is a required user PK — the exact case
                        # that failed before the BOM fix.
                        {"name": "order_no", "type": "String", "length": 50, "primary_key": True, "label": "订单号"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # Double BOM + Chinese headers
            csv_file = tmp_path / "bom.csv"
            csv_file.write_text("\ufeff\ufeff订单号,金额\nA1,10.5\nA2,20.0\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("bom.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["rows_inserted"] == 2
        finally:
            await purge_dynamic_table(name)


# ── Upload counting & strict header matching ───────────────────────


@pytest.mark.asyncio
async def test_upsert_count_semantics_for_pk_table(tmp_path):
    """新增/更新/跳过/拒绝 must follow the ingestion definitions exactly.

    新增 = no matching record, added;
    更新 = matching key, at least one stored value changed;
    跳过 = matching key, all provided values identical;
    拒绝 = invalid / cannot be legally written.
    """
    name = _unique("counts")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 50, "label": "部门名称"},
                        {"name": "manager", "type": "String", "length": 50, "label": "负责人", "default": "待定"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            data = {"target_table": name}

            async def aupload(content: str, fname: str) -> dict:
                f = tmp_path / fname
                f.write_text(content, encoding="utf-8")
                resp = await client.post(
                    "/api/imports",
                    files={"file": (fname, f.read_bytes(), "text/csv")},
                    data=data,
                )
                assert resp.status_code == 200, resp.text
                return resp.json()

            # 1) Two fresh records → 2 新增
            body = await aupload("部门编号,部门名称,负责人\n1,A,杨\n2,B,李\n", "f1.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                2,
                0,
                0,
                0,
            )

            # 2) Identical re-upload → 2 跳过, nothing else
            body = await aupload("部门编号,部门名称,负责人\n1,A,杨\n2,B,李\n", "f2.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                0,
                2,
                0,
            )

            # 3) One changed record + one new record → 1 更新 + 1 新增
            body = await aupload("部门编号,部门名称,负责人\n1,A2,杨\n3,C,王\n", "f3.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                1,
                1,
                0,
                0,
            )

            # 4) Partial upload touches only the provided columns:
            #    dept_name must NOT be nulled out, and the change counts
            body = await aupload("部门编号,负责人\n2,李四\n", "f4.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                1,
                0,
                0,
            )

            # 5) Invalid key value cannot be written → 1 拒绝
            body = await aupload("部门编号,部门名称,负责人\nabc,X,赵\n", "f5.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                0,
                0,
                1,
            )

            # Final DB state: changed value applied, omitted column preserved
            detail = (await client.get(f"/api/schema/tables/{name}")).json()
            rows = {r["dept_id"]: r for r in detail["sample_rows"]}
            assert rows[1]["dept_name"] == "A2"
            assert rows[2]["dept_name"] == "B"  # untouched by the partial upload
            assert rows[2]["manager"] == "李四"
            assert rows[3]["dept_name"] == "C"
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_reupload_same_file_counts_skipped(tmp_path):
    """Re-uploading identical data must not report phantom inserts."""
    name = _unique("reup")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 50, "label": "部门名称"},
                        {"name": "manager", "type": "String", "length": 50, "label": "负责人"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            csv_file = tmp_path / "dept.csv"
            csv_file.write_text("部门编号,部门名称,负责人\n1,技术部,杨帆\n2,市场部,李娜\n", encoding="utf-8")
            data = {"target_table": name}

            resp = await client.post(
                "/api/imports",
                files={"file": ("dept.csv", csv_file.read_bytes(), "text/csv")},
                data=data,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["rows_inserted"] == 2
            assert body["rows_skipped"] == 0
            assert body["rows_rejected"] == 0

            # Second identical upload: nothing new, both rows skipped
            resp = await client.post(
                "/api/imports",
                files={"file": ("dept.csv", csv_file.read_bytes(), "text/csv")},
                data=data,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["rows_inserted"] == 0
            assert body["rows_skipped"] == 2
            assert body["rows_rejected"] == 0
            assert body["total_rows"] == 2
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_reupload_with_date_and_numeric_columns_counts_skipped(tmp_path):
    """DATE/NUMERIC columns must compare equal on identical re-upload.

    Regression: PG DATE returns date while the importer coerces to
    datetime; datetime == date is always False, which made every row
    count as 更新 on re-upload.
    """
    name = _unique("dtnum")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "emp_id", "type": "Integer", "primary_key": True, "label": "编号"},
                        {"name": "salary", "type": "Numeric", "label": "薪资"},
                        {"name": "hire_date", "type": "Date", "label": "入职日期"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            csv_file = tmp_path / "emp.csv"
            content = "编号,薪资,入职日期\n101,15800.50,2023-03-15\n102,13200.00,2021-11-20\n"
            csv_file.write_text(content, encoding="utf-8")
            data = {"target_table": name}

            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", csv_file.read_bytes(), "text/csv")},
                data=data,
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["rows_inserted"] == 2

            # Identical re-upload: everything skipped, nothing updated
            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", csv_file.read_bytes(), "text/csv")},
                data=data,
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                0,
                2,
                0,
            )
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_upload_rejected_when_headers_do_not_match_table(tmp_path):
    """A file whose headers belong to another table must be rejected —
    even when the target's required columns happen to be covered."""
    name = _unique("wrong")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 50, "label": "部门名称"},
                        {"name": "manager", "type": "String", "length": 50, "label": "负责人"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # 员工-style file: 部门编号/负责人 match, but four headers don't
            csv_file = tmp_path / "emp.csv"
            csv_file.write_text(
                "员工编号,姓名,部门编号,职位,薪资,入职日期\n101,张伟,1,工程师,100,2024-01-01\n",
                encoding="utf-8",
            )
            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 422, resp.text
            body = resp.json()
            assert set(body["unexpected"]) == {"员工编号", "姓名", "职位", "薪资", "入职日期"}
            assert "无法匹配" in body["detail"]
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_upload_with_extra_unmatched_header_rejected(tmp_path):
    """Every file header must map to a table column — extras fail the gate."""
    name = _unique("extra")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "title", "type": "String", "length": 50, "label": "标题"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            csv_file = tmp_path / "extra.csv"
            csv_file.write_text("标题,金额,多余列\nA,1,x\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("extra.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 422, resp.text
            assert resp.json()["unexpected"] == ["多余列"]
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_duplicate_pk_rows_in_one_file_collapse(tmp_path):
    """Duplicate PK rows within one file collapse (last wins) — no rejects."""
    name = _unique("dupkey")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                        {"name": "dept_name", "type": "String", "length": 50, "label": "部门名称"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            csv_file = tmp_path / "dup.csv"
            csv_file.write_text("部门编号,部门名称\n1,旧名称\n1,新名称\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("dup.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": name},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert body["rows_inserted"] == 1
            assert body["rows_skipped"] == 1  # the collapsed duplicate key row
            assert body["rows_rejected"] == 0

            detail = (await client.get(f"/api/schema/tables/{name}")).json()
            row = next(r for r in detail["sample_rows"] if r["dept_id"] == 1)
            assert row["dept_name"] == "新名称"
        finally:
            await purge_dynamic_table(name)


# ── Table rename (English name + Chinese display name) ───────────────────


@pytest.mark.asyncio
async def test_rename_table_display_name_only():
    old = _unique("rn")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, old)
            resp = await client.put(f"/api/schema/tables/{old}", json={"display_name": "新显示名"})
            assert resp.status_code == 200, resp.text
            detail = (await client.get(f"/api/schema/tables/{old}")).json()
            assert detail["name"] == old  # English name unchanged
            assert detail["chinese_name"] == "新显示名"
            assert migration_exists(f"settings_table_{old}")
        finally:
            await purge_dynamic_table(old)


@pytest.mark.asyncio
async def test_rename_table_english_name():
    old = _unique("rn")
    new = f"{old}_two"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            await _create_table(client, old)
            resp = await client.put(f"/api/schema/tables/{old}", json={"name": new})
            assert resp.status_code == 200, resp.text
            assert resp.json()["name"] == new

            # Old name is gone, new name is registered and detailed
            assert (await client.get(f"/api/schema/tables/{old}")).status_code == 404
            detail = (await client.get(f"/api/schema/tables/{new}")).json()
            assert detail["name"] == new
            assert detail["chinese_name"] == "测试表"  # display name preserved

            # Visible in Data Browser under the new name
            tables = (await client.get("/api/tables")).json()
            assert any(t["name"] == new for t in tables)
            assert not any(t["name"] == old for t in tables)

            # Renaming to an existing table name is rejected
            other = _unique("rnother")
            await _create_table(client, other)
            resp = await client.put(f"/api/schema/tables/{new}", json={"name": other})
            assert resp.status_code == 409
            await purge_dynamic_table(other)
        finally:
            await purge_dynamic_tables(new, old)


@pytest.mark.asyncio
async def test_rename_blocked_when_referenced_by_view():
    old = _unique("rnview")
    view_name = f"重命名依赖_{uuid.uuid4().hex[:6]}"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = None
        try:
            await _create_table(client, old)
            view_resp = await client.post(
                "/api/views",
                json={
                    "name": view_name,
                    "description": "rename dep test",
                    "config_json": {
                        "from_tables": [old],
                        "joins": [],
                        "columns": [{"table": old, "column": "title", "alias": None}],
                        "computed_columns": [],
                        "selected_computed_columns": [],
                        "filters": [],
                        "group_by": [],
                        "aggregations": [],
                    },
                },
            )
            assert view_resp.status_code == 201, view_resp.text
            view_id = view_resp.json()["id"]

            resp = await client.put(f"/api/schema/tables/{old}", json={"name": f"{old}_x"})
            assert resp.status_code == 409
        finally:
            if view_id:
                await client.delete(f"/api/views/{view_id}")
            await purge_dynamic_table(old)


@pytest.mark.asyncio
async def test_fk_target_can_be_unique_column():
    """Foreign keys may target a UNIQUE column, not only a primary key."""
    parent = _unique("fkuparent")
    child = _unique("fkuchild")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": parent,
                    "columns": [
                        {"name": "code", "type": "Integer", "label": "编码", "unique": True},
                        {"name": "title", "type": "String", "length": 50, "label": "标题"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            # FK to the unique (non-PK) column is accepted
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": child,
                    "columns": [
                        {"name": "ref", "type": "Integer", "foreign_key": f"{parent}.code", "label": "引用"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            fk_col = next(c for c in resp.json()["columns"] if c["name"] == "ref")
            assert fk_col["foreign_key"] == f"{parent}.code"

            # fk-options exposes the unique column and marks it unique
            opts = {o["table"]: o for o in (await client.get("/api/schema/fk-options")).json()}
            cols = {c["name"]: c for c in opts[parent]["columns"]}
            assert "code" in cols
            assert cols["code"]["unique"] is True
            assert cols["code"]["primary_key"] is False
        finally:
            await purge_dynamic_tables(child, parent)


@pytest.mark.asyncio
async def test_fk_violation_row_counts_rejected_only(tmp_path):
    """A new row violating an FK must count as 拒绝 only, never also 新增.

    Regression: insert-intent rows were pre-counted as 新增 before the
    write; when the batch failed and the per-row fallback rejected the
    FK-violating row, that row was double-counted (新增 + 拒绝).
    """
    parent = _unique("fkvdept")
    child = _unique("fkvemp")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": parent,
                    "columns": [
                        {"name": "dept_id", "type": "Integer", "primary_key": True, "label": "部门编号"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": child,
                    "columns": [
                        {"name": "emp_id", "type": "Integer", "primary_key": True, "label": "员工编号"},
                        {"name": "dept_id", "type": "Integer", "foreign_key": f"{parent}.dept_id", "label": "部门编号"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text

            resp = await client.post(
                "/api/imports",
                files={"file": ("p.csv", "部门编号\n1\n2\n", "text/csv")},
                data={"target_table": parent},
            )
            assert resp.status_code == 200, resp.text

            csv_file = tmp_path / "emp.csv"
            good = "员工编号,部门编号\n101,1\n102,2\n"
            csv_file.write_text(good, encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": child},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["rows_inserted"] == 2

            # Re-upload: the two original rows unchanged + one new row whose
            # FK value does not exist in the parent table
            csv_file.write_text(good + "103,999\n", encoding="utf-8")
            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", csv_file.read_bytes(), "text/csv")},
                data={"target_table": child},
            )
            assert resp.status_code == 200, resp.text
            body = resp.json()
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                0,
                2,
                1,
            )

            # The violating row must not have been written
            resp = await client.post(
                "/api/imports",
                files={"file": ("emp.csv", good.encode(), "text/csv")},
                data={"target_table": child},
            )
            assert resp.json()["rows_skipped"] == 2
        finally:
            await purge_dynamic_tables(child, parent)


# ── Configurable upsert key & dedup toggle (duplicate scenarios) ─────────


@pytest.mark.asyncio
async def test_composite_upsert_key_duplicate_handling(tmp_path):
    """A composite upsert key drives update/skip; in-file key dups collapse."""
    name = _unique("ckey")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "upsert_key": ["code", "region"],
                    "columns": [
                        {"name": "code", "type": "String", "length": 20, "label": "编码"},
                        {"name": "region", "type": "String", "length": 20, "label": "区域"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            detail = resp.json()
            assert detail["upsert_key"] == ["code", "region"]
            col_names = [c["name"] for c in detail["columns"]]
            assert "content_hash" not in col_names  # keyed table, no hash

            data = {"target_table": name}

            async def upload(content: str, fname: str) -> dict:
                f = tmp_path / fname
                f.write_text(content, encoding="utf-8")
                r = await client.post(
                    "/api/imports",
                    files={"file": (fname, f.read_bytes(), "text/csv")},
                    data=data,
                )
                assert r.status_code == 200, r.text
                return r.json()

            # In-file duplicate on the composite key collapses (last wins)
            body = await upload("编码,区域,金额\nc1,华东,10\nc1,华东,20\nc2,华北,5\n", "f1.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                2,
                0,
                1,
                0,
            )

            # Same file again: everything matches and is identical
            body = await upload("编码,区域,金额\nc1,华东,20\nc2,华北,5\n", "f2.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                0,
                2,
                0,
            )

            # Changed value on the same composite key → update
            body = await upload("编码,区域,金额\nc1,华东,99\n", "f3.csv")
            assert (body["rows_inserted"], body["rows_updated"], body["rows_skipped"], body["rows_rejected"]) == (
                0,
                1,
                0,
                0,
            )

            rows = (await client.get(f"/api/schema/tables/{name}")).json()["sample_rows"]
            c1 = next(r for r in rows if r["code"] == "c1")
            assert float(c1["amount"]) == 99.0
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_keyless_dedup_enabled_skips_identical_rows(tmp_path):
    """Keyless table + dedup on: content_hash column, identical rows skipped."""
    name = _unique("kd")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "title", "type": "String", "length": 50, "label": "标题"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            detail = resp.json()
            assert detail["upsert_key"] == []
            assert detail["dedup_enabled"] is True
            col_names = [c["name"] for c in detail["columns"]]
            assert "content_hash" in col_names

            data = {"target_table": name}
            f = tmp_path / "d.csv"
            content = "标题,金额\n甲,1\n乙,2\n"
            f.write_text(content, encoding="utf-8")

            r = await client.post("/api/imports", files={"file": ("d.csv", f.read_bytes(), "text/csv")}, data=data)
            assert r.status_code == 200, r.text
            assert r.json()["rows_inserted"] == 2

            # Identical re-upload → all skipped, nothing inserted/rejected
            r = await client.post("/api/imports", files={"file": ("d.csv", f.read_bytes(), "text/csv")}, data=data)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["rows_inserted"] == 0
            assert body["rows_skipped"] == 2
            assert body["rows_rejected"] == 0

            # Exact duplicates WITHIN one file are skipped, not rejected
            f2 = tmp_path / "d2.csv"
            f2.write_text("标题,金额\n丙,3\n丙,3\n", encoding="utf-8")
            r = await client.post("/api/imports", files={"file": ("d2.csv", f2.read_bytes(), "text/csv")}, data=data)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["rows_inserted"] == 1
            assert body["rows_skipped"] == 1
            assert body["rows_rejected"] == 0
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_keyless_dedup_disabled_inserts_every_row(tmp_path):
    """Keyless table + dedup off: pure insert, duplicates kept."""
    name = _unique("kn")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "dedup_enabled": False,
                    "columns": [
                        {"name": "title", "type": "String", "length": 50, "label": "标题"},
                        {"name": "amount", "type": "Numeric", "label": "金额"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            detail = resp.json()
            assert detail["dedup_enabled"] is False
            col_names = [c["name"] for c in detail["columns"]]
            assert "content_hash" not in col_names

            data = {"target_table": name}
            f = tmp_path / "n.csv"
            content = "标题,金额\n甲,1\n甲,1\n"
            f.write_text(content, encoding="utf-8")

            # Both duplicate rows are inserted…
            r = await client.post("/api/imports", files={"file": ("n.csv", f.read_bytes(), "text/csv")}, data=data)
            assert r.status_code == 200, r.text
            assert r.json()["rows_inserted"] == 2

            # …and again on re-upload (no dedup anywhere)
            r = await client.post("/api/imports", files={"file": ("n.csv", f.read_bytes(), "text/csv")}, data=data)
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["rows_inserted"] == 2
            assert body["rows_skipped"] == 0
        finally:
            await purge_dynamic_table(name)


@pytest.mark.asyncio
async def test_settings_validation_rules():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Disabling dedup while a PK exists is rejected
        resp = await client.post(
            "/api/schema/tables",
            json={
                "name": _unique("badcfg"),
                "dedup_enabled": False,
                "columns": [{"name": "pid", "type": "Integer", "primary_key": True, "label": "ID"}],
            },
        )
        assert resp.status_code == 400
        assert "去重" in resp.json()["detail"]

        # Upsert key referencing a missing column is rejected
        resp = await client.post(
            "/api/schema/tables",
            json={
                "name": _unique("badcfg2"),
                "upsert_key": ["nope"],
                "columns": [{"name": "title", "type": "String", "length": 50, "label": "标题"}],
            },
        )
        assert resp.status_code == 400
        assert "Upsert" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_edit_upsert_key_via_settings_endpoint(tmp_path):
    """Changing the upsert key on an existing (empty) table re-keys imports."""
    name = _unique("ek")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            resp = await client.post(
                "/api/schema/tables",
                json={
                    "name": name,
                    "columns": [
                        {"name": "code", "type": "String", "length": 20, "label": "编码"},
                        {"name": "title", "type": "String", "length": 50, "label": "标题"},
                    ],
                },
            )
            assert resp.status_code == 201, resp.text
            assert resp.json()["dedup_enabled"] is True
            assert any(c["name"] == "content_hash" for c in resp.json()["columns"])

            # Switch to an explicit upsert key → content_hash drops, key applies
            resp = await client.put(f"/api/schema/tables/{name}", json={"upsert_key": ["code"]})
            assert resp.status_code == 200, resp.text
            detail = resp.json()
            assert detail["upsert_key"] == ["code"]
            assert not any(c["name"] == "content_hash" for c in detail["columns"])

            data = {"target_table": name}

            async def upload(content: str, fname: str) -> dict:
                f = tmp_path / fname
                f.write_text(content, encoding="utf-8")
                r = await client.post(
                    "/api/imports",
                    files={"file": (fname, f.read_bytes(), "text/csv")},
                    data=data,
                )
                assert r.status_code == 200, r.text
                return r.json()

            body = await upload("编码,标题\nk1,旧\n", "e1.csv")
            assert body["rows_inserted"] == 1
            body = await upload("编码,标题\nk1,新\n", "e2.csv")
            assert (body["rows_updated"], body["rows_inserted"], body["rows_rejected"]) == (1, 0, 0)

            rows = (await client.get(f"/api/schema/tables/{name}")).json()["sample_rows"]
            assert next(r for r in rows if r["code"] == "k1")["title"] == "新"

            # Clearing the key on a keyed table falls back to keyless+dedup
            resp = await client.put(f"/api/schema/tables/{name}", json={"upsert_key": []})
            assert resp.status_code == 200, resp.text
            detail = resp.json()
            assert detail["upsert_key"] == []
            assert any(c["name"] == "content_hash" for c in detail["columns"])
        finally:
            await purge_dynamic_table(name)
