# Phase 13 — Polish & Deploy: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — README & Documentation Completeness

Manual review of the rewritten root `README.md` and `deploy/README.md`.

**Expected:** README covers: architecture overview, dev quick-start (unchanged from current), production deployment (compose stack, GHCR login, `scripts/deploy.ps1`, pointer to `deploy/README.md`, backup/restore), and a troubleshooting section. `deploy/README.md` covers the full one-time cloud setup: frps install + systemd unit, cloud Nginx server block, Alibaba security group rules, and a note that cloud config never changes with releases. No placeholder text remains.

---

## Gate 2 — Formatting & Linting (Backend)

```powershell
cd ykmmgmt/backend
ruff check .
```

**Expected:** Exit code 0, no findings — including any new Python files (entrypoint logic, logging config, migration squash script).

---

## Gate 3 — Formatting & Linting (Frontend)

```powershell
cd ykmmgmt/frontend
npm run lint
npx tsc --noEmit
```

**Expected:** Both commands exit 0 — including the new error-boundary and 404 components.

---

## Gate 4 — Dead Code & Hygiene

```powershell
git status --short
```

**Expected:** No leftover scaffolding files, no commented-out compose service drafts, no duplicate Dockerfiles. `deploy/frpc.toml` is NOT tracked by git (only `frpc.toml.example`); `backups/` is git-ignored. `.dockerignore` files exist in both `ykmmgmt/backend/` and `ykmmgmt/frontend/`.

---

## Gate 5 — Existing Test Suites Still Pass

```powershell
cd ykmmgmt/backend; pytest
cd ../frontend; npm run test
```

**Expected:** All backend Pytest tests and all frontend Vitest tests pass with zero failures. The deployment work must not break any existing behavior (dev workflow untouched).

---

## Gate 6 — Docker Images Build

```powershell
docker build -t ykmmgmt-backend:test ykmmgmt/backend/
docker build -t ykmmgmt-frontend:test ykmmgmt/frontend/
```

**Expected:** Both builds complete successfully. Backend image runs as a non-root user; frontend image contains only Nginx + static `dist/` assets (no `node_modules`).

---

## Gate 7 — Production Compose Stack End-to-End

```powershell
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml ps
```

Then in a browser at `http://localhost:8080`: log in with the seeded root account, upload a CSV via 数据导入, browse it in Data Browser, and render a dashboard.

**Expected:** All four services (`db`, `backend`, `frontend`, `frpc`) are up and healthy; only the frontend port (8080) is published to the host. Alembic migrations ran automatically on backend start (check `docker compose -f docker-compose.prod.yml logs backend` for the migration output). Login, upload, browsing, and dashboard rendering all work through the Nginx container.

---

## Gate 8 — Restart Resilience

```powershell
docker compose -f docker-compose.prod.yml restart
docker compose -f docker-compose.prod.yml ps
```

Additionally: restart Docker Desktop (or reboot the machine), then check `docker compose -f docker-compose.prod.yml ps` again.

**Expected:** After both a compose restart and a Docker Desktop restart, all services return to running state without any manual intervention; the app is reachable at `http://localhost:8080` and the frpc container logs show a successful re-login to frps.

---

## Gate 9 — Migration Baseline & Startup Guard

1. Fresh database: `docker compose -f docker-compose.prod.yml down -v; docker compose -f docker-compose.prod.yml up -d` — backend boots cleanly, `alembic_version` points at the baseline revision.
2. Create a table via Schema Manager, rebuild the backend image, `up -d` again — the table still exists and is registered.
3. Manually stamp the DB with a bogus revision (`alembic stamp nonexistent123` against a scratch DB) and start the backend against it.

**Expected:** (1) clean boot on the baseline; (2) Schema Manager tables survive image rebuilds; (3) the entrypoint fails fast with a clear, human-readable error naming the missing revision — not a raw Alembic stack trace.

---

## Gate 10 — CI/CD Pipeline

Push a trivial commit (e.g. a README typo fix) to `main` on GitHub.

**Expected:** The `ci.yml` workflow runs backend (ruff + pytest with a postgres service) and frontend (eslint + tsc + vitest) jobs and goes green. The `deploy.yml` workflow then builds both images and pushes them to GHCR tagged `latest` + the commit SHA; both packages are visible under the repo's GitHub Packages. On the local machine (after one-time `docker login ghcr.io`), `scripts/deploy.ps1` pulls the new images and restarts the stack; `docker compose -f docker-compose.prod.yml images` shows the new SHA tag.

---

## Gate 11 — frp Tunnel Connectivity

With a real (or test) frps endpoint configured in `deploy/frpc.toml`:

```powershell
docker compose -f docker-compose.prod.yml logs frpc
```

**Expected:** Logs contain `login to server success` and the proxy for the frontend port shows `start proxy success`. The manual end-to-end check (browse to the cloud server's public IP and reach the app) is documented in `deploy/README.md` and performed during the actual cloud setup — it is recorded as done or explicitly deferred with the cloud credentials pending.

---

## Gate 12 — Database Backup & Restore

```powershell
./scripts/backup-db.ps1
```

Then restore the produced dump into a scratch database (`pg_restore` into a fresh container/volume) and compare row counts on a few business tables.

**Expected:** A timestamped `.dump` file appears in `backups/`; backups older than 30 days are pruned; the restored scratch database has identical row counts. README documents the Windows Task Scheduler daily schedule and the restore procedure.

---

## Merge Checklist

- [ ] All 12 gates pass on a clean checkout
- [ ] README + `deploy/README.md` complete with no placeholders
- [ ] Ruff, ESLint, tsc all clean
- [ ] Backend Pytest and frontend Vitest suites fully green
- [ ] Both Docker images build; backend non-root, frontend static-only
- [ ] Prod compose stack healthy end-to-end (login, upload, browse, dashboard)
- [ ] Stack auto-recovers from compose restart and Docker Desktop restart
- [ ] Migration baseline works on fresh DB; startup guard fails fast on missing revisions
- [ ] CI green on `main`; images in GHCR; `scripts/deploy.ps1` pulls and restarts locally
- [ ] frpc connects to frps; cloud end-to-end check done or explicitly deferred
- [ ] Backup script produces restorable dumps with pruning; schedule documented
- [ ] `deploy/frpc.toml` and `backups/` git-ignored; no secrets committed
- [ ] Dev workflow (uvicorn --reload + Vite dev server) unchanged
