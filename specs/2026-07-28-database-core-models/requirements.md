# Phase 2 — Database & Core Models: Requirements

## Scope

**Delivered:**
- Docker Compose PostgreSQL 16 instance running locally
- Async SQLAlchemy 2.0 engine + session factory with FastAPI dependency injection
- Alembic configured for async migrations
- `DataSource` model — tracks each data source (CSV file) with name, type, config JSON, and optional schedule
- `ImportJob` model — tracks import runs with status, timing, row/error counts
- Three business data tables derived 1:1 from the sample CSV files:
  - `service_refund_work_orders` (from `服务退款工单0601~0721.csv`, ~16,768 rows)
  - `refund_orders` (from `退费单0601~0721.csv`, ~36,703 rows)
  - `wallet_withdrawals` (from `钱包提现操作0601~0721.csv`, ~7,561 rows)
- Every column has an English name with a Chinese `comment=` describing the original CSV header
- Seed script that loads the first 20 rows of each CSV as cold-start data
- `GET /api/health/db` endpoint confirming database connectivity
- Updated README with PostgreSQL setup, migration, and seed instructions

**Explicitly out of scope:**
- The Excel file (`各商户号退款数据明细表.xlsx`) — skipped per user decision
- Any import/upload endpoint (Phase 3)
- Data cleaning pipeline (Phase 3)
- Dashboard API or UI (Phase 4–6)

## Context (from mission.md)

This phase lays the data foundation for YKMMgmt's core purpose: unifying scattered business data into one consistent view. The three CSV files represent real refund and withdrawal operations — the kinds of records that finance and operations teams currently sift through manually. Getting them into a queryable PostgreSQL database is the first step toward replacing those manual workflows with an automated dashboard.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database engine | PostgreSQL 16 via Docker Compose | Per tech-stack.md; JSON support for flexible config, strong ecosystem |
| Async driver | asyncpg | Fastest PostgreSQL driver for Python, native async, recommended for SQLAlchemy 2.0 |
| Table mapping strategy | 1:1 file-to-table (denormalized) | Matches user's Scope answer; simple, verifiable, mirrors source files exactly. Normalization can happen in later phases if needed. |
| Column naming | English names with Chinese `comment=` | Matches user's Context answer; schema is developer-friendly while preserving original Chinese field semantics |
| Config management | `.env` + Pydantic Settings | Per tech-stack.md; standard FastAPI pattern, keeps secrets out of source control |
| Seed scope | First 20 rows per file | Enough to verify schema correctness and enable frontend development without loading the full dataset |
| Timestamp strategy | `created_at`/`updated_at` on models, `imported_at` on data tables | Separates system audit timestamps from source data timestamps |

## Constraints

- **CSV parsing quirks:** The sample CSVs use non-standard delimiters (tabs mixed with commas) and may have encoding issues. The seed script must handle this robustly.
- **Duplicate column name:** `服务退款工单0601~0721.csv` has two `备注` columns with different meanings — column 10 is customer-provided (`customer_remark`), column 26 is internal/staff notes (`internal_remark`).
- **Chinese text throughout:** All data values are Chinese; UTF-8 must be used at every layer (DB, connection, file I/O).
- **No conda assumption for Docker commands:** Docker must be installed and available on the host. Conda environment is only used for Python execution.
- **Async-first:** All database access uses async sessions. Blocking synchronous calls (e.g., Pandas `read_csv`) are confined to the seed script, not the API runtime.

## Out of Scope

- The Excel merchant refund detail file — skipped per user decision
- Data cleaning, validation, or transformation logic (Phase 3)
- File upload or import API endpoints (Phase 3)
- Any frontend changes
- Scheduled imports (Phase 8)
- Auth or multi-user (Phase 9)
