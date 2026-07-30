# Phase 3.5 — Upsert Support for Data Imports: Requirements

## Scope

**Delivered:**
- A generic upsert mechanism in the import pipeline that applies to all three business tables (`refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`) — not table-specific code paths
- Each model declares its business unique key columns used for conflict detection
- On re-upload of a file with matching business keys, existing records are **updated** (all non-key, non-timestamp business columns refreshed) instead of silently discarded
- `imported_at` timestamp is **reset** to current time on each update, reflecting the most recent successful import
- `rows_inserted`, `rows_updated`, `rows_skipped` are tracked as new columns on `ImportJob` and returned in the API response
- Existing `rows_imported` field is preserved as total rows affected (`inserted + updated`) for backward compatibility

**Explicitly out of scope:**
- Upsert on tables other than the three business tables
- Audit trail of old vs new values on update (no history table)
- Partial update — if any conflict row fails, the entire batch uses savepoints as before
- UI changes (Phase 4 handles frontend display)

## Context (from mission.md)

YKMMgmt ingests business data from external sources into a unified view. Phase 3 delivered the import engine, but it silently discards re-uploaded records via `on_conflict_do_nothing()`. Phase 3.5 closes this gap by making re-uploads idempotent and data-refreshing — critical for the operational workflow where source files are periodically re-exported and re-ingested with updated values. Every subsequent dashboard phase (5-7) benefits from having fresh data rather than stale first-import snapshots.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Upsert scope | All 3 business tables, generic mechanism | Avoids code duplication across tables. A single, model-driven mechanism is easier to maintain and extend to future tables. |
| Business key identification | Model-driven — each model declares its conflict columns (via `unique=True` introspection or explicit `__upsert_key__`) | Keeps the upsert logic generic while letting each model control its own identity. Already works for `RefundOrder` (`refund_order_no`) and `ServiceRefundWorkOrder` (`work_order_no`) which have `unique=True`. |
| WalletWithdrawal key | Composite unique constraint on `(account_id, sn, operated_at)` | This table has no natural single-column key. The combination of account, device, and operation time uniquely identifies a withdrawal record. Added via Alembic migration. |
| `imported_at` on update | Reset to `func.now()` | The user chose fresh timestamps. This reflects when the row was last seen/imported, which is more useful for auditing data freshness than preserving a first-seen timestamp. |
| Upsert stats storage | New columns on existing `ImportJob` model | Chosen by user. Keeps stats colocated with the job they describe. No new model needed. |
| `rows_imported` backward compatibility | Preserved as `inserted + updated` | Existing API consumers (e.g., Phase 4 upload UI) can continue using `rows_imported` without changes. |
| Columns updated on conflict | All non-key, non-timestamp business columns (exclude: `id`, `imported_at`, `created_at`, `record_created_at`, `record_updated_at`) | Timestamps have specific semantics that shouldn't be overwritten by incoming data. Business columns should always reflect the latest source data. |

## Constraints

- **Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16+. Uses PostgreSQL's native `ON CONFLICT ... DO UPDATE` (no ORM-level merge).
- **Database:** Requires a new Alembic migration to add `WalletWithdrawal` unique constraint and `ImportJob` upsert stat columns. Existing data must survive the migration.
- **API design:** Response schema expands but is backward-compatible — only new fields are added, no existing fields removed or renamed.
- **Existing tests:** All Phase 3 tests must continue to pass. The behavior change from `on_conflict_do_nothing` to `on_conflict_do_update` means some test expectations may need updating (re-upload now updates instead of discarding).
- **Data integrity:** The `unique=True` constraints on `refund_order_no` and `work_order_no` are relied upon. The new composite constraint on `wallet_withdrawals` must be validated against existing data before migration can succeed (no duplicate `(account_id, sn, operated_at)` triples must exist).

## Out of Scope

- History/audit trail of old values on update
- Configurable upsert behavior per table (always update all non-key columns)
- Partial column update (e.g., only update if new value differs)
- Upsert for any future tables beyond the current three
- Frontend display of upsert stats (Phase 4 will consume these new fields)
