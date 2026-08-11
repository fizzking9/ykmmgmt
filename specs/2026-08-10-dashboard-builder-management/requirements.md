# Phase 9 — Dashboard Builder & Management: Requirements

## Scope

Deliver a full dashboard lifecycle: compose, save, view, edit, rename, and delete dashboards built from tiles on a draggable/resizable grid.

**Tile types (3):**
- **Visualization tiles** — reference a saved visualization from Phase 8 (by `visualization_id`).
- **Text/markdown tiles** — free-form content for titles, notes, and section headers.
- **Ad-hoc KPI card tiles** — created inline (pick a view + value column + label + aggregation), not requiring a pre-saved visualization.

**Display-page interactivity:**
- Per-tile manual refresh (consistent with Phase 8's manual-refresh decision; no auto-refresh/polling).
- Full-screen single-tile view (maximize a tile).
- **Global time controls** — a date-range picker, a time-granularity picker (年/月/日), and an aggregation-function selector. These apply **only** to tiles whose visualization declares a `date_column` in its `config_json` (a new "时间配置" profile set in the Visualization Builder). Tiles without a `date_column` are unaffected and show a subtle hint. This design keeps the global filter flexible and less error-prone when tiles come from different views.

**Management:**
- Dynamic sidebar: a collapsible "仪表盘" parent section whose children are the saved dashboards (by name); the parent links to a list/manage page.
- List/manage page with create, rename, delete, and view/edit entry points.
- Unique dashboard names with a name-conflict save/update flow mirroring views and visualizations.

## Context (from mission.md)

YKMMgmt's mission is to "surface what matters" by presenting KPIs through interactive metric cards, charts, and filterable tables on a single, responsive internal dashboard. Phases 5–8 built the ability to create data views and visualizations; Phase 9 is the capstone that composes those visualizations into the shared, live dashboard the team actually checks — directly fulfilling the "single dashboard" and "responsive by default" promises.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Grid library | `react-grid-layout` | Roadmap-endorsed; mature drag/resize grid with a serializable layout array. |
| Layout persistence | Store the raw `react-grid-layout` layout array (mapped to `{tile_type, visualization_id?, x, y, w, h, content?/config?}`) in `layout_json` JSONB | Simplest faithful round-trip; JSONB avoids a join table and matches how `config_json` is stored elsewhere. |
| Sidebar behavior | Dynamic collapsible "仪表盘" parent with one child nav item per dashboard | Roadmap requirement; quick access to each dashboard. Uses explicit `isLinkActive` logic to avoid NavLink prefix-matching pitfalls on `/dashboards/builder*`. |
| Global time filter mechanism | Per-visualization `date_column` profile (set in Visualization Builder) + optional `start`/`end`/`granularity`/`agg` query params on `GET /api/visualizations/{id}/data` | Tiles come from different views with different date columns; declaring the date column per visualization lets the global picker target the right column and lets non-time tiles opt out cleanly. |
| SQL for time overrides | Regenerate parameterized SQL from the view's stored config (existing `_build_sql_from_config` path), injecting the date filter / `date_trunc` re-bucketing | Matches the project's "regenerate SQL from config, never store params" decision; keeps values bound (no SQL injection). |
| Name uniqueness | Unique `dashboards.name` with 409 conflict flow | Consistent with views and visualizations; prevents ambiguous sidebar child labels. |
| Responsive strategy | Desktop-first grid; below `lg`, tiles stack vertically read-only (no drag/resize) | `react-grid-layout` touch support is limited; internal tool is primarily used on desktop. |
| Builder state persistence | `DashboardBuilderContext` above the router | Mirrors ViewBuilder/VisualizationBuilder so builder state survives navigation. |

## Constraints

- **Tech stack:** FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2 backend; React 18 + TypeScript + Vite + shadcn/ui + TanStack Query + React Router v6 frontend; PostgreSQL 16. New dependency: `react-grid-layout`.
- **Backend-first:** the FastAPI backend is the source of truth; the frontend is a read/trigger client.
- **Chinese UI:** all frontend text (labels, buttons, empty/loading/error states, toasts, dialogs, placeholders) must be in Chinese; backend error messages in Chinese.
- **Chinese column comments:** every new model column has a Chinese `comment=`.
- **No auto-refresh:** tile data is fetched on load and on manual refresh / global-filter change only (Phase 8 decision).
- **Alembic:** schema changes ship as a migration; `upgrade head` and `downgrade -1` must both work.
- **Risk:** `react-grid-layout` adds bundle weight and CSS; touch drag/resize is unreliable — mitigated by the desktop-first responsive strategy.
- **Risk:** global time overrides must stay parameterized — reuse the SQL-regeneration path rather than string interpolation.

## Out of Scope

- Auto-refresh / polling of tiles.
- Cross-tile interactions (click one chart to filter another).
- Dashboard sharing/permissions, per-user dashboards, or auth (Phase 11).
- Touch/mobile drag-and-resize editing (mobile is read-only stacked view).
- Scheduled report/export (PDF/PNG) of dashboards.
- Version history of dashboard layouts.
- Platform data scraping (Phase 10).
