# Phase 13 — Polish & Deploy: Requirements

## Scope

Deliver the full Phase 13 roadmap scope: a production-ready deployment of YKMMgmt where the entire stack (FastAPI backend, React SPA served by Nginx, PostgreSQL 16) runs in Docker containers on the local Windows machine, publicly reachable through an Alibaba Cloud ECS server that acts purely as a stateless reverse-proxy entry via an frp tunnel. A GitHub Actions CI/CD pipeline lints, tests, builds, and pushes Docker images to GHCR on every push to `main`; the local machine pulls new images and restarts for fast iteration. The phase also covers the runtime-migration baseline squash with a startup guard, a database backup/restore procedure, structured JSON logging, user-friendly error pages, and a rewritten README covering both dev and production workflows.

## Context (from mission.md)

YKMMgmt is an internal business tool whose value depends on being a reliable, always-available shared dashboard for finance, operations, and management. Until now it has run only in dev mode (uvicorn --reload + Vite dev server) on a single machine. This phase turns it into a production service the team can depend on daily: reachable from anywhere via the cloud entry point, resilient to machine reboots, backed up, and continuously deployable — while keeping all business data on the local machine under the organization's control.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Deployment topology | Full stack in Docker on the local machine; Alibaba Cloud server is a stateless reverse-proxy entry only | Data stays on hardware we control; the cloud server is configured once and never changes with app releases |
| Tunnel technology | frp (frps on cloud, frpc as a container in the prod compose stack) | Self-hosted, free, full control, survives reconnects, works with HTTP now and HTTPS later |
| Container registry | GHCR (ghcr.io) | Free, natively integrated with GitHub Actions via `GITHUB_TOKEN`, no extra account; local pulls are infrequent so China-network pull speed is acceptable |
| CI/CD delivery model | GitHub Actions builds + pushes images; local machine pulls and restarts (`scripts/deploy.ps1`) | The cloud server needs no deployments; no SSH into the local machine required; every release is a tested, immutable image |
| Production compose layout | Separate `docker-compose.prod.yml`; existing dev compose and dev workflow (uvicorn --reload + Vite dev server) untouched | Dev iteration speed is preserved; production config never leaks into the dev path |
| Host platform | Windows 11 + Docker Desktop (WSL2) | This is the machine that runs the production stack; all scripts are PowerShell |
| Restart resilience | `restart: unless-stopped` on all services; frpc reconnects automatically | The stack must survive machine reboots and Docker Desktop restarts without manual intervention |
| Database backups | `scripts/backup-db.ps1` (pg_dump custom format, timestamped, 30-day pruning) + Windows Task Scheduler | The DB is a local Docker volume with no managed backups; data loss would be unrecoverable otherwise |
| Public access | IP-only over HTTP for now; domain + HTTPS deferred | Team-internal tool; `cookie_secure` flips to `True` when HTTPS lands |
| Migration lifecycle | Squash `runtime_migrations/` into a version-controlled baseline migration; entrypoint fails fast when `alembic_version` references a missing revision | Redeployments and DB restores must never depend on machine-local files |

## Constraints

- **Windows host:** All local-machine automation is PowerShell (`scripts/deploy.ps1`, `scripts/backup-db.ps1`). Docker Desktop must be running for any docker command to work.
- **Backend conventions:** Python 3.12, dependencies pinned in `requirements-lock.txt`, Alembic migrations run via the env's Python; Ruff + Pytest are the backend quality gates.
- **Frontend conventions:** Node 20, npm ci from `package-lock.json`; ESLint + tsc + Vitest are the frontend quality gates; all UI copy in Chinese per project convention (applies to the new error pages).
- **Auth:** httpOnly-cookie JWT already implemented; over HTTP, `cookie_secure` stays `False` (already the default in config). CORS origins in `main.py` must not break when the app is served from the Nginx container (same-origin, so CORS is bypassed in production).
- **frp token secrecy:** `deploy/frpc.toml` contains the tunnel token and must be git-ignored; only `frpc.toml.example` is tracked.
- **GHCR authentication:** The local machine needs a one-time `docker login ghcr.io` with a PAT (read:packages) before the deploy script works.
- **Cloud setup is manual:** frps + Nginx on the Alibaba ECS are set up once by hand following `deploy/README.md`; CI does not touch the cloud server.

## Out of Scope

- Domain registration and HTTPS/TLS termination (deferred; noted as a follow-up that requires flipping `cookie_secure`)
- Automated deployment to the Alibaba Cloud server (it is configured once, manually)
- Watchtower or other auto-pull daemons (manual `scripts/deploy.ps1` is the delivery mechanism; auto-pull can be added later)
- High availability / multi-machine failover
- Platform data scraping (Phase 14, post-deployment)
- Monitoring/alerting stack (e.g. Prometheus, Grafana) — structured logs are delivered, but no metrics pipeline
