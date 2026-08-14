"""Full-lifecycle integration test for the Schema Manager.

Walks a brand-new table through its entire real-world lifecycle using
actual sample CSV files:

1. Create — infer schema from lifecycle_v1.csv, create the table.
2. Upload — import lifecycle_v1.csv via the existing import engine.
3. Integrate — Data Browser sees it; a view and a visualization are
   built on top of it.
4. Edit — add a column and modify a column type (migrations + registry).
5. Re-upload — import lifecycle_v2.csv containing the new column.
6. Features respond — Data Browser/view/visualization reflect the change.
7. Delete — dependency warning, forced delete, registry removal.

The table and all generated artifacts (migrations, view, visualization)
are cleaned up at the end.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from tests.schema_cleanup import migration_exists, purge_dynamic_table

pytestmark = pytest.mark.usefixtures("_dispose_engine_after_test")

V1_CSV = "订单号,金额,下单日期,备注\nA001,199.50,2026-08-01,首单\nA002,250.00,2026-08-02,\nA003,99.99,2026-08-03,加急\n"

# v2 adds the 折扣 column introduced by the schema edit
V2_CSV = "订单号,金额,下单日期,备注,折扣\nB001,120.00,2026-08-05,会员,9折\nB002,80.00,2026-08-06,,8折\n"


@pytest.mark.asyncio
async def test_full_lifecycle(tmp_path):
    suffix = uuid.uuid4().hex[:6]
    table_name = f"lifecycle_{suffix}"
    view_name = f"生命周期视图_{suffix}"
    viz_name = f"生命周期图表_{suffix}"

    v1_file = tmp_path / "lifecycle_v1.csv"
    v1_file.write_text(V1_CSV, encoding="utf-8")
    v2_file = tmp_path / "lifecycle_v2.csv"
    v2_file.write_text(V2_CSV, encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        view_id = None
        viz_id = None
        try:
            # ── 1. Create (infer + create + migration) ──────────────────
            resp = await client.post(
                "/api/schema/infer-from-csv",
                files={"file": ("lifecycle_v1.csv", v1_file.read_bytes(), "text/csv")},
            )
            assert resp.status_code == 200, resp.text
            inferred = resp.json()
            assert len(inferred["columns"]) == 4
            labels = [c["label"] for c in inferred["columns"]]
            assert labels == ["订单号", "金额", "下单日期", "备注"]

            resp = await client.post(
                "/api/schema/tables",
                json={"name": table_name, "display_name": "生命周期表", "columns": inferred["columns"]},
            )
            assert resp.status_code == 201, resp.text
            assert migration_exists(f"create_table_{table_name}")

            # Column name mapping for later steps (Chinese headers → col_N)
            col_names = {c["label"]: c["name"] for c in inferred["columns"]}
            amount_col = col_names["金额"]
            date_col = col_names["下单日期"]

            # ── 2. Upload data via the existing import engine ───────────
            resp = await client.post(
                "/api/imports",
                files={"file": ("lifecycle_v1.csv", v1_file.read_bytes(), "text/csv")},
                data={"target_table": table_name},
            )
            assert resp.status_code == 200, resp.text
            import_result = resp.json()
            assert import_result["rows_inserted"] == 3
            assert "cleaning_report" in import_result

            # ── 3. Integrate: Data Browser + view + visualization ───────
            tables = (await client.get("/api/tables")).json()
            assert any(t["name"] == table_name and t["chinese_name"] == "生命周期表" for t in tables)

            schema = (await client.get(f"/api/tables/{table_name}/schema")).json()
            assert any(c["name"] == amount_col and c["label"] == "金额" for c in schema)

            view_resp = await client.post(
                "/api/views",
                json={
                    "name": view_name,
                    "description": "lifecycle test view",
                    "config_json": {
                        "from_tables": [table_name],
                        "joins": [],
                        "columns": [
                            {"table": table_name, "column": date_col, "alias": "日期"},
                            {"table": table_name, "column": amount_col, "alias": "金额"},
                        ],
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

            data = (await client.get(f"/api/views/{view_id}/data")).json()
            assert data["total"] == 3

            viz_resp = await client.post(
                "/api/visualizations",
                json={
                    "name": viz_name,
                    "view_id": view_id,
                    "chart_type": "table",
                    "config_json": {"visible_columns": ["日期", "金额"]},
                },
            )
            assert viz_resp.status_code == 201, viz_resp.text
            viz_id = viz_resp.json()["id"]

            # ── 4. Edit schema: add column + modify type ────────────────
            resp = await client.post(
                f"/api/schema/tables/{table_name}/columns",
                json={"name": "discount", "type": "String", "length": 50, "nullable": True, "label": "折扣"},
            )
            assert resp.status_code == 201, resp.text
            assert migration_exists(f"add_column_{table_name}_discount")

            resp = await client.put(
                f"/api/schema/tables/{table_name}/columns/{col_names['备注']}",
                json={"type": "Text"},
            )
            assert resp.status_code == 200, resp.text
            assert migration_exists(f"alter_column_{table_name}_{col_names['备注']}")

            # Runtime registry reflects the added column immediately
            schema = (await client.get(f"/api/tables/{table_name}/schema")).json()
            assert any(c["name"] == "discount" and c["label"] == "折扣" for c in schema)

            # ── 5. Upload edited-schema data (with the new column) ──────
            resp = await client.post(
                "/api/imports",
                files={"file": ("lifecycle_v2.csv", v2_file.read_bytes(), "text/csv")},
                data={"target_table": table_name},
            )
            assert resp.status_code == 200, resp.text
            assert resp.json()["rows_inserted"] == 2

            rows = (await client.get(f"/api/tables/{table_name}/data", params={"size": 50})).json()["rows"]
            discounts = [r.get("discount") for r in rows if r.get("discount")]
            assert "9折" in discounts

            # ── 6. Features respond to the schema change ────────────────
            data = (await client.get(f"/api/views/{view_id}/data")).json()
            assert data["total"] == 5  # 3 v1 rows + 2 v2 rows

            viz_data = (await client.get(f"/api/visualizations/{viz_id}/data")).json()
            assert len(viz_data["rows"]) >= 1

            # ── 7. Delete: dependency warning, forced delete ────────────
            resp = await client.delete(f"/api/schema/tables/{table_name}")
            assert resp.status_code == 409
            deps = resp.json()["detail"]["dependencies"]
            assert any(v["id"] == view_id for v in deps["views"])
            assert any(v["id"] == viz_id for v in deps["visualizations"])

            resp = await client.delete(f"/api/schema/tables/{table_name}?confirm=true")
            assert resp.status_code == 200, resp.text
            assert migration_exists(f"drop_table_{table_name}")

            tables = (await client.get("/api/tables")).json()
            assert not any(t["name"] == table_name for t in tables)

            from app.services.schema_validator import get_registered_tables

            assert table_name not in get_registered_tables()
        finally:
            # Remove dependent assets, then purge table + migrations
            if viz_id:
                await client.delete(f"/api/visualizations/{viz_id}")
            if view_id:
                await client.delete(f"/api/views/{view_id}")
            await purge_dynamic_table(table_name)
