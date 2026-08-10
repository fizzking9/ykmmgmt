# Phase 8 — Saved Visualizations Management: Requirements

## Scope

Deliver the frontend management experience for saved visualizations (the backend endpoints were delivered ahead of schedule and are already live):

- **Visualizations list page** (`/visualizations`): a table of all saved visualizations showing thumbnail (charts only), name, chart type (Chinese badge), source view name, and created date, with 查看 / 编辑 / 删除 actions per row and a page-level 刷新 button.
- **Static thumbnails**: chart-type visualizations (bar/line/pie/scatter/histogram/boxplot) render a small non-interactive Recharts preview. Table and KPI card visualizations render NO thumbnail. Thumbnail data is fetched once and cached across tab navigation — leaving the list page (e.g. switching to another sidebar tab) and returning does NOT re-query or re-render them. Only the manual 刷新 button triggers a re-fetch and re-render with possibly new data.
- **Full-size view page** (`/visualizations/:id`): renders the visualization at full size with live data from its source view, plus a manual 刷新 button.
- **Edit**: navigates to the Phase 7 Visualization Builder pre-filled with the saved definition; saving issues an update (PUT).
- **Delete**: confirmation dialog before permanent deletion.
- **Sidebar**: new "可视化" nav item.

## Context (from mission.md)

YKMMgmt exists to "surface what matters" — presenting KPIs through interactive metric cards, charts, and filterable tables for internal finance/operations teams. Phases 5–7 built the machinery (views → visualizations); this phase makes those visualizations first-class, browsable, maintainable assets so teams can find, inspect, update, and clean up the charts that drive their decisions — a prerequisite for composing them into dashboards in Phases 9–10.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Refresh mechanism | Manual 刷新 button; auto-refresh/polling dropped | User decision — polling was deemed unnecessary; on-demand refresh gives users control and avoids background load |
| Thumbnails on list page | Yes, but only for chart types (bar/line/pie/scatter/histogram/boxplot); table & KPI card get no thumbnail | User decision ("minimap is only needed for charts"); keeps list rendering cost bounded |
| Thumbnail lifecycle | Data fetched once and cached across tab/route navigation (TanStack Query long staleTime); NOT re-queried when the user switches to another page and back; re-rendered only on 刷新 | User decision — avoid querying all visualization data every time the list is visited; stable previews, explicit refresh for new data |
| Reuse of Phase 7 rendering | Extract/share the builder's chart rendering component for list thumbnails and full-size view | Avoids duplicating chart-type rendering logic across three surfaces |
| Backend changes | None — existing endpoints suffice | `GET /api/visualizations`, `{id}`, `{id}/data`, `DELETE` already implemented and tested |

## Constraints

- All UI text in Chinese (labels, badges, buttons, empty/loading/error states, confirmation dialogs, toasts). Only code-like identifiers may remain in English.
- Frontend stack per tech-stack.md: React + TypeScript, shadcn/ui, Recharts, TanStack Query, React Router v6, Vitest + RTL.
- Responsive layout: list page and full-size view must work at `sm:`/`md:`/`lg:` breakpoints.
- Thumbnail data fetching must not degrade UX or hit the backend repeatedly: each visualization's `/data` call happens at most once until the user clicks 刷新, including across tab navigation (cache must outlive the list page unmount); list pagination is client-side.
- The Phase 7 builder pre-fill/edit path (`/visualizations/builder/:id?` route exists) must be preserved and verified, not rebuilt.

## Out of Scope

- Auto-refresh / configurable polling intervals (explicitly dropped in favor of manual refresh).
- Dashboards: composing visualizations into grid layouts is Phase 9; sidebar "Dashboards" section is Phase 10.
- Server-side pagination of the visualizations list (the list endpoint returns all; client-side pagination is sufficient at this scale).
- Thumbnail rendering for table and KPI card visualization types.
- Any backend API changes or new migrations.
- Visualization duplication/cloning, sharing, or export (image/PNG download).
