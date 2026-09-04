# YKMMgmt

Internal business tool for financial and operational data management — unify business data, automate imports, and surface KPIs through an interactive dashboard.

## Architecture

The full stack runs in Docker on the local machine. An Alibaba Cloud server acts as a stateless public entry point, reverse-proxying traffic through an frp tunnel back to the local machine.

```
Browser ──HTTP──> Alibaba Cloud ECS (public entry)
                    │ Nginx :80  ──> frp tunnel ──┐
                    │ frps :7000                   │
                    ▼                              │
                 Local machine (Docker Compose) ◄──┘
                    │ frontend  (Nginx: SPA + /api proxy, host port 8080)
                    │ backend   (FastAPI + uvicorn)
                    │ db        (PostgreSQL 16)
                    └ frpc      (tunnel client, part of the compose stack)
```

Releases: GitHub Actions runs lint + tests on every push to `main`, builds both Docker images, and pushes them to the GitHub Container Registry (GHCR). The local machine pulls the new images with `scripts\deploy.ps1`. The cloud server is configured once and never changes with app releases — see [deploy/README.md](deploy/README.md).

## Developer Quick Start

### Prerequisites

- **Python 3.12+** (conda environment `ykmmgmt` recommended)
- **Node.js 20+**
- **npm 10+**
- **Docker & Docker Compose** (Docker Desktop on Windows)

### 1. Database (PostgreSQL)

