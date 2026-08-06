# Phase 6 — Saved Data Views Management: Requirements

## Scope

Deliver a management page for saved data views created in Phase 5. Users can browse all their views in a list, preview the data a view produces, edit an existing view (navigating back to the Phase 5 builder), and delete views they no longer need. A placeholder "Visualisation" button is present but disabled, reserved for Phase 7.

**Included:**
- Backend APIs to list, retrieve, execute, and delete saved views
- Frontend views list page with name, description, and creation time
- Four action buttons per view row: 可视化 (placeholder), 预览 (popup dialog), 编辑 (navigate to builder), 删除 (confirm + delete)
- Preview popup dialog showing paginated results (max 100 rows) using the Data Browser grid pattern
- Edit flow that pre-fills the Phase 5 View Builder with the saved view's config
- Sidebar navigation item linking to the views list

**Explicitly excluded:**
- Creating or updating views (those are Phase 5 responsibilities; this phase only reads and deletes)
- Actual visualization/chart rendering (the 可视化 button is a placeholder for Phase 7)
- Bulk actions (delete multiple views at once)
- View duplication or cloning
- View sharing or export

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. Phase 5 enabled users to build sophisticated data views with joins, filters, aggregations, and computed columns. Phase 6 closes the loop: it lets users see what views they've built, preview the data those views produce, refine them, and clean up unused ones. This turns the View Builder from a one-shot creation tool into a managed, evolving knowledge base of business queries — directly supporting the mission of giving teams a reliable, self-updating view of the numbers that drive the business.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Delete semantics | Hard delete (permanent) | Views are user-created configurations, not business data. A confirmation dialog prevents accidental loss. No need for soft-delete complexity. |
| Preview UX | Popup dialog with paginated grid (max 100 rows/page) | Consistent with the popup pattern; avoids cluttering the list page. Reuses the Phase 4.5 Data Browser grid for consistency. 100-row cap balances usability with performance. |
| Preview data source | Execute stored `generated_sql` directly | Views already store compiled SQL from Phase 5. Executing it is simpler and faster than re-compiling from `config_json`. |
| Edit flow | Navigate to `/views/builder?id={id}`, builder pre-fills from config | Reuses the existing Phase 5 builder page rather than building a separate edit UI. The `id` query parameter triggers fetch-and-fill behavior. Save becomes PUT when editing. |
| Visualisation button | Disabled placeholder with tooltip "即将推出" | Reserves the UI slot for Phase 7 without implementing any logic. Users see it's coming. |
| List response | Metadata only (no config_json or generated_sql) | Keeps the list endpoint lightweight. Full details are fetched on demand via the detail endpoint. |
| List ordering | Newest first (created_at DESC) | Users typically want to see recently created views first. |

## Constraints

- Backend: FastAPI + SQLAlchemy 2.0 async + Pydantic v2 (per tech-stack.md)
- Frontend: React + TypeScript + Vite + shadcn/ui + TanStack Query (per tech-stack.md)
- Chinese UI text only — all labels, buttons, messages, and placeholders must be in Chinese
- No new database tables or migrations — the views table already exists from Phase 5
- Preview grid must reuse the Phase 4.5 Data Browser component pattern (paginated table with Chinese column headers)
- Edit flow must integrate with the Phase 5 View Builder page and its ViewBuilderContext
- Sidebar must follow existing pattern: icon + Chinese label, positioned in logical order

## Out of Scope

- View creation (POST /api/views) — already exists from Phase 5
- View update (PUT /api/views/{id}) — already exists from Phase 5
- Visualization/chart rendering — reserved for Phase 7
- Bulk delete or multi-select actions
- View search or filtering on the list page
- View categories, tags, or folders
