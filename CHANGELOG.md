# Changelog

All notable changes to YKMMgmt are documented in this file.

---

## 2026-07-27

- **Phase 1 — Project Scaffolding:** FastAPI backend with `/api/health` endpoint, CORS, Ruff linting, conda env. React 18 + TypeScript + Vite frontend with shadcn/ui, TanStack Query, Vitest, and ESLint + Prettier. Vite proxy routes `/api/*` to backend. Root `.gitignore` and `README.md` with quick-start instructions. Phase 1 feature specs (`plan.md`, `requirements.md`, `validation.md`) created.
- **Testing, responsive design, and tooling:** Vitest as formal validation gate, shadcn/ui resolved in tech-stack. Responsive design added to mission, roadmap, and Phase 1 specs. Backend: 7 Pytest tests for health endpoint, CORS, OpenAPI docs. Frontend: 10 Vitest tests (App component + utilities). Phase 1 validation.md updated to 9 gates with full merge checklist. `CHANGELOG.md` created. `.qoder/skills/` with `changelog` and `validate` skills.
