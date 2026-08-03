# Phase 4 — App Shell & CSV/Excel Upload UI: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Formatting (Prettier)

```bash
cd ykmmgmt/frontend && npx prettier --check "src/**/*.{ts,tsx,css}"
```

**Expected:** "All matched files use Prettier code style!" — zero unformatted files.

---

## Gate 2 — Linting (ESLint)

```bash
cd ykmmgmt/frontend && npm run lint
```

**Expected:** Zero errors, zero warnings.

---

## Gate 3 — TypeScript Compilation

```bash
cd ykmmgmt/frontend && npx tsc --noEmit
```

**Expected:** Zero type errors. No `any` usage except where explicitly justified.

---

## Gate 4 — Frontend Tests (Vitest)

```bash
cd ykmmgmt/frontend && npm test
```

**Expected:** All test suites pass, zero failures. At minimum, tests cover:
- App shell renders with sidebar and main content area
- All four routes render their respective pages
- Upload page renders the file input and target table selector
- Import history page renders the table (with mock data)

---

## Gate 5 — Backend Tests (Pytest)

```bash
cd ykmmgmt/backend && python -m pytest tests/ -v
```

**Expected:** All existing tests pass. New test for `GET /api/imports` returns paginated results in the expected format.

---

## Gate 6 — Dead Code & Unused Imports

```bash
cd ykmmgmt/frontend && npx tsc --noEmit
```

**Expected:** No unused variables, no unused imports (enforced by `noUnusedLocals` and `noUnusedParameters` in tsconfig, plus ESLint rules). Remove any dead code from the old single-page health display that is no longer used.

---

## Gate 7 — App Shell Renders & Routes Work

Manual verification in browser at `http://localhost:5173`:

1. Visit `/` — see the app shell with sidebar and an empty main content area
2. Click **上传数据** in sidebar → navigates to `/upload`, page title/header is visible
3. Click **导入历史** in sidebar → navigates to `/imports`, page title/header is visible
4. Click **仪表盘** in sidebar → navigates to `/dashboard`, "即将上线" card is visible
5. Verify sidebar active link highlighting follows the current route

**Expected:** All four routes render without errors. Sidebar link highlights correctly.

---

## Gate 8 — Sidebar Responsive Behavior

Manual verification:

1. Resize browser to mobile width (`< 768px`) — sidebar collapses, hamburger menu appears
2. Tap hamburger → sidebar opens as an overlay sheet/drawer
3. Tap a nav link → navigates, sidebar closes
4. Resize back to desktop width — sidebar is always visible, hamburger hidden

**Expected:** Sidebar behavior matches responsive design spec.

---

## Gate 9 — Sidebar Group Collapse

Manual verification:

1. On desktop, both sidebar groups (**数据管理**, **数据可视化**) are collapsed by default
2. Click **数据管理** header → group expands, showing 上传数据 and 导入历史
3. Click **数据可视化** header → group expands, showing 仪表盘
4. Click either header again → group collapses

**Expected:** Groups toggle independently. Default state is collapsed.

---

## Gate 10 — Upload Page UI

Manual verification at `/upload`:

1. A drag-and-drop zone is visible with text instructing the user to drag or click to select a `.csv` or `.xlsx` file
2. Clicking the zone opens the native file picker filtered to `.csv` and `.xlsx`
3. A target table dropdown is visible — clicking it shows Chinese table names fetched from the backend
4. Upload button is disabled until both a file and a target table are selected
5. Selecting a `.txt` file (or other invalid type) shows a client-side validation error

**Expected:** Upload page UI matches the spec. All text is in Chinese.

---

## Gate 11 — Upload Flow (End-to-End)

Manual verification:

1. Navigate to `/upload`
2. Select a valid `.csv` file (e.g., `钱包提现操作0601~0721.csv`) via drag-and-drop or file picker
3. Select the matching target table from the dropdown
4. Click **上传**
5. Observe a loading spinner / disabled button while the upload is in progress
6. After completion, see the result card with: 文件名, 目标表, 总行数, 新增行数, 更新行数, 失败行数
7. Click the link to navigate to `/imports`

**Expected:** File uploads successfully. Result matches what the backend returns. No double-submit occurs.

---

## Gate 12 — Upload Error Handling

Manual verification:

1. Upload an empty file → backend returns an error, frontend shows the error message (in Chinese)
2. Upload a file with wrong columns for the selected table → frontend shows validation errors from the backend
3. Upload an unsupported file type (e.g., `.pdf`) → client-side validation error before any request is made

**Expected:** Errors are displayed clearly in Chinese. The upload form remains usable after an error.

---

## Gate 13 — Import History Page

Manual verification at `/imports`:

1. Table is displayed with columns: 文件名, 上传时间, 状态, 总行数, 目标数据表, 新增行数, 更新行数, 失败行数, 操作
2. Status column shows color-coded badges (绿色 for 成功, 红色 for 失败, 黄色 for 处理中)
3. Rows are sorted by upload time (newest first)
4. After a fresh upload from Gate 11, the new import appears in the table (可能需要刷新)

**Expected:** Table displays import history correctly with all specified columns.

---

## Gate 14 — Empty & Error States

Manual verification:

1. On a fresh database with no imports, visit `/imports` → see "暂无导入记录" empty state
2. Simulate a network error (stop the backend) and visit `/imports` → see an error message in Chinese with a retry button

**Expected:** Empty and error states are handled gracefully. All text is in Chinese.

---

## Gate 15 — All UI Text in Chinese

Manual visual scan of the entire app:

- [x] Sidebar group headers: 数据管理, 数据可视化
- [x] Sidebar links: 上传数据, 导入历史, 仪表盘
- [x] Upload page: all labels, button text, placeholder text, error messages
- [x] Import history: column headers, status badges, empty state, error state
- [x] Dashboard: "即将上线" placeholder
- [x] Toast notifications: success/error messages

**Expected:** Zero English text visible in the UI (excluding code-like identifiers such as `.csv`/`.xlsx` file extensions).

---

## Gate 16 — Backend `GET /api/imports` Endpoint

```bash
curl -s http://127.0.0.1:8000/api/imports | python -m json.tool
```

**Expected:** Returns a JSON object with:
- `items`: array of import job objects (each with: `id`, `file_name`, `target_table`, `status`, `total_rows`, `rows_inserted`, `rows_updated`, `rows_failed`, `created_at`)
- `page`, `page_size`, `total` for pagination
- Items ordered by `created_at` descending

```bash
curl -s "http://127.0.0.1:8000/api/imports?page=1&page_size=5" | python -m json.tool
```

**Expected:** Pagination parameters work — returns at most 5 items.

---

## Merge Checklist

- [x] All 16 gates pass on a clean checkout
- [x] Prettier reports zero unformatted files
- [x] ESLint reports zero errors and zero warnings
- [x] TypeScript compiles with zero errors
- [x] Vitest — all frontend tests pass
- [x] Pytest — all backend tests pass (including new `GET /api/imports` test)
- [x] No dead code or unused imports remain
- [x] All four routes render without errors
- [x] Sidebar is responsive (collapses on mobile, always visible on desktop)
- [x] Sidebar groups are collapsed by default and toggle independently
- [x] Upload page works end-to-end (select file, choose table, upload, see result)
- [x] Upload errors are handled and displayed in Chinese
- [x] Import history table shows all specified columns with correct data
- [x] Empty state and error state render correctly on import history page
- [x] Every piece of visible UI text is in Chinese
- [x] `GET /api/imports` returns paginated results in the expected format
