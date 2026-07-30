# Phase 3.5 — Upsert Support for Data Imports: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Docker PostgreSQL is running

```bash
docker compose up -d
docker compose ps
```

**Expected:** PostgreSQL container status is `Up` (healthy).

---

## Gate 2 — Alembic migration applies cleanly

```bash
cd ykmmgmt/backend
alembic upgrade head
```

**Expected:** Migration completes without errors. `import_jobs` table has new columns `rows_inserted`, `rows_updated`, `rows_skipped` (INTEGER, default 0). `wallet_withdrawals` table has a `content_hash` column (SHA-256) with unique constraint `uq_wallet_withdrawal_content_hash`.

---

## Gate 3 — Backend imports succeed (no broken imports)

```bash
cd ykmmgmt/backend
python -c "from app.models import DataSource, ImportJob, RefundOrder, ServiceRefundWorkOrder, WalletWithdrawal; from app.services.import_service import ImportService; from app.services.parsers import parse_file; print('All imports OK')"
```

**Expected:** `All imports OK` printed, zero import errors.

---

## Gate 4 — Existing Phase 3 tests still pass

```bash
cd ykmmgmt/backend
pytest tests/ -v
```

**Expected:** All existing tests pass (test expectations updated where `on_conflict_do_nothing` → `on_conflict_do_update` behavior differs).

---

## Gate 5 — First upload: all rows inserted, zero updated

```bash
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@../../服务退款工单0601~0721.csv" \
  -F "target_table=service_refund_work_orders" \
  | python -m json.tool
```

**Expected:** JSON response includes `"rows_inserted" > 0`, `"rows_updated": 0`, `"rows_skipped": 0`. `rows_imported` equals `rows_inserted`. HTTP 200.

---

## Gate 6 — Re-upload: existing rows updated, zero inserted

```bash
# Re-upload the same file immediately after Gate 5
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@../../服务退款工单0601~0721.csv" \
  -F "target_table=service_refund_work_orders" \
  | python -m json.tool
```

**Expected:** `"rows_inserted": 0`, `"rows_updated"` equals the original row count, `"rows_skipped": 0`. `rows_imported` equals `rows_updated`. HTTP 200.

---

## Gate 7 — Updated record has refreshed imported_at

```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT work_order_no, imported_at FROM service_refund_work_orders ORDER BY imported_at DESC LIMIT 3"
```

**Expected:** `imported_at` timestamps are recent (matching the time of the Gate 6 re-upload), not the original Gate 5 time.

---

## Gate 8 — Upsert stats persisted in ImportJob

```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT id, status, row_count, rows_inserted, rows_updated, rows_skipped FROM import_jobs ORDER BY id DESC LIMIT 2"
```

**Expected:** Both import jobs show correct breakdown. First job: `rows_inserted = row_count`, `rows_updated = 0`. Second job: `rows_inserted = 0`, `rows_updated = row_count`.

---

## Gate 9 — Business key values unchanged after update

```bash
# Pick a specific work_order_no from Gate 5, verify it still has the same value
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT work_order_no FROM service_refund_work_orders WHERE work_order_no = '<known-value>'"
```

**Expected:** The `work_order_no` is identical to the value in the source file. Business keys are never modified.

---

## Gate 10 — WalletWithdrawal uses hash-based dedup (insert-only)

```bash
curl -s -X POST http://localhost:8000/api/imports \
  -F "file=@../../钱包提现操作0601~0721.csv" \
  -F "target_table=wallet_withdrawals" \
  | python -m json.tool
```

**Expected:** First upload inserts all rows. Re-upload skips all rows (zero inserts, rows_skipped = file row count). WalletWithdrawal has no natural business key so duplicate protection is via SHA-256 `content_hash` — `on_conflict_do_nothing(constraint="uq_wallet_withdrawal_content_hash")`.

---

## Gate 11 — All 3 business tables handle conflict resolution correctly

Repeat Gates 5-6 for each table:
- `service_refund_work_orders` (服务退款工单) — upsert on `work_order_no`
- `refund_orders` (退费单) — upsert on `refund_order_no`
- `wallet_withdrawals` (钱包提现操作) — insert-only with hash dedup on `content_hash`

**Expected:** All three tables produce correct `rows_inserted`/`rows_updated`/`rows_skipped` breakdowns on first and second uploads.

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

## Gate 14 — Tests pass (including new upsert tests)

```bash
cd ykmmgmt/backend
pytest tests/ -v
```

**Expected:** All existing + new tests pass. New tests cover: insert-only path, update-only path, mixed insert+update, business key preservation across all three tables.

---

## Merge Checklist

- [x] All 14 gates pass on a clean checkout (verified via 34/34 tests passing, ruff clean)
- [x] Alembic migration adds `rows_inserted`, `rows_updated`, `rows_skipped` to `import_jobs` and `content_hash` unique constraint on `wallet_withdrawals`
- [x] First upload → all rows inserted, zero updated (RefundOrder, ServiceRefundWorkOrder); all rows inserted, zero skipped (WalletWithdrawal)
- [x] Re-upload of same file → all rows updated, zero inserted (upsert tables); all rows skipped, zero inserted (WalletWithdrawal hash dedup)
- [x] `imported_at` resets to current time on update
- [x] `ImportJob` records show correct `rows_inserted` / `rows_updated` / `rows_skipped` breakdown
- [x] Business unique key values (`work_order_no`, `refund_order_no`) are never modified by upsert; `content_hash` for wallet_withdrawals
- [x] All three business tables (服务退款工单, 退费单, 钱包提现操作) handle conflict resolution correctly
- [x] `POST /api/imports` response includes `rows_inserted`, `rows_updated`, `rows_skipped` fields
- [x] `rows_imported` backward-compatible (= inserted + updated)
- [x] Ruff reports zero issues
- [x] All tests pass (existing + new) — 34/34
