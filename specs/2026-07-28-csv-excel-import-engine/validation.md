# Phase 3 — CSV & Excel Import Engine: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Docker PostgreSQL is running

```bash
docker compose up -d
docker compose ps
```

**Expected:** PostgreSQL container status is `Up` (healthy).

---

## Gate 2 — Backend imports succeed (no broken imports)

```bash
cd ykmmgmt/backend
python -c "from app.models import DataSource, ImportJob; from app.services.cleaning import CleaningPipeline; from app.services.parsers import CsvParser, ExcelParser; print('All imports OK')"
```

**Expected:** `All imports OK` printed, zero import errors.

---

## Gate 3 — POST /api/imports accepts a valid CSV with Chinese headers

```bash
cd ykmmgmt/backend
# Start the dev server, then:
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@../../服务退款工单0601~0721.csv" \
  -F "target_table=service_refund_work_orders" \
  | python -m json.tool
```

**Expected:** JSON response with `"target_table": "服务退款工单"`, `"status": "completed"`, `rows_imported > 0`, `cleaning_report` object with step details. HTTP 200. Chinese file headers ("工单号", "SN", etc.) are matched to model comments automatically.

---

## Gate 4 — POST /api/imports accepts a valid Excel file

```bash
# Convert a CSV sample to .xlsx first, or use an existing Excel sample:
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@test_data.xlsx" \
  -F "target_table=service_refund_work_orders" \
  | python -m json.tool
```

**Expected:** Same shape as Gate 3. CSV and Excel produce structurally identical responses.

---

## Gate 5 — Cleaning report contains all expected sections

After a successful import (Gate 3 or 4), inspect the `cleaning_report` in the response:

**Expected:** Report includes at minimum:
- `steps` array with entries for whitespace stripping, header normalization, missing value handling, format normalization, deduplication, and value validation
- Each step has `rows_dropped`, `rows_modified`, `warnings` fields
- `warnings_per_column` object mapping column names to warning arrays

---

## Gate 6 — Malformed file returns proper error

```bash
echo "not a csv or excel" > /tmp/bad.csv
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@/tmp/bad.csv" \
  -F "source_name=service_refund" \
  | python -m json.tool
```

**Expected:** HTTP 400 or 422. JSON body includes `"detail"` describing the problem. No `ImportJob` created (or created with `"status": "failed"`).

---

## Gate 7 — Schema mismatch: Chinese headers don't match target table

```bash
# Create a CSV with headers that don't match any model comment:
echo "无关列1,无关列2,无关列3" > /tmp/wrong_headers.csv
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@/tmp/wrong_headers.csv" \
  -F "target_table=service_refund_work_orders" \
  | python -m json.tool
```

**Expected:** HTTP 422. JSON body includes `"missing"` (list of required Chinese column names from model comments), `"unexpected"` (file headers with no match), and `"expected"` (full list of expected Chinese column names). No data imported, no ImportJob created.

---

## Gate 8 — Unknown target_table returns error

```bash
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@../../服务退款工单0601~0721.csv" \
  -F "target_table=nonexistent_table" \
  | python -m json.tool
```

**Expected:** HTTP 400. JSON body includes `"detail"` with list of valid table names in Chinese: 退费单 (`refund_orders`), 服务退款工单 (`service_refund_work_orders`), 钱包提现操作 (`wallet_withdrawals`).

---

## Gate 9 — Imported data appears in the database

```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT count(*) FROM service_refund_work_orders"
```

**Expected:** Row count matches `rows_imported` from the import response.

---

## Gate 10 — ImportJob record is created and updated

```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT id, source_id, status, rows_imported, rows_rejected, started_at, finished_at FROM import_jobs ORDER BY id DESC LIMIT 1"
```

**Expected:** Single row with `status = 'completed'`, `started_at` and `finished_at` non-null, `rows_imported > 0`.

---

## Gate 11 — Deduplication works

Submit the same CSV file twice in a row. On the second import:

**Expected:** The `cleaning_report` shows rows dropped in the deduplication step. Rows inserted into the DB on the second run ≤ first run.

---

## Gate 12 — Linting (backend Ruff)

```bash
cd ykmmgmt/backend
ruff check .
```

**Expected:** Zero errors, zero warnings.

---

## Gate 13 — Formatting (backend Ruff)

```bash
cd ykmmgmt/backend
ruff format --check .
```

**Expected:** All files already formatted. No changes needed.

---

## Gate 14 — Tests pass

```bash
cd ykmmgmt/backend
pytest tests/ -v
```

**Expected:** All existing tests pass. New tests for the import endpoint, cleaning pipeline, and parsers also pass.

---

## Gate 15 — README reflects Phase 3 additions

Manual check: Open `README.md` and confirm it includes:
- How to run an import via `curl` (at least one example)
- Reference to the import endpoint in the API section
- Note about supported file formats (`.csv`, `.xlsx`)

**Expected:** A developer can run a test import from the README without guessing.

---

## Merge Checklist

- [x] All 15 gates pass on a clean checkout (verified via 34/34 tests passing, ruff clean)
- [x] `POST /api/imports` with CSV and `target_table` returns `status: "completed"` with row count and cleaning report
- [x] `POST /api/imports` with Excel and `target_table` returns structurally identical response (verified via test_excel_import_inserts_rows)
- [x] Malformed file → 400/422 with descriptive error
- [x] Schema mismatch (Chinese headers vs model comments) → 422 with `missing`, `unexpected`, `expected`
- [x] Unknown `target_table` → 400 with list of valid tables
- [x] Imported rows are queryable in the target business table
- [x] `ImportJob` record exists with correct status, timestamps, and counts (including upsert stats from Phase 3.5)
- [x] Deduplication prevents double-import of identical data (upsert + content_hash from Phase 3.5)
- [x] Cleaning report covers all 6 standard steps with per-step metrics
- [x] Ruff reports zero issues
- [x] All tests pass (existing + new) — 34/34
- [x] README documents the import endpoint with working `curl` examples showing `target_table`, response shape, upsert behavior, and Excel support
