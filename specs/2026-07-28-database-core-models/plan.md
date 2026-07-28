# Phase 2 — Database & Core Models: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Docker PostgreSQL Setup

1. Create `docker-compose.yml` at project root with PostgreSQL 16 service (port 5432, persistent volume, env vars for user/password/db name)
2. Create `.env` with `DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/ykmmgmt`
3. Add `.env` to `.gitignore` (if not already present); create `.env.example` with placeholder values
4. Verify container starts: `docker compose up -d` → `docker compose ps` shows healthy

## Group 2 — SQLAlchemy Engine & AsyncSession

1. Install dependencies: `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `python-dotenv`
2. Create `ykmmgmt/backend/app/` package with `__init__.py`
3. Create `ykmmgmt/backend/app/core/` with `config.py` (reads DATABASE_URL from .env via Pydantic Settings)
4. Create `ykmmgmt/backend/app/core/database.py` — async engine, `AsyncSession` factory, `Base` declarative base, `get_db` async generator dependency
5. Wire a health-check variant in `main.py`: `GET /api/health/db` that verifies DB connectivity (returns `{"status": "ok", "database": "connected"}`)

## Group 3 — Alembic Setup & First Migration

1. Run `alembic init alembic` inside `ykmmgmt/backend/`
2. Configure `alembic.ini`: point `sqlalchemy.url` to DATABASE_URL
3. Configure `alembic/env.py`: import `Base.metadata` from `app.core.database`, set `target_metadata`, enable async migrations
4. Generate initial migration: `alembic revision --autogenerate -m "init"` (should produce empty migration — models not imported yet)
5. Run `alembic upgrade head` → confirms migration infrastructure works

## Group 4 — Core Infrastructure Models (DataSource & ImportJob)

1. Create `ykmmgmt/backend/app/models/` package with `__init__.py`
2. Implement `DataSource` model:
   - Fields: `id`, `name`, `source_type` (csv/excel), `config` (JSON), `schedule`, `created_at`, `updated_at`
   - Chinese column comments on every field
3. Implement `ImportJob` model:
   - Fields: `id`, `source_id` (FK → DataSource), `status` (pending/running/completed/failed), `started_at`, `finished_at`, `row_count`, `error_count`, `errors` (JSON), `created_at`
   - Chinese column comments on every field
4. Import models into `env.py` so Alembic detects them
5. Generate and run migration: `alembic revision --autogenerate -m "add_datasource_and_importjob"` → `alembic upgrade head`
6. Verify tables exist: `docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "\dt"` shows `datasources` and `import_jobs`

## Group 5 — Business Data Models (3 CSV-derived tables)

Model each CSV file as a 1:1 database table. Use English column names with Chinese `comment=` on every column. Add `imported_at` timestamp to each table for tracking.

1. **ServiceRefundWorkOrder** (`service_refund_work_orders`) — from `服务退款工单0601~0721.csv`
   - Columns: `work_order_no` (unique), `sn`, `device_type`, `device_type_remark`, `phone`, `service_category`, `service_item`, `priority`, `status`, `customer_remark`, `registered_at`, `activated_at`, `dispatched_at`, `completed_at`, `processing_duration`, `registrar`, `channel`, `processing_node`, `processor`, `processing_opinion`, `is_appeal`, `order_no`, `bank_name`, `bank_card_no`, `recipient`, `internal_remark`, `refund_amount`, `estimated_refundable_amount`, `imported_at`
   - Note: The CSV has two `备注` columns with different meanings — the first (column 10) is customer-provided, mapped to `customer_remark`; the second (column 26) is internal/staff notes, mapped to `internal_remark`
   - Types: strings → `String`/`Text`, datetime strings → `DateTime`, numeric → `Numeric(12,2)`, integer → `Integer`

2. **RefundOrder** (`refund_orders`) — from `退费单0601~0721.csv`
   - Columns: `refund_order_no` (unique), `platform_order_no`, `third_party_order_no`, `device_sn`, `refund_reason`, `plan_name`, `merchant_name`, `refund_amount`, `actual_refund_amount`, `remark`, `status`, `refund_method`, `audit_remark`, `auditor`, `record_created_at`, `record_updated_at`, `operator`, `plan_price`, `imported_at`
   - Note: CSV's `创建时间`/`更新时间` mapped to `record_created_at`/`record_updated_at` to avoid collision with the model's own timestamps

3. **WalletWithdrawal** (`wallet_withdrawals`) — from `钱包提现操作0601~0721.csv`
   - Columns: `account_id`, `wallet_balance`, `sn`, `operation_type`, `operation_amount`, `remark`, `operated_at`, `operator`, `imported_at`

4. Generate and run migration for all three tables
5. Verify: `docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "\dt"` shows all 5 tables

## Group 6 — Seed Script

1. Create `ykmmgmt/backend/seed.py`:
   - Reads the three CSV files from project root using Pandas
   - Handles CSV parsing quirks (tab+comma delimiter, encoding, null representations)
   - Inserts first 20 rows of each file into the corresponding table
   - Uses the async session from `app.core.database`
   - Prints row counts inserted per table
2. Create three `DataSource` records (one per file) as part of the seed
3. Run `python seed.py` → confirms data is loaded
4. Verify: `docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT count(*) FROM service_refund_work_orders"` returns 20

## Group 7 — DB Health Check & Verification

1. Finalize `GET /api/health/db` endpoint:
   - Executes `SELECT 1` against the database
   - Returns `{"status": "ok", "database": "connected", "tables": 5}`
2. Run the dev server and confirm `curl http://localhost:8000/api/health/db` returns success
3. Update `README.md` with:
   - Docker PostgreSQL setup instructions
   - Migration commands (`alembic upgrade head`)
   - Seed script usage
