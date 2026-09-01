# Phase 13 — Polish & Deploy: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend Docker Image

1. Write `ykmmgmt/backend/Dockerfile` — multi-stage build: stage 1 installs dependencies from `requirements-lock.txt` into a virtualenv; stage 2 copies the venv + app code onto a slim Python 3.12 base, runs as a non-root user.
2. Write `ykmmgmt/backend/docker-entrypoint.sh` — runs `alembic upgrade head` (using the full Python path inside the container), then execs `uvicorn main:app --host 0.0.0.0 --port 8000`.
3. Add `.dockerignore` for the backend (exclude `.pytest_cache`, `.ruff_cache`, `__pycache__`, `tests`, `.env`).
4. Verify the image builds locally: `docker build -t ykmmgmt-backend:dev ykmmgmt/backend/`.
5. Verify the container starts against the existing dev database container and passes `GET /api/health` and `GET /api/health/db`.

## Group 2 — Frontend Docker Image

1. Write `ykmmgmt/frontend/Dockerfile` — multi-stage build: stage 1 (`node:20-alpine`) runs `npm ci` and `npm run build`; stage 2 copies `dist/` onto `nginx:alpine`.
2. Write `ykmmgmt/frontend/nginx.conf` — serves the SPA (with `try_files $uri /index.html` fallback for client-side routing), proxies `/api/` to `http://backend:8000`, sets `client_max_body_size` large enough for CSV/Excel uploads (e.g. 50m), forwards `X-Forwarded-*` headers.
3. Add `.dockerignore` for the frontend (exclude `node_modules`, `dist`, `.vite`).
4. Verify the image builds locally: `docker build -t ykmmgmt-frontend:dev ykmmgmt/frontend/`.

## Group 3 — Production Compose Stack

1. Create `docker-compose.prod.yml` at the repo root with four services on an internal network:
   - `db` — postgres:16 (mirrors existing dev service, named volume, healthcheck, `restart: unless-stopped`)
   - `backend` — backend image, env from `.env`, depends on healthy `db`, `restart: unless-stopped`, no host port published
   - `frontend` — frontend Nginx image, depends on `backend`, publishes a single host port (e.g. `8080:80`), `restart: unless-stopped`
   - `frpc` — frp client container (`snowdreamtech/frpc`) mounting `deploy/frpc.toml`, `restart: unless-stopped`
2. Compose file references registry images (`ghcr.io/<owner>/ykmmgmt-backend:latest` etc.) with `build:` fallback sections so local dev can still build from source.
3. Update `.env.example` with production variables: `DATABASE_URL` pointing at the `db` service hostname, strong `SECRET_KEY` guidance, `ROOT_USERNAME`/`ROOT_PASSWORD`, and the frp token placeholder.
4. Update `.gitignore` to exclude `deploy/frpc.toml` (contains the frp token) while keeping `deploy/frpc.toml.example` tracked.
5. Verify the full stack: `docker compose -f docker-compose.prod.yml up -d` — all four containers healthy, app reachable at `http://localhost:8080`, login works, upload + Data Browser + a dashboard render end-to-end.
6. Verify auto-restart resilience: `docker compose -f docker-compose.prod.yml restart` and a Docker Desktop restart both bring the stack back without manual intervention.

## Group 4 — Migration Lifecycle (Baseline Squash + Startup Guard)

1. Write a squash script/procedure that consolidates `ykmmgmt/runtime_migrations/` into a single version-controlled baseline Alembic migration under `ykmmgmt/backend/alembic/versions/` (checkpoint), preserving the revision chain so existing databases stamp cleanly.
2. Add a startup guard in the backend entrypoint: when `alembic_version` references a revision missing from the container's migration files, fail fast with a clear error message (instead of a cryptic Alembic stack trace).
3. Document the checkpoint procedure in the README: how to re-squash after future Schema Manager tables accumulate.
4. Verify: fresh database → `docker compose -f docker-compose.prod.yml up` → backend boots, `alembic_version` points at the baseline, Schema Manager creates a table and it survives a container rebuild.

## Group 5 — CI/CD Pipeline (GitHub Actions)

1. Create `.github/workflows/ci.yml` — on push to `main` and on PRs:
   - Backend job: set up Python 3.12, install `requirements-dev.txt`, run `ruff check` and `pytest` (with a postgres service container).
   - Frontend job: set up Node 20, `npm ci`, run `eslint`, `tsc --noEmit`, and `vitest run`.
2. Create `.github/workflows/deploy.yml` — on push to `main` (after CI passes):
   - Build backend + frontend images, tag with `latest` + the commit SHA.
   - Push to GHCR (`ghcr.io/<owner>/ykmmgmt-backend`, `ghcr.io/<owner>/ykmmgmt-frontend`) using the built-in `GITHUB_TOKEN`.
3. Write `scripts/deploy.ps1` (Windows) for the local machine: `docker compose -f docker-compose.prod.yml pull && docker compose -f docker-compose.prod.yml up -d`, plus image pruning.
4. Document one-time GHCR authentication on the local machine (`docker login ghcr.io` with a PAT) in the README.
5. Verify: push a trivial commit to `main` → CI green → images appear in GHCR → running `scripts/deploy.ps1` on the local machine pulls and restarts the stack with the new images.

## Group 6 — Public Access via Alibaba Cloud (Docs + frp Client)

1. Write `deploy/frpc.toml.example` — frp client config exposing the local frontend port (8080) through the tunnel, token placeholder, `transport.tls` enabled.
2. Write `deploy/README.md` — one-time cloud setup guide:
   - Install frps on the Alibaba Cloud ECS (binary + systemd unit, `bindPort`, token, dashboard optional).
   - Nginx server block on the cloud server reverse-proxying public HTTP (IP-only) to the frp tunnel port, with `proxy_set_header` for Host/X-Real-IP/X-Forwarded-For.
   - Alibaba security group rules: open only the Nginx port (80) and the frps bind port.
   - Note: cloud-side config never changes with app releases.
3. Verify the frpc container in the prod compose stack connects to frps (log line `login to server success`) using a real or test frps endpoint; document the manual end-to-end check (cloud IP → local app) as a validation step performed during the actual cloud setup.

## Group 7 — Database Backup Procedure

1. Write `scripts/backup-db.ps1` — runs `pg_dump` inside the `db` container, writes a timestamped `.dump` file (custom format) to a `backups/` directory, prunes backups older than N days (default 30).
2. Add `backups/` to `.gitignore`.
3. Document scheduling via Windows Task Scheduler (daily) and the restore procedure (`pg_restore` into a fresh volume) in the README.
4. Verify: run the backup script, then restore into a scratch database and confirm row counts match.

## Group 8 — Polish: Logging, Error Pages, README

1. Configure structured JSON logging in the backend (uvicorn + app loggers emit single-line JSON; keep readable text format for dev via an env flag).
2. Add user-friendly frontend error surfaces: a global error boundary page (Chinese copy per project convention) and a 404 catch-all route.
3. Rewrite the root `README.md` — architecture overview, dev quick-start (unchanged), production deployment guide (compose stack, GHCR login, deploy script, frp/cloud setup pointer to `deploy/README.md`, backup/restore), and a troubleshooting section (stale containers, migration guard errors, frp reconnect).

---

## Validation

See `validation.md` for the merge gates.
