# Changelog

All notable changes to YKMMgmt are documented in this file.

---

## 2026-07-28

- **Phase 3 — CSV & Excel Import Engine:** Unified `POST /api/imports` endpoint accepting CSV and Excel files with Chinese header auto-mapping. Multi-step cleaning pipeline (whitespace strip, missing-value handling, dedup, format normalization, value validation) producing structured cleaning reports. Table-specific structural rules (extra-column merge, split-row fix) run before column mapping. Batch inserts (500 rows) with PostgreSQL savepoints for resilience. Schema validation gate rejects mismatched headers with 422. All 3 sample data files imported successfully (36K + 16K + 7.5K rows). 19 unit tests covering pipeline, parsers, validator. Ruff + format gate passed.
- **Phase 2 — Database & Core Models:** Docker Compose PostgreSQL 16, async SQLAlchemy 2.0 engine + session with FastAPI dependency injection, Alembic async migrations. `DataSource` and `ImportJob` infrastructure models. Three business tables derived 1:1 from sample CSV files: `service_refund_work_orders`, `refund_orders`, `wallet_withdrawals` — all with English column names and Chinese `comment=` descriptions. Seed script with row-skip resilience, sanity check, and DB cleanup. `GET /api/health/db` endpoint. Ruff line-length bumped to 120, B008 suppressed for FastAPI Depends. All 10 validation gates passed.
- **Feature spec skill:** New local skill at `.qoder/skills/feature-spec/` automates spec scaffolding from roadmap — discovers next unchecked phase, asks 3 mandatory clarifying questions (Scope/Decisions/Context), then generates `plan.md`, `requirements.md`, `validation.md`.

## 2026-07-27

- **Phase 1 — Project Scaffolding:** FastAPI backend with `/api/health` endpoint, CORS, Ruff linting, conda env. React 18 + TypeScript + Vite frontend with shadcn/ui, TanStack Query, Vitest, and ESLint + Prettier. Vite proxy routes `/api/*` to backend. Root `.gitignore` and `README.md` with quick-start instructions. Phase 1 feature specs (`plan.md`, `requirements.md`, `validation.md`) created.
- **Testing, responsive design, and tooling:** Vitest as formal validation gate, shadcn/ui resolved in tech-stack. Responsive design added to mission, roadmap, and Phase 1 specs. Backend: 7 Pytest tests for health endpoint, CORS, OpenAPI docs. Frontend: 10 Vitest tests (App component + utilities). Phase 1 validation.md updated to 9 gates with full merge checklist. `CHANGELOG.md` created. `.qoder/skills/` with `changelog` and `validate` skills.
