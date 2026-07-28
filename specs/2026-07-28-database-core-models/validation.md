# Phase 2 — Database & Core Models: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Docker PostgreSQL is running

```bash
docker compose up -d
docker compose ps
```

**Expected:** PostgreSQL container status is `Up` (healthy). No errors in `docker compose logs db`.

---

## Gate 2 — Backend imports succeed (no broken model definitions)

```bash
cd ykmmgmt/backend
python -c "from app.models import DataSource, ImportJob, ServiceRefundWorkOrder, RefundOrder, WalletWithdrawal; print('All models imported successfully')"
```

**Expected:** `All models imported successfully` printed to stdout, zero import errors.

---

## Gate 3 — Alembic migrations apply cleanly

```bash
cd ykmmgmt/backend
alembic upgrade head
```

**Expected:** Migration completes without errors. Running it a second time reports "No migrations to apply" or equivalent.

---

## Gate 4 — All 5 tables exist in PostgreSQL

```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "\dt"
```

**Expected:** Output lists exactly 5 tables: `alembic_version`, `datasources`, `import_jobs`, `service_refund_work_orders`, `refund_orders`, `wallet_withdrawals`.

---

## Gate 5 — Seed script populates data

```bash
cd ykmmgmt/backend
python seed.py
```

**Expected:** Script prints row counts inserted (e.g., `service_refund_work_orders: 20 rows`). Exit code 0. No Python exceptions.

Verify:
```bash
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT count(*) FROM service_refund_work_orders"
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT count(*) FROM refund_orders"
docker compose exec db psql -U ykmmgmt -d ykmmgmt -c "SELECT count(*) FROM wallet_withdrawals"
```

**Expected:** Each returns 20.

---

## Gate 6 — DB health endpoint responds

```bash
# Start the dev server in background, then:
curl -s http://localhost:8000/api/health/db | python -m json.tool
```

**Expected:** JSON response with `{"status": "ok", "database": "connected"}` (or includes `tables` count).

---

## Gate 7 — Linting (backend Ruff)

```bash
cd ykmmgmt/backend
ruff check .
```

**Expected:** Zero errors, zero warnings.

---

## Gate 8 — Formatting (backend Ruff)

```bash
cd ykmmgmt/backend
ruff format --check .
```

**Expected:** "1 file(s) already formatted" (or similar — no unformatted files).

---

## Gate 9 — Tests pass

```bash
cd ykmmgmt/backend
pytest tests/ -v
```

**Expected:** All existing tests pass. New tests (if added for DB health endpoint or model sanity) also pass.

---

## Gate 10 — README reflects Phase 2 additions

Manual check: Open `README.md` and confirm it includes:
- Docker PostgreSQL setup section (`docker compose up -d`)
- Alembic migration commands (`alembic upgrade head`)
- Seed script instructions (`python seed.py`)

**Expected:** A new developer can read README and get a working database with seeded data without asking questions.

---

## Merge Checklist

- [x] All 10 gates pass on a clean checkout
- [x] `docker compose up -d` succeeds first try (no missing env vars)
- [x] `alembic upgrade head` completes with no errors
- [x] `python seed.py` loads data without exceptions
- [x] `GET /api/health/db` returns `"database": "connected"`
- [x] All 5 tables exist in PostgreSQL with correct schemas
- [x] Ruff reports zero issues on new code
- [x] Existing Phase 1 tests still pass
- [x] README documents the new DB setup workflow
