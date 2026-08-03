# Phase 4 — App Shell & CSV/Excel Upload UI: Requirements

## Scope

This phase delivers the **application shell** (responsive sidebar navigation + layout) and the **file upload UI** that lets users upload CSV/Excel files and see their import history. It transforms the current single-page health-check display into a navigable multi-page app.

**Delivered:**
- Responsive app layout with sidebar navigation (collapsible on mobile)
- Sidebar hierarchy: two collapsible groups — 数据管理 (上传数据, 导入历史) and 数据可视化 (仪表盘)
- Four routes: `/` (empty home page), `/upload`, `/imports`, `/dashboard` (placeholder)
- Drag-and-drop file upload page with target table selector, progress indicator, and post-upload result display
- Import history page with a detailed table showing past uploads and their outcomes
- TanStack Query hooks for `POST /api/imports` and `GET /api/imports`
- Backend `GET /api/imports` endpoint for listing import jobs (paginated)

**All UI text is in Chinese** — this is an internal tool for Chinese-speaking users.

## Context (from mission.md)

This phase connects the backend import engine (Phase 3/3.5) to real users. It provides the first tangible user interface for ingesting business data — the core workflow that replaces manual copy-paste. The app shell also lays the foundation for all future dashboard and data visualization features (Phases 5–7).

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Sidebar grouping | Collapsible groups (数据管理, 数据可视化), default collapsed | Keeps the sidebar clean; users expand only the group they need. Default collapsed per user preference. |
| Home page (`/`) | Completely empty content area | Placeholder for future use — no filler content needed per user direction. |
| Dashboard page (`/dashboard`) | Simple "即将上线" placeholder card | Not yet implemented (Phase 6–7); placeholder signals it is coming. |
| Upload progress | Spinner + disabled button during upload | Simple, prevents double-submit. No chunked upload progress (file sizes are manageable). |
| Import history columns | 文件名, 上传时间, 状态, 总行数, 目标数据表, 新增行数, 更新行数, 失败行数, 操作 | Rich detail as requested by user — surfaces upsert stats from Phase 3.5 directly. |
| Mobile sidebar | Sheet/drawer overlay triggered by hamburger | Standard mobile pattern; shadcn/ui `Sheet` component handles this cleanly. |
| shadcn/ui components | Install via `npx shadcn-ui@latest add` on demand | Follows shadcn/ui convention — components are copied into the project, not imported as a package. |

## Constraints

- **All frontend UI text must be in Chinese.** No English labels, button text, error messages, or empty states. This is a hard requirement for all UI work.
- React Router v6 is already in `package.json` dependencies (v6.26.0).
- shadcn/ui component library (Tailwind-based) — components must be added via the CLI, not manually created.
- lucide-react is already available for icons.
- TanStack Query v5 is already available for data fetching.
- The backend `POST /api/imports` and `GET /api/imports/tables` endpoints already exist from Phase 3/3.5.
- The backend `GET /api/imports` endpoint needs to be created in this phase (Group 4).
- Vite proxy at `vite.config.ts` already routes `/api/*` to FastAPI — no changes needed.
- Vitest + React Testing Library are configured and serve as the formal validation gate.
- Follow existing frontend conventions: `@/` path alias, `cn()` utility from `@/lib/utils`, Tailwind CSS variables for theming.

## Out of Scope

- Dashboard metrics, charts, or data visualization (Phases 5–7)
- User authentication or login (Phase 9)
- Backend scraping/scheduled imports (Phase 8)
- File chunking or resumable uploads
- Drag-and-drop for anything other than file upload
- Real-time WebSocket progress updates — simple request/response progress is sufficient
- Editing or deleting import records
- Dark mode toggle
