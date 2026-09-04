# Phase 14 — MCP Server for External AI Agents: Requirements

## Scope

Deliver a persistent MCP server (`ykmmgmt/mcp_server/`) that external AI agents connect to over **streamable HTTP**. The server runs as a Docker Compose service in the production stack, is exposed to external agents via the frpc tunnel, and protects its MCP endpoint with an API key. It exposes YKMMgmt capabilities as MCP tools, starting with visualization export. A backend endpoint (`GET /api/visualizations/{id}/export`) provides CSV download for table-type visualizations, used by both the frontend UI and the MCP server. The frontend table export switches from html2canvas PNG capture to the new CSV endpoint. The MCP export tool uses **server-side rendering**: table charts download as CSV, all other chart types are rendered to PNG by a matplotlib renderer inside the MCP server — deterministic images with correct chart configuration, and no raw data entering the agent's context.

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. It unifies business data, automates manual workflows, and surfaces key metrics through interactive dashboards. The MCP server extends this mission by making YKMMgmt's data and visualizations accessible to external AI agents, enabling automated reporting and data extraction workflows that go beyond the web UI.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|----------|
| MCP transport | Streamable HTTP | A persistent, network-reachable service fits remote agents and the existing Docker/frpc deploy topology. Replaces the original stdio choice (per-client local subprocess), which cannot serve agents running on other machines and does not fit the production stack |
| MCP server location | Persistent Docker Compose service (`ykmmgmt/mcp_server/`) | Runs 24/7 alongside backend/frontend in the production stack; lifecycle managed by Docker, not by an MCP client spawning a subprocess; reaches the backend over the Docker internal network |
| MCP client authentication | API key (`Authorization: Bearer <YKM_MCP_API_KEY>`) | Streamable HTTP exposes the endpoint over the network, so the implicit trust of a local stdio subprocess no longer applies. A shared secret rejects unauthorized callers (401) while staying simple for this phase |
| Exposure | frpc tunnel | A new `[[proxies]]` entry tunnels the MCP port to the cloud entry, so external agents reach it the same way the frontend is reached — no separate public infrastructure |
| Backend authentication | Service account JWT | Reuses existing auth system (login endpoint, JWT tokens, role enforcement); no new auth infrastructure needed; service account created as a regular user with appropriate role |
| Table export format | CSV via backend endpoint | Backend generates CSV directly from query results — consistent encoding (UTF-8 with BOM), no browser dependency; both frontend and MCP server use the same endpoint |
| Non-table chart export format | PNG rendered server-side by the MCP server (matplotlib) | Deterministic, correct interpretation of `config_json` guaranteed by code — agent-side rendering was tried and reverted (non-deterministic output across runs, misinterpreted chart variables, ad-hoc .py script per run). Accepts the double chart implementation (Recharts for UI, matplotlib for MCP) in exchange for reliability |
| Renderer location | matplotlib inside the MCP server, not the backend | Keeps matplotlib (and its image/font dependencies) out of the FastAPI Docker image; the backend `/data` endpoint stays the stable raw-data contract, so any rendering approach can be swapped without backend changes |
| Tool result shape | File-based export + compact summary | Full datasets inline would blow the agent's context window or get truncated; with server-side rendering, raw chart data never enters the agent's context at all — only file paths and compact previews (columns + row count) do |
| Tool framework | File-based registry with auto-discovery | Adding a new tool = dropping a new file into `tools/`; no central registry file to maintain; each tool is self-contained |
| Distribution | Docker image (GHCR) as the primary deployment; pip-installable package retained for the tool code | The production deployment is the `mcp_server` Docker service built from `ykmmgmt/mcp_server/Dockerfile` and pushed to GHCR; the console script now starts the HTTP server instead of stdio |

> **Decision history (rendering):** the spec originally chose agent-side rendering (raw data JSON + a rendering SKILL delivered as an MCP prompt and standalone `SKILL.md`). Manual testing with a third-party agent exposed unacceptable drawbacks (see the PNG row above) and the decision was reverted to server-side rendering. The SKILL/prompt mechanism was removed along with it.
>
> **Decision history (transport):** the spec originally chose stdio transport. It was replanned to streamable HTTP because a persistent, network-reachable service better fits remote agents and the existing Docker/frpc deploy topology; stdio support is fully removed.

## Constraints

- MCP server runs in the same conda environment as the backend (Python 3.12+) in dev; in production it runs in its own Docker container
- MCP server communicates with the FastAPI backend over HTTP (localhost in dev, the Docker internal network in production)
- The MCP endpoint requires a valid API key on every request (`Authorization: Bearer <YKM_MCP_API_KEY>`); requests without a valid key are rejected with 401
- The MCP service runs in the `internal` Docker network and reaches the backend over that network; frpc proxies the MCP port to the cloud entry so external agents can connect
- Service account credentials are provided via environment variables (`YKM_SERVICE_USERNAME`, `YKM_SERVICE_PASSWORD`) — never hardcoded; the MCP API key is provided via `YKM_MCP_API_KEY`
- All backend API endpoints require authentication — the MCP server must handle login and token refresh transparently
- CSV export must use UTF-8 with BOM for Excel compatibility (project convention from data import pipeline)
- Frontend table export change must not break the existing PNG export for non-table chart types
- Tool results must never inline full datasets — only file paths and compact schema previews (context-window protection)
- Rendered PNGs must handle Chinese text (titles, axis labels, legends) — explicit CJK font selection with fallbacks, never tofu boxes
- Every chart type's `config_json` required keys must be honored by the renderer (x_column/y_columns for bar/line/scatter, label_column/value_column for pie, columns/bins for histogram, category_column/value_column for boxplot, value_column/label for kpi_card) — the renderer never guesses columns

## Out of Scope

- stdio transport (fully replaced by streamable HTTP)
- Per-user auth passthrough / end-user identity propagation to the backend (the API key + service account JWT model is sufficient for this phase)
- Additional MCP tools beyond `export_visualizations` (future phases will add more)
- Backend-side chart rendering endpoint (matplotlib lives in the MCP server; adding it to FastAPI would bloat the backend Docker image — rejected)
- Dashboard export via MCP (only individual visualizations in this phase)
- Pixel-perfect parity with the Recharts UI rendering (readable, correct matplotlib charts are the bar, not visual clones)
