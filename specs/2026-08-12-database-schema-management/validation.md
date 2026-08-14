# Phase 10 — Database Schema Management: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — README & docs

Confirm the README documents the new Schema Manager feature and any new setup steps (none expected beyond existing env).

```powershell
Get-Content README.md | Select-String -Pattern "Schema" -SimpleMatch
```

**Expected:** At least one mention of the Schema Manager / database schema management capability.

---

## Gate 2 — Formatting

Backend (Ruff format check) and frontend (Prettier check) must be clean.

```powershell
cd ykmmgmt/backend; ruff format --check .; cd ../../ykmmgmt/frontend; npx prettier --check "src/**/*.{ts,tsx}"
```

**Expected:** Ruff reports no files would be reformatted; Prettier reports "All matched files use Prettier code style!".

---

## Gate 3 — Linting

Backend (Ruff) and frontend (ESLint) must pass with no errors.

```powershell
cd ykmmgmt/backend; ruff check .; cd ../../ykmmgmt/frontend; npx eslint "src/**/*.{ts,tsx}"
```

**Expected:** Ruff exits 0 with no findings; ESLint exits 0 with no errors (warnings acceptable only if pre-existing).

---

## Gate 4 — Dead code

No unused imports, no commented-out blocks, no leftover `console.log`/`print` debug statements in new Schema Manager code.

```powershell
cd ykmmgmt/backend; ruff check --select F401,F841 .; cd ../../ykmmgmt/frontend; npx eslint "src/**/*.{ts,tsx}" --rule '{"no-console":"error"}'
```

**Expected:** No unused-import (F401) or unused-variable (F841) findings; no `no-console` errors in new files.

---

## Gate 5 — Backend tests

All backend tests pass, including the new Schema Manager tests.

```powershell
cd ykmmgmt/backend; python -m pytest -q
```

**Expected:** All tests pass (exit 0); new tests cover schema inspection, column-type listing, manual create, CSV inference, add/drop/modify column, delete table, read-only guard on business tables, and runtime registry visibility. CSV inference and the end-to-end create flow are exercised against a real sample CSV file written to `tmp_path` (Chinese headers, mixed text/integer/decimal/date columns), plus a second edge-case CSV (blank rows, whitespace in headers, an all-null column).

---

## Gate 6 — Frontend tests

All frontend tests pass, including the new Schema Manager component tests.

```powershell
cd ykmmgmt/frontend; npx vitest run
```

**Expected:** All Vitest suites pass (exit 0); new tests cover the table list, create wizard (manual + CSV paths), edit dialog, and delete confirmation with dependency warning.

---

## Gate 7 — Phase-specific: schema inspection & type system

Verify the inspection and column-type endpoints return real data.

```powershell
curl http://localhost:8000/api/schema/tables
curl http://localhost:8000/api/schema/column-types
```

**Expected:** `/tables` returns all tables with English + Chinese names, column/row counts, and `read_only: true` on `refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`. `/column-types` returns the supported type list (String, Text, Integer, BigInteger, Numeric, Boolean, DateTime, Date, JSON).

---

## Gate 8 — Phase-specific: create table (manual) + runtime registry

Create a table via the API and confirm it is immediately visible without restart.

```powershell
curl -X POST http://localhost:8000/api/schema/tables -H "Content-Type: application/json" -d '{"name":"test_phase10","display_name":"测试表","columns":[{"name":"title","type":"String","length":200,"nullable":false,"label":"标题"}]}'
curl http://localhost:8000/api/tables
```

**Expected:** Create returns 200/201; `/api/tables` (Data Browser source) now lists `test_phase10` / `测试表` with no server restart. An Alembic migration file for the new table exists under `runtime_migrations/` (kept outside the backend tree so `uvicorn --reload` does not restart mid-request; wired into Alembic via `version_locations`).

---

## Gate 9 — Phase-specific: CSV inference from a sample file

Create a real sample CSV with Chinese headers and mixed-type columns, then confirm schema inference returns a proposed schema without creating a table.

```powershell
@'
订单号,金额,下单日期,备注
A001,199.50,2026-08-01,首单
A002,250.00,2026-08-02,
A003,99.99,2026-08-03,加急
'@ | Out-File -Encoding utf8 sample_phase10.csv
curl -X POST http://localhost:8000/api/schema/infer-from-csv -F "file=@sample_phase10.csv"
```

**Expected:** Returns a proposed schema with four columns; `金额` inferred as Numeric, `下单日期` as Date/DateTime, `订单号`/`备注` as String/Text; Chinese labels suggested from the headers; no new table is created.

---

## Gate 10 — Phase-specific: edit, delete & read-only guard

Verify add/drop/modify column and delete table work on a new table, and that business tables are protected.

```powershell
curl -X POST http://localhost:8000/api/schema/tables/test_phase10/columns -H "Content-Type: application/json" -d '{"name":"amount","type":"Numeric","nullable":true,"label":"金额"}'
curl -X DELETE http://localhost:8000/api/schema/tables/test_phase10
curl -X DELETE http://localhost:8000/api/schema/tables/refund_orders
```

**Expected:** Add-column succeeds; delete of `test_phase10` succeeds and removes it from the registry; delete of `refund_orders` returns 403 with a read-only message. Each operation generated a migration.

---

## Gate 11 — Phase-specific: full-lifecycle integration test

Run the dedicated lifecycle test module that walks a new table through create → upload → integrate → edit → re-upload → features-respond → delete using real sample CSV files.

```powershell
cd ykmmgmt/backend; python -m pytest tests/test_schema_lifecycle.py -q
```

**Expected:** The module passes (exit 0) and asserts, in order: (1) `lifecycle_v1.csv` inferred + table created with a migration; (2) `lifecycle_v1.csv` imported via `POST /api/imports` with rows landed; (3) table visible in `GET /api/tables`, schema served, a data view built and executed, a visualization created; (4) add-column + modify-type generate migrations and update the registry; (5) `lifecycle_v2.csv` (with the new column) imported and the new column populated; (6) Data Browser shows the new column and the view/visualization reflect the change; (7) delete removes the table from the registry, flags dependents, and generates a drop migration.

---

## Merge Checklist

- [x] All 11 gates pass on a clean checkout
- [x] Schema inspection lists all tables with correct read-only flags on the 3 business tables
- [x] Column-type endpoint drives the frontend type picker
- [x] Manual table creation generates + applies an Alembic migration and registers the table at runtime (no restart)
- [x] CSV inference returns a reviewable proposed schema without creating a table
- [x] CSV inference + end-to-end create flow are tested against a real sample CSV file (Chinese headers, mixed types) plus an edge-case CSV
- [x] Add/drop/modify column each generate + apply a migration and refresh the registry
- [x] Deleting a table warns about dependent views/visualizations
- [x] The 3 business tables cannot be edited or deleted (403)
- [x] New table appears in Data Browser / View Builder immediately
- [x] All Schema Manager UI text is in Chinese
- [x] Full-lifecycle integration test (`test_schema_lifecycle.py`) passes: create → upload → integrate (Data Browser/View Builder/Visualization) → edit → re-upload → features respond → delete
- [x] Backend and frontend test suites pass
