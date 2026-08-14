# YKMMgmt

Internal business tool for financial and operational data management — unify business data, automate imports, and surface KPIs through an interactive dashboard.

## Prerequisites

- **Python 3.12+** (conda environment `ykmmgmt` recommended)
- **Node.js 20+**
- **npm 10+**
- **Docker & Docker Compose** (for PostgreSQL)

## Quick Start

### 1. Database (PostgreSQL)

```bash
# Start PostgreSQL 16 in a Docker container
docker compose up -d

# Verify it's running
docker compose ps
```

### 2. Backend

```bash
cd ykmmgmt/backend

# Activate conda env (if using conda)
conda activate ykmmgmt

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# (Optional) Seed sample data
python seed.py

# Start dev server
uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000** with auto-generated docs at `/docs`.

### 3. Frontend

```bash
cd ykmmgmt/frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend runs at **http://localhost:5173** and proxies `/api/*` to the backend.

### 4. Verify

```bash
curl http://localhost:8000/api/health     # → {"status":"ok"}
curl http://localhost:8000/api/health/db  # → {"status":"ok","database":"connected"}
curl http://localhost:5173/api/health     # → {"status":"ok"} (via proxy)
```

Open **http://localhost:5173** in a browser — you should see the backend health status.

## Database

- **Migrations:** Run `alembic upgrade head` to apply all migrations. Generate new ones with `alembic revision --autogenerate -m "description"`.
- **Seed data:** `python seed.py` loads the first 20 rows from each sample CSV file.
- **Environment:** Copy `.env.example` to `.env` and adjust `DATABASE_URL` as needed.

## Import API

Upload CSV or Excel (`.csv`, `.xlsx`) files to import data into the system.

### Quick Examples

**Import a CSV file** (Chinese headers are auto-matched to database columns):

```bash
# 服务退款工单 (Service Refund Work Orders)
curl -X POST http://localhost:8000/api/imports \
  -F "file=@服务退款工单0601~0721.csv" \
  -F "target_table=service_refund_work_orders"

# 退费单 (Refund Orders)
curl -X POST http://localhost:8000/api/imports \
  -F "file=@退费单0601~0721.csv" \
  -F "target_table=refund_orders"

# 钱包提现操作 (Wallet Withdrawals)
curl -X POST http://localhost:8000/api/imports \
  -F "file=@钱包提现操作0601~0721.csv" \
  -F "target_table=wallet_withdrawals"
```

**Import an Excel (.xlsx) file** — same endpoint, same behavior:

```bash
curl -X POST http://localhost:8000/api/imports \
  -F "file=@data.xlsx" \
  -F "target_table=service_refund_work_orders"
```

### Response Shape

```json
{
  "status": "completed",
  "target_table": "服务退款工单",
  "rows_imported": 1450,
  "rows_rejected": 0,
  "rows_inserted": 0,
  "rows_updated": 1450,
  "rows_skipped": 0,
  "import_job_id": 42,
  "cleaning_report": {
    "rows_before": 1450,
    "rows_after": 1450,
    "steps": [
      { "step": "strip_whitespace", "rows_modified": 0, "rows_dropped": 0 },
      { "step": "handle_missing_values", "rows_dropped": 0 },
      { "step": "normalize_formats", "rows_modified": 0 },
      { "step": "deduplicate_rows", "rows_dropped": 0 },
      { "step": "validate_values", "rows_dropped": 0 },
      { "step": "table_specific_cleaning", "rows_dropped": 0 }
    ],
    "warnings_per_column": {}
  }
}
```

- `rows_imported` = `rows_inserted` + `rows_updated` (backward-compatible total)
- `rows_inserted` — new records created
- `rows_updated` — existing records refreshed (upsert via business keys)
- `rows_skipped` — duplicates silently ignored (hash-based dedup for WalletWithdrawal)
- `rows_rejected` — rows that failed validation

### Upsert Behavior

Re-uploading the same file will **update** existing records instead of creating duplicates, based on business unique keys:

| Table | Chinese Name | Conflict Key |
|-------|-------------|-------------|
| `refund_orders` | 退费单 | `refund_order_no` (退费单号) |
| `service_refund_work_orders` | 服务退款工单 | `work_order_no` (工单号) |
| `wallet_withdrawals` | 钱包提现操作 | `content_hash` (SHA-256 hash of all columns) |

**WalletWithdrawal** has no natural business key, so duplicates are detected via a SHA-256 hash of all imported columns — identical rows are silently skipped.

### List Available Tables

```bash
curl http://localhost:8000/api/imports/tables
```

Returns English table names and their Chinese labels.

## Schema Manager（数据库管理）

Manage the database schema directly in the app — no hand-written models or migrations.

- **Inspect** every table (`/schema`): columns, types, Chinese labels, descriptions, default values, sample rows.
- **Create tables** manually or by uploading a CSV — column types and Chinese labels are inferred for review before creation. Columns support primary keys, foreign keys (picked via table/column dropdowns), descriptions, and default values. New tables no longer carry the `content_hash` bookkeeping column.
- **Edit tables**: add/drop columns, and per column change its name, Chinese label, type, nullability, unique constraint, description, default value, and foreign key (with data-loss warnings).
- **Delete tables** with a dependency warning for views/visualizations that reference them.
- **Imports match headers two ways**: a file header equal to a column's 中文标签 *or* its real column name maps to that column, so both Chinese-labeled files and production-style Chinese column names work.
- Every change **generates and applies an Alembic migration automatically**, and new tables appear in the Data Browser / View Builder immediately — no server restart.
- Runtime-generated migrations are written to `ykmmgmt/runtime_migrations/` (outside the backend tree) so `uvicorn --reload` never restarts mid-request; both version directories are wired up in `alembic.ini`.
- The three pre-existing business tables (`refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`) are **inspection-only** and protected from edits.

```bash
curl http://localhost:8000/api/schema/tables          # all tables + read-only flags
curl http://localhost:8000/api/schema/column-types    # supported column types
curl http://localhost:8000/api/schema/fk-options      # FK targets (tables + PK/unique columns)
curl -X POST http://localhost:8000/api/schema/infer-from-csv -F "file=@sample.csv"
```

## Project Structure

```
ykmmgmt/
├── backend/              # FastAPI application
│   ├── app/
│   │   ├── core/         # Config, database engine, sessions
│   │   └── models/       # SQLAlchemy models (5 tables)
│   ├── alembic/          # Database migrations
│   ├── tests/
│   ├── main.py           # App entry point
│   ├── seed.py           # Seed script
│   ├── requirements.txt
│   └── ruff.toml
├── frontend/             # React + Vite + TypeScript
│   ├── src/
│   │   ├── App.tsx       # Health check page
│   │   ├── main.tsx      # React entry point
│   │   └── lib/          # Utility functions
│   ├── vite.config.ts
│   └── package.json
├── specs/                # Project specifications & roadmap
├── docker-compose.yml    # PostgreSQL container
├── .env                  # Environment variables (git-ignored)
├── .env.example          # Environment template
└── .gitignore
```
