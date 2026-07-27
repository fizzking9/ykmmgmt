# Phase 1 — Project Scaffolding: Requirements

## Scope

Deliver two runnable "hello world" applications — a FastAPI backend and a React + TypeScript + Vite frontend — that communicate over a single health-check endpoint. This phase establishes the project skeleton, tooling, and developer workflow that all subsequent phases build upon.

## Context (from mission.md)

YKMMgmt is an **internal business tool** for financial and operational data management. The backend is the single source of truth; the frontend is a read/trigger client. The scaffolding must reflect this backend-first architecture from day one.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI component library | **shadcn/ui** | Modern, Tailwind-based, smaller bundle than Ant Design |
| Python package manager | **pip + venv** | No extra tooling beyond standard library; keeps bootstrap simple |
| Docker Compose | **Deferred** | Phase 1 runs natively; containerization added in Phase 11 (Polish & Deploy) |
| Monorepo structure | `ykmmgmt/backend/` + `ykmmgmt/frontend/` | Single repo, clear separation; matches roadmap structure |

## Constraints

- Backend: Python 3.12+, FastAPI, Pydantic v2, Ruff for linting
- Frontend: React 18+, TypeScript, Vite, shadcn/ui (Tailwind CSS), ESLint + Prettier, Vitest + React Testing Library
- Responsive design: viewport meta tag, Tailwind CSS mobile-first breakpoints (`sm:`, `md:`, `lg:`, `xl:`)
- Vite dev server must proxy `/api/*` requests to the FastAPI dev server
- No database yet — Phase 2 introduces PostgreSQL
- No auth yet — Phase 10 introduces JWT auth

## Out of Scope

- Docker, Docker Compose, Nginx (deferred to Phase 11)
- Database models, Alembic (Phase 2)
- Any dashboard UI beyond the single health-check page (Phase 5+)
- CI/CD pipeline (GitHub Actions recommended but not required for Phase 1 completion)