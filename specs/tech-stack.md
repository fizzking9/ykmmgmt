# YKMMgmt — Tech Stack

## Backend

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.12+ | Fast development, rich data ecosystem (Pandas, etc.) |
| **Framework** | FastAPI | Async, auto OpenAPI docs, great DX, high performance |
| **ORM** | SQLAlchemy 2.0 | Mature, async support, works seamlessly with FastAPI |
| **Migrations** | Alembic | Standard companion to SQLAlchemy |
| **Task scheduling** | APScheduler or Celery + Redis | For scheduled CSV/API imports; start with APScheduler for simplicity |
| **Data processing** | Pandas, openpyxl | CSV parsing, Excel/spreadsheet ingestion, data transformation |
| **Validation** | Pydantic v2 | Built into FastAPI; request/response models, config management |
| **Testing** | Pytest + httpx | Async test client for FastAPI endpoints |

## Frontend

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | TypeScript | Type safety, better tooling, scales well |
| **Framework** | React 18+ | Largest ecosystem, strong component model, team familiarity |
| **Build tool** | Vite | Fast dev server, quick HMR, modern defaults |
| **UI components** | Ant Design or shadcn/ui | Rich table, form, and layout primitives for dashboards |
| **Charts** | Recharts | React-native charting, composable, good for metric cards & time series |
| **Data fetching** | TanStack Query (React Query) | Caching, refetching, loading/error states for API calls |
| **Routing** | React Router v6 | Standard SPA routing |
| **Testing** | Vitest + React Testing Library | Vite-native, fast, component-level tests |

## Database

| Choice | Rationale |
|--------|-----------|
| **PostgreSQL 16+** | Robust, great JSON support for flexible metric schemas, strong ecosystem |

Data from external sources (CSVs, APIs) is **normalized and stored** in PostgreSQL — the dashboard never queries sources directly; it always reads from the curated local DB.

## Infrastructure & DevOps

| Layer | Choice |
|-------|--------|
| **Containerization** | Docker + Docker Compose |
| **Reverse proxy** | Nginx (production) |
| **CI** | GitHub Actions (lint, type-check, test) |
| **Version control** | Git |

## Key Architectural Decisions

1. **Backend-first API design** — the FastAPI backend is the single source of truth. The React frontend is a read/trigger client only.
2. **Import pipeline pattern** — each external source type (CSV, API, spreadsheet) has a dedicated import handler. Imports run synchronously for ad-hoc uploads and asynchronously (scheduled) for recurring pulls.
3. **Metric normalization** — raw imported data is transformed into a unified metric schema before hitting the dashboard, so charts and cards don't need source-specific logic.
