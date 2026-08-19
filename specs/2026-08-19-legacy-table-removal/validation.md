# Phase 11 — Legacy Business Table Removal & System Reset: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Migration Applies Cleanly

```bash
cd ykmmgmt/backend
python -m alembic upgrade head
```

**Expected:** Migration completes without errors. `alembic current` shows the new head revision.

**Status: PASS (2026-08-19)** — `b7d3e9a14f25` applies cleanly on the dev database and on a brand-new database (full chain `a97bfa4a5039 → b7d3e9a14f25`); `alembic_version` at `b7d3e9a14f25`.

---

## Gate 2 — Legacy Tables Are Gone

```bash
cd ykmmgmt/backend
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name\"))
        tables = [r[0] for r in result]
        print('Tables:', tables)
        assert 'refund_orders' not in tables
        assert 'service_refund_work_orders' not in tables
        assert 'wallet_withdrawals' not in tables
        print('OK: legacy tables absent')

asyncio.run(check())
"
```

**Expected:** `OK: legacy tables absent` printed. Only system tables remain.

**Status: PASS (2026-08-19)** — `information_schema.tables` after upgrade: alembic_version, column_meta, dashboards, datasources, import_jobs, table_meta, views, visualizations (plus user-created dynamic tables on the dev DB). No refund_orders / service_refund_work_orders / wallet_withdrawals.

---

## Gate 3 — No Orphaned Dependent Objects

```bash
cd ykmmgmt/backend
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        # Check views
        r = await conn.execute(text(\"SELECT COUNT(*) FROM views WHERE generated_sql ~ 'refund_orders|service_refund_work_orders|wallet_withdrawals'\"))
        assert r.scalar() == 0, 'orphaned views found'
        # Check visualizations (via view join)
        r = await conn.execute(text(\"SELECT COUNT(*) FROM visualizations v JOIN views vw ON v.view_id = vw.id WHERE vw.generated_sql ~ 'refund_orders|service_refund_work_orders|wallet_withdrawals'\"))
        assert r.scalar() == 0, 'orphaned visualizations found'
        # Check dashboards
        r = await conn.execute(text(\"SELECT COUNT(*) FROM dashboards WHERE layout_json::text ~ 'refund_orders|service_refund_work_orders|wallet_withdrawals'\"))
        assert r.scalar() == 0, 'orphaned dashboards found'
        print('OK: no orphaned dependent objects')

asyncio.run(check())
"
```

**Expected:** `OK: no orphaned dependent objects` printed.

**Status: PASS (2026-08-19)** — counts after migration: views 0, visualizations 0, dashboards 0; no rows reference any legacy table name in generated_sql / config_json / layout_json.

---

## Gate 4 — Backend Starts Without Errors

```bash
cd ykmmgmt/backend
python -c "
from app.main import app
print('OK: app imports cleanly')
"
```

**Expected:** `OK: app imports cleanly` printed. No `ImportError`, `AttributeError`, or registry warnings.

**Status: PASS (2026-08-19)** — `import main` succeeds; `table_specific.get_rules(...)` returns `[]` (empty registry functional); uvicorn startup log clean, no registry warnings.

---

## Gate 5 — Schema Manager Shows Zero Tables

```bash
cd ykmmgmt/backend
python -c "
import asyncio
from app.core.database import async_session_factory
from app.services.schema_manager import list_tables_info

async def check():
    async with async_session_factory() as db:
        tables = await list_tables_info(db)
        print('Tables:', tables)
        assert len(tables) == 0, f'expected 0 tables, got {len(tables)}'
        print('OK: zero business tables')

asyncio.run(check())
"
```

**Expected:** `OK: zero business tables` printed.

**Status: PASS (2026-08-19)** — on a freshly migrated database, `GET /api/schema/tables` returns `[]` and `GET /api/tables` returns `[]`. New regression test `test_system_starts_with_zero_builtin_business_tables` asserts no built-in models/registrations.

---

## Gate 6 — Backend Tests Pass

```bash
cd ykmmgmt/backend
python -m pytest tests/ -v --tb=short
```

**Expected:** All tests pass. No failures related to missing legacy tables or models.

**Status: PASS (2026-08-19)** — 139 backend tests pass (run twice for stability), ruff clean. All view/visualization/dashboard/data-browser tests now run against dynamically created fixture tables via the real Schema Manager + import APIs.

---

## Gate 7 — Frontend Tests Pass

```bash
cd ykmmgmt/frontend
npm run test -- --run
```

**Expected:** All Vitest tests pass. No failures related to `退费单` or `read_only` legacy assertions.

**Status: PASS (2026-08-19)** — 65 frontend tests pass, `tsc --noEmit` clean; legacy `退费单` fixture and read-only assertions removed from SchemaManager.test.tsx.

---

## Gate 8 — End-to-End Dynamic Table Flow

Manual verification:

1. Start backend and frontend
2. Open Schema Manager → confirm zero tables shown
3. Create a new table manually (e.g., `test_products` with columns: `name` String, `price` Numeric)
4. Upload a CSV file matching the new table schema
5. Confirm import succeeds with cleaning report
6. Open Data Browser → confirm new table appears and data is browsable
7. Create a view on the new table → confirm SQL generation works
8. Create a visualization on the view → confirm chart renders
9. Create a dashboard with the visualization → confirm dashboard displays

**Expected:** Full flow works without errors. No references to legacy tables anywhere in the UI.

**Status: PASS (2026-08-19)** — full in-browser walkthrough on a fresh database: zero tables on first launch → manual create `test_products` → CSV upload (3 新增, cleaning report) → Data Browser rows → View Builder preview + save → bar-chart visualization → dashboard tile rendering. No console errors, no legacy references. Screenshots in `.qoder/verify_step*.png`.

---

## Merge Checklist

- [x] All 8 gates pass on a clean checkout
- [x] Alembic migration applies and rolls back cleanly (`alembic downgrade -1` then `alembic upgrade head`)
- [x] No legacy table names found in codebase (`grep -r "refund_orders\|service_refund_work_orders\|wallet_withdrawals" ykmmgmt/`)
- [x] No legacy model files remain (`ls ykmmgmt/backend/app/models/refund_order.py ykmmgmt/backend/app/models/service_refund_work_order.py ykmmgmt/backend/app/models/wallet_withdrawal.py` → file not found)
- [x] No table-specific rule files remain (`ls ykmmgmt/backend/app/services/table_specific/refund_order.py ykmmgmt/backend/app/services/table_specific/service_refund.py ykmmgmt/backend/app/services/table_specific/wallet_withdrawal.py` → file not found)
- [x] `seed.py` deleted
- [x] Legacy CSV files removed from project root
- [x] All tests pass (backend + frontend)
- [x] Fresh database starts with zero business tables
