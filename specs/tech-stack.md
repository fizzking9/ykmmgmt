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
| **UI components** | shadcn/ui | Modern, Tailwind-based, copy-paste components, smaller bundle than Ant Design |
| **Charts** | Recharts | React-native charting, composable, good for metric cards & time series |
| **Data fetching** | TanStack Query (React Query) | Caching, refetching, loading/error states for API calls |
| **Routing** | React Router v6 | Standard SPA routing |
| **Testing** | Vitest + React Testing Library | Vite-native, fast, component-level tests; serves as the formal validation gate for feature completion |
| **Responsive design** | Tailwind CSS breakpoints | Mobile-first responsive utilities (`sm:`, `md:`, `lg:`, `xl:`) built into every component |

## Database

| Choice | Rationale |
|--------|-----------|
| **PostgreSQL 16+** | Robust, great JSON support for flexible metric schemas, strong ecosystem |

Data from external sources (CSVs, APIs) is **normalized and stored** in PostgreSQL — the dashboard never queries sources directly; it always reads from the curated local DB.

## Infrastructure & DevOps

| Layer | Choice |
|-------|--------|
| **Containerization** | Docker + Docker Compose (production stack runs on the local machine) |
| **Reverse proxy (local)** | Nginx — serves the React SPA and proxies `/api` to FastAPI |
| **Public entry / tunnel** | frp tunnel (frps on Alibaba Cloud ECS, frpc on the local machine) + Nginx on the cloud server as the stateless public reverse-proxy entry |
| **CI/CD** | GitHub Actions — lint, test, build Docker images, push to a container registry (GHCR or Alibaba ACR); the local machine pulls new images and restarts |
| **Version control** | Git |

## Key Architectural Decisions

1. **Backend-first API design** — the FastAPI backend is the single source of truth. The React frontend is a read/trigger client only.
2. **Import pipeline pattern** — each external source type (CSV, API, spreadsheet) has a dedicated import handler. Imports run synchronously for ad-hoc uploads and asynchronously (scheduled) for recurring pulls.
3. **Metric normalization** — raw imported data is transformed into a unified metric schema before hitting the dashboard, so charts and cards don't need source-specific logic.
4. **Deployment topology** — the full stack (backend, frontend, PostgreSQL) runs in Docker on the local machine. The Alibaba Cloud server is a stateless public entry point only: its Nginx reverse-proxies traffic through an frp tunnel to the local machine, and it is configured once (no per-release deployments to the cloud). CI builds and pushes Docker images; the local machine pulls and restarts for fast iteration.
