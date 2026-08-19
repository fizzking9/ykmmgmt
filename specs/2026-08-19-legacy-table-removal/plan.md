# Phase 11 — Legacy Business Table Removal & System Reset: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Database Migration & Data Cleanup

1. Write a single Alembic migration that:
   - Drops `refund_orders`, `service_refund_work_orders`, `wallet_withdrawals` tables
   - Deletes all rows from `views`, `visualizations`, `dashboards` where `generated_sql` or `config_json` references any of the three table names
   - Deletes `ImportJob` and `DataSource` records tied to the three tables
   - Deletes orphaned `column_meta` and `table_meta` rows for the three tables
2. Run the migration against a development database copy and verify:
   - Three tables are gone
   - No orphaned views/visualizations/dashboards remain
   - System tables (`datasources`, `import_jobs`, `views`, `visualizations`, `dashboards`, `column_meta`, `table_meta`, `alembic_version`) are intact

## Group 2 — Backend Code Cleanup

1. Delete model files: `app/models/refund_order.py`, `app/models/service_refund_work_order.py`, `app/models/wallet_withdrawal.py`
2. Remove the three model imports from `app/models/__init__.py`
3. Remove `READ_ONLY_TABLES` frozenset from `app/services/schema_manager.py`
4. Remove the three hardcoded entries from `TABLE_DISPLAY_NAMES` in `app/services/schema_validator.py`
5. Remove `READ_ONLY_TABLES` guard from `app/routers/schema.py::_get_editable_model()`
6. Delete table-specific cleansing rules: `app/services/table_specific/refund_order.py`, `service_refund.py`, `wallet_withdrawal.py`
7. Verify `table_specific/__init__.py` registry still works correctly with an empty registry

## Group 3 — Seed Script & Sample Data Removal

1. Delete `seed.py` entirely
2. Remove the three legacy CSV sample files from the project root (`服务退款工单0601~0721.csv`, `退费单0601~0721.csv`, `钱包提现操作0601~0721.csv`)

## Group 4 — Test Updates

1. Update `tests/test_views.py` — replace `refund_orders` references with a dynamically created test table via Schema Manager fixtures
2. Update `tests/test_visualizations.py` — same replacement
3. Update `tests/test_view_sql_builder.py` — same replacement
4. Update `tests/test_imports.py` — remove legacy-table-specific import tests, keep generic pipeline tests
5. Update `frontend/src/test/SchemaManager.test.tsx` — remove `退费单` / `read_only` assertions tied to legacy tables
6. Add new test: verify that a fresh database starts with zero business tables and the Schema Manager table list is empty

## Group 5 — End-to-End Validation

1. Fresh database: `alembic upgrade head` creates only system tables
2. Schema Manager UI shows zero tables on first launch
3. Create a new table via Schema Manager → upload CSV → data flows through general cleaning pipeline → lands in DB correctly
4. Data Browser, View Builder, Visualization Builder, Dashboard Builder all work with dynamically created tables
5. No import errors or registry warnings on backend startup
