# Phase 4 — App Shell & CSV/Excel Upload UI: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — App Shell & Layout

1. Install and configure React Router v6 in `App.tsx` — replace the current single-page health display with a router layout
2. Create a responsive app layout component with:
   - Sidebar navigation (collapsible on mobile via hamburger, always visible on `md:`+)
   - Main content area (`<Outlet />`)
   - shadcn/ui `Sheet` component for mobile sidebar drawer
3. Build sidebar navigation with grouped hierarchy:
   - **数据管理** group (collapsible, default collapsed): 上传数据, 导入历史
   - **数据可视化** group (collapsible, default collapsed): 仪表盘
   - Use shadcn/ui `Collapsible` for group expand/collapse
   - Use `lucide-react` icons next to each link
   - Active route highlighting (shadcn/ui sidebar active state)
4. Create four page placeholder components as route targets:
   - `HomePage` (`/`) — completely empty content area (bare minimum placeholder)
   - `UploadPage` (`/upload`) — placeholder, implemented in Group 2
   - `ImportHistoryPage` (`/imports`) — placeholder, implemented in Group 3
   - `DashboardPage` (`/dashboard`) — placeholder "即将上线" card
5. Redirect `/` to the home page; ensure all four routes render within the layout

---

## Group 2 — Upload Page

1. Build the Upload Page at `/upload` with:
   - Drag-and-drop zone using native HTML5 drag events or a lightweight wrapper — accepts `.csv` and `.xlsx`
   - File picker button as fallback for click-to-browse
   - File type and size validation on the client side before upload
   - Target table selector dropdown — fetches options from `GET /api/imports/tables`, displays Chinese table names
   - Upload button (disabled until both file and target table are selected)
2. Create TanStack Query mutation hook (`useUploadFile`) for `POST /api/imports`:
   - Sends `multipart/form-data` with `file` and `target_table`
   - Handles loading, success, and error states
3. Add upload progress indicator:
   - Show a progress bar or spinner while the upload is in flight
   - Disable the upload button during the request to prevent double-submit
4. Build post-upload result display:
   - Show a result card/panel after successful upload
   - Display: 文件名, 目标表, 总行数, 新增行数, 更新行数, 失败行数, 清洗报告摘要
   - Show validation errors if the backend returned any
   - Include a link/button to navigate to the import history page
   - Use a shadcn/ui toast notification for quick success/error feedback

---

## Group 3 — Import History Page

1. Create TanStack Query hook (`useImportHistory`) for fetching import job list from `GET /api/imports` (the endpoint may need to be added to the backend; coordinate with backend if necessary)
2. Build the Import History Page at `/imports`:
   - Table displaying past imports using shadcn/ui `Table`
   - Columns: 文件名, 上传时间, 状态 (color-coded badge: 成功/失败/处理中), 总行数, 目标数据表, 新增行数, 更新行数, 失败行数, 操作
   - Status badges use shadcn/ui `Badge` with variant colors (green for 成功, red for 失败, yellow for 处理中)
   - Sortable by upload time (default: newest first)
3. Handle empty state — show a friendly "暂无导入记录" message when the table is empty
4. Handle loading state — show skeleton rows or a spinner while data is being fetched
5. Handle error state — show an error message with a retry button if the fetch fails

---

## Group 4 — Backend: Import History Endpoint

1. Add `GET /api/imports` endpoint to list recent import jobs:
   - Returns paginated list with: id, file_name, target_table, status, total_rows, rows_inserted, rows_updated, rows_failed, created_at
   - Support `?page=` and `?page_size=` query parameters
   - Ordered by `created_at DESC`
2. Ensure the response format matches what the frontend hook expects

---

## Group 5 — Polish & Integration

1. Ensure all UI text is in Chinese (sidebar labels, page titles, button text, error messages, empty states, toasts)
2. Verify the sidebar collapses on mobile (`< md` breakpoint) using a hamburger toggle
3. Verify Vite proxy still routes `/api/*` correctly to FastAPI
4. End-to-end smoke test: navigate to `/upload`, select a CSV file, upload it, verify it appears in `/imports`