**One-shot startup:** `.\scripts\dev.ps1` starts everything below in one go
(db + backend + frontend + MCP server, in the background, logs in
`logs\dev\`). Stop with `.\scripts\dev.ps1 -Stop`. The manual steps:

```bash
# Start PostgreSQL 16 in a Docker container (host port 15432)
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

# Seed the initial root (super admin) account — idempotent, safe to re-run
python -m scripts.seed_root

# Start dev server
uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000** with auto-generated docs at `/docs`.

> **Auth required:** all API endpoints (except `/api/health`) require a logged-in session — see [Authentication & User Management](#authentication--user-management).

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

Open **http://localhost:5173** in a browser and log in with the root account.

## Production Deployment

Everything below happens on the local machine. One-time cloud setup is documented separately in [deploy/README.md](deploy/README.md).

### 1. One-time setup

```powershell
# Create the production environment file (git-ignored) and fill it in
copy deploy\.env.prod.example deploy\.env.prod

# Create the frp tunnel config (git-ignored) — see deploy/README.md
copy deploy\frpc.toml.example deploy\frpc.toml

# Authenticate to GHCR with a PAT that has read:packages scope
docker login ghcr.io
```

Set `BACKEND_IMAGE` / `FRONTEND_IMAGE` in `deploy/.env.prod` to your GHCR images (`ghcr.io/<owner>/ykmmgmt-backend:latest`, `ghcr.io/<owner>/ykmmgmt-frontend:latest`).

### 2. Start / update the stack

```powershell
# First start (images are pulled or built from source)
docker compose -f docker-compose.prod.yml --env-file deploy\.env.prod up -d

# Subsequent releases
.\scripts\deploy.ps1
```

The stack: `db` + `backend` + `frontend` + `frpc`, all with `restart: unless-stopped` so they survive reboots and Docker Desktop restarts. Only the frontend port (default 8080) is published to the host. On startup the backend automatically applies Alembic migrations, seeds the root account (if `ROOT_USERNAME`/`ROOT_PASSWORD` are set), and emits structured JSON logs (`LOG_FORMAT=json`).

### 3. Schema changes made via Schema Manager (re-squash workflow)

The Schema Manager writes runtime migrations to `ykmmgmt/runtime_migrations/` — machine-local and git-ignored. Before redeploying an image after creating/editing tables in Schema Manager, squash them into the version-controlled baseline:

```bash
cd ykmmgmt/backend
python -m scripts.squash_runtime_migrations
```

Commit the generated baseline migration, then rebuild the image. If you forget, the backend startup guard fails fast with a clear error naming the missing revision instead of a cryptic Alembic stack trace.

### 4. Logs

Logs are written to **plain files under `logs/`** (openable in any editor) and mirrored to `docker logs`. All rotation is automatic:

| File | Contents | Rotation |
|------|----------|----------|
| `logs/backend/app.log` | Every API request, app event, error (JSON) | 10 MB × 5 files |
| `logs/db/postgresql-YYYY-MM-DD.log` | PostgreSQL log + slow queries (>500 ms) | daily file, 20 MB cap |
| `logs/frpc/frpc.log` | Tunnel health and reconnects | daily, 7 days kept |
| `docker logs ykmmgmt-prod-frontend` | Nginx access/error log (not file-based) | 10 MB × 5 files |

```powershell
# Tail the backend log live (any editor or)
Get-Content logs\backend\app.log -Wait -Tail 50

# Errors from the last hour
docker logs --since 1h ykmmgmt-prod-backend | findstr "ERROR"
```

Backend log fields: `timestamp`, `level`, `logger` (`uvicorn.access` = requests, `ykmmgmt` = app events, `uvicorn.error` = server errors), `message`. Set `LOG_FORMAT=text` in `deploy/.env.prod` for human-readable output instead.

Import history (who imported what, when, row counts) is also recorded in the database and visible in the app under 数据导入 → 导入历史.

### 5. Backups

```powershell
# Manual backup (custom-format dump into backups/, prunes >30 days old)
.\scripts\backup-db.ps1
```

Schedule it daily via Windows Task Scheduler:

```
Program:   powershell.exe
Arguments: -ExecutionPolicy Bypass -File "D:\rs\ykmmgmt\scripts\backup-db.ps1"
Start in:  D:\rs\ykmmgmt
```

Restore into a scratch database:

```powershell
docker run -d --name ykmmgmt-restore -e POSTGRES_PASSWORD=restore -e POSTGRES_DB=ykmmgmt postgres:16
docker cp "backups\ykmmgmt-<timestamp>.dump" ykmmgmt-restore:/tmp/restore.dump
docker exec ykmmgmt-restore pg_restore -U postgres -d ykmmgmt --clean --if-exists --no-owner --no-privileges /tmp/restore.dump
# verify, then: docker rm -f ykmmgmt-restore
```

### Troubleshooting

- **Docker commands fail with a pipe error** — Docker Desktop is not running; start it first.
- **Backend container exits with "database schema version ... not present in this image"** — a runtime migration was never squashed; run the re-squash workflow above.
- **App unreachable from the internet** — check the frp tunnel (`docker logs ykmmgmt-prod-frpc` for `login to server success`) and the cloud-side guide in [deploy/README.md](deploy/README.md#troubleshooting).
- **Stale code after a rebuild** — verify no orphaned containers serve the old image: `docker compose -f docker-compose.prod.yml ps`, then `.\scripts\deploy.ps1` again.

## Authentication & User Management（认证与用户管理）

The app requires login — every page and API endpoint (except `GET /api/health`) rejects unauthenticated requests.

### Setup

1. Copy `.env.example` to `.env` and set:

   | Variable | Purpose |
   |----------|---------|
   | `SECRET_KEY` | JWT signing key — use a long random string in production |
   | `ROOT_USERNAME` | Username for the initial root account |
   | `ROOT_PASSWORD` | Password for the initial root account |

2. Create the root account (idempotent — re-running skips if the username exists):

   ```bash
   cd ykmmgmt/backend
   python -m scripts.seed_root
   ```

3. Start both servers and log in with the root credentials.

### Role Hierarchy

| Role | Chinese | Rights |
|------|---------|--------|
| `root` | 超级管理员 | Everything; creates admins and users. Immutable via the API (cannot be deactivated or demoted); never assignable through the API |
| `admin` | 管理员 | All operational rights (data imports, schema management, all create/edit/delete); can create and manage plain users only — cannot see root accounts or touch other admins |
| `user` | 用户 | Read-only: browse data, views, visualizations, dashboards |

- Sessions use httpOnly cookies (2-hour access token + 7-day refresh token); the frontend silently refreshes an expired session and only redirects to the login page when the refresh token is gone.
- Manage accounts in the app under **用户管理**（ root and admin only）: create users, reset passwords, change roles, enable/disable accounts.

## Import API

Upload CSV or Excel (`.csv`, `.xlsx`) files to import data into any table created via Schema Manager. Headers match a column's Chinese label or its column name.

```bash
curl -X POST http://localhost:8000/api/imports \
  -F "file=@data.csv" \
  -F "target_table=<table_name>"
```

The response contains the cleaning report (rows dropped/modified per step, warnings per column) and upsert counters: `rows_inserted`, `rows_updated`, `rows_skipped`, `rows_rejected` (`rows_imported` = inserted + updated). Re-uploading the same file **updates** existing records based on the table's configured upsert key (primary key, unique key, or content hash for keyless dedup tables).

List available tables:

```bash
curl http://localhost:8000/api/imports/tables
```

## Schema Manager（数据库管理）

Manage the database schema directly in the app — no hand-written models or migrations.

- **Inspect** every table (`/schema`): columns, types, Chinese labels, descriptions, default values, sample rows.
- **Create tables** manually or by uploading a CSV — column types and Chinese labels are inferred for review before creation. Columns support primary keys, foreign keys (picked via table/column dropdowns), descriptions, and default values.
- **Edit tables**: add/drop columns, and per column change its name, Chinese label, type, nullability, unique constraint, description, default value, and foreign key (with data-loss warnings).
- **Delete tables** with a dependency warning for views/visualizations that reference them.
- **Imports match headers two ways**: a file header equal to a column's 中文标签 *or* its real column name maps to that column.
- Every change **generates and applies an Alembic migration automatically**, and new tables appear in the Data Browser / View Builder immediately — no server restart.
- Runtime-generated migrations are written to `ykmmgmt/runtime_migrations/` (outside the backend tree) so `uvicorn --reload` never restarts mid-request; both version directories are wired up in `alembic.ini`. Squash them into the version-controlled baseline before deploying — see the re-squash workflow above.

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
│   │   ├── core/         # Config, database engine, logging, security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── routers/      # API routers
│   │   ├── schemas/      # Pydantic schemas
│   │   └── services/     # Business logic (imports, cleaning, schema manager)
│   ├── alembic/          # Version-controlled migrations (+ runtime baseline)
│   ├── scripts/          # seed_root, migrate (startup guard), serve, squash
│   ├── tests/
│   ├── main.py           # App entry point
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/             # React + Vite + TypeScript
│   ├── src/
│   │   ├── components/   # UI components (incl. ErrorBoundary)
│   │   ├── contexts/     # Auth, builder state contexts
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── pages/        # Feature pages (incl. NotFoundPage)
│   ├── Dockerfile
│   ├── nginx.conf        # SPA serving + /api proxy
│   └── package.json
├── runtime_migrations/   # Schema Manager runtime migrations (git-ignored)
├── specs/                # Project specifications & roadmap
├── deploy/               # Production configs + cloud setup guide
├── scripts/             # deploy.ps1, backup-db.ps1
├── .github/workflows/    # CI + deploy (build & push to GHCR)
├── docker-compose.yml        # Dev PostgreSQL
├── docker-compose.prod.yml   # Production stack (local machine)
├── .env                  # Dev environment (git-ignored)
└── .gitignore
```
