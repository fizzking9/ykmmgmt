# Phase 3.5 — Upsert Support for Data Imports: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Declare Business Unique Keys Per Model ✅

1. ✅ For each business model (`RefundOrder`, `ServiceRefundWorkOrder`, `WalletWithdrawal`), identify or create the business unique key columns used for conflict detection
2. ✅ Define a convention for models to expose their upsert conflict targets — via a class-level `__upsert_key__` attribute (empty list = insert-only with hash dedup)
3. ✅ For `WalletWithdrawal` which has no natural unique key: added `content_hash` column (SHA-256 of all business columns) with unique constraint `uq_wallet_withdrawal_content_hash` — insert-only dedup via `on_conflict_do_nothing(constraint=...)`
4. ✅ Built `_compute_content_hash()` utility and `_count_existing_hashes()` for accurate stats in insert-only mode

---

## Group 2 — Replace on_conflict_do_nothing with on_conflict_do_update ✅

1. ✅ In `ImportService._insert_rows()`, replaced `on_conflict_do_nothing()` with `on_conflict_do_update()` targeting each model's business unique key columns (RefundOrder, ServiceRefundWorkOrder). WalletWithdrawal stays insert-only with hash-targeted `on_conflict_do_nothing(constraint="uq_wallet_withdrawal_content_hash")`
2. ✅ On conflict, update all non-key, non-timestamp columns (`imported_at`, `created_at`, `record_created_at`, `record_updated_at`) with values from the new row — this means all business data columns get refreshed
3. ✅ Reset `imported_at` to `func.now()` on each update so the timestamp always reflects the most recent successful import of that row
4. ✅ Preserve `created_at` from the original record (the ImportJob-level timestamp) — do not touch it on upsert

---

## Group 3 — Track Upsert Statistics in ImportJob ✅

1. ✅ Added three new columns to the `ImportJob` model: `rows_inserted` (Integer, default 0), `rows_updated` (Integer, default 0), `rows_skipped` (Integer, default 0)
2. ✅ Created and ran Alembic migration to add these columns to the `import_jobs` table
3. ✅ Updated `ImportService._insert_rows()` to track and return separate counts: inserted, updated, skipped
4. ✅ Updated `_finish_import_job()` to populate these new columns on the ImportJob record
5. ✅ Return upsert breakdown in the API response: `{ rows_inserted, rows_updated, rows_skipped }`

---

## Group 4 — API Response & Report Updates ✅

1. ✅ Updated the `POST /api/imports` response schema to include `rows_inserted`, `rows_updated`, `rows_skipped` alongside the existing `rows_imported` and `rows_rejected` fields
2. ✅ Ensured backward compatibility: keep existing `rows_imported` as the total affected (`inserted + updated`), and add the breakdown fields
3. ✅ Updated the cleaning report or response to clearly distinguish inserted vs updated rows

---

## Group 5 — Tests ✅

1. ✅ Test upsert insert path: `test_service_refund_upsert_insert` — `rows_inserted` matches file row count, `rows_updated = 0`
2. ✅ Test upsert update path: `test_service_refund_upsert_update` — non-key column values refreshed, `imported_at` reset
3. ✅ Test business key preservation: `test_refund_order_upsert_preserves_key` — business unique key values remain unchanged
4. ✅ Test mixed insert+update: `test_refund_order_mixed_upsert` — correct `rows_inserted` and `rows_updated` counts
5. ✅ Test all three target tables: refund_orders (upsert via refund_order_no), service_refund_work_orders (upsert via work_order_no), wallet_withdrawals (hash dedup via content_hash)
6. ✅ Test upsert stats in ImportJob: all integration tests verify `rows_inserted`, `rows_updated`, `rows_skipped` in DB — 34/34 tests pass
