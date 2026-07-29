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

```bash
# Import a CSV file (Chinese headers are auto-matched to database columns)
curl -X POST http://localhost:8000/api/imports \
  -F "file=@服务退款工单0601~0721.csv" \
  -F "target_table=service_refund_work_orders"

# List available target tables (supports Chinese or English names)
curl http://localhost:8000/api/imports/tables
```

**Supported target tables:** 退费单 (`refund_orders`), 服务退款工单 (`service_refund_work_orders`), 钱包提现操作 (`wallet_withdrawals`).

The response includes import status, row counts, a cleaning report (steps, warnings), and any errors.

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

# Management App for YKM

## Input from stakeholders

- The management team wants a light-weight system to use in their daily work, making it easier to decision making based on data.
- This application is for Chinese users.
