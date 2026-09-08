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
| **WebGL / 3D** | Three.js | Particle/glow rendering for the Phase 16 welcome splash; loaded only in that lazy chunk so the main bundle is unaffected |

## Database

| Choice | Rationale |
|--------|-----------|
| **PostgreSQL 16+** | Robust, great JSON support for flexible metric schemas, strong ecosystem |

Data from external sources (CSVs, APIs) is **normalized and stored** in PostgreSQL — the dashboard never queries sources directly; it always reads from the curated local DB.

## MCP Server (Phase 14)

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **Language** | Python 3.12+ | Same ecosystem as the backend; shares conda env |
| **MCP SDK** | `mcp` (Python) | Official Model Context Protocol SDK; streamable HTTP transport for remote MCP clients |
| **Transport** | Streamable HTTP (persistent service) | Replaces the original stdio choice — a network-reachable service fits remote agents and the Docker/frpc deploy topology better than a per-client local subprocess |
| **Chart rendering** | matplotlib (in the MCP server) | Server-side PNG rendering of non-table charts — deterministic output, correct `config_json` interpretation guaranteed by code, and raw data never enters the agent's context. Accepts the double implementation (Recharts for UI, matplotlib for MCP) in exchange for reliability — agent-side rendering (raw JSON + SKILL) was tried and reverted: non-deterministic output, misread variables, per-run scripts |
| **Backend communication** | httpx | Async HTTP client to call the FastAPI backend's REST API |
| **Backend auth** | Service account JWT | MCP server authenticates with the backend via env-var credentials, not user sessions |
| **MCP client auth** | API key (`Authorization: Bearer`) | Incoming MCP connections must present a valid `YKM_MCP_API_KEY`; requests without one are rejected (401) |
| **Deployment** | Docker Compose service + GHCR image | Runs as a persistent service in the production stack, exposed to external agents via the frpc tunnel |

The MCP server is a **persistent HTTP service** (`ykmmgmt/mcp_server/`), deployed as a Docker Compose service in the production stack — not part of the FastAPI app, and no longer a per-client subprocess. It exposes YKMMgmt capabilities as MCP tools that external AI agents discover and invoke over streamable HTTP.

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
