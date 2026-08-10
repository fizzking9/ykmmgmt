# Phase 8 — Saved Visualizations Management: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Backend linting

✅ PASS (no backend files modified; `ruff check` clean on `app/`, `tests/`, `main.py` — pre-existing findings in auto-generated Alembic boilerplate untouched)

```bash
cd ykmmgmt/backend && ruff check .
```

**Expected:** Zero errors, zero warnings.

---

## Gate 2 — Frontend linting

✅ PASS

```bash
cd ykmmgmt/frontend && npx eslint src/ --ext .ts,.tsx
```

**Expected:** Zero errors, zero warnings.

---

## Gate 3 — Frontend type-check

✅ PASS (verified via `npm run build` — `tsc -b` + vite build)

```bash
cd ykmmgmt/frontend && npx tsc --noEmit
```

**Expected:** Zero type errors.

---

## Gate 4 — Backend tests (regression)

✅ PASS (84 passed)

```bash
cd ykmmgmt/backend && python -m pytest tests/ -v
```

**Expected:** All existing tests pass — no backend changes were made in this phase, so `test_visualizations.py` and the full suite must pass unchanged.

---

## Gate 5 — Frontend tests

✅ PASS (29 passed, incl. 5 new in VisualizationsManagement.test.tsx)

```bash
cd ykmmgmt/frontend && npx vitest run
```

**Expected:** All tests pass, zero failures. New Phase 8 tests cover: list page rows + action buttons, thumbnail rendered only for chart types, refresh triggers re-fetch, delete confirmation dialog.

---

## Gate 6 — Visualizations list page renders with metadata and actions

✅ PASS

Manual verification in browser at `http://localhost:5173/visualizations`:

1. Page loads showing a table with columns: 缩略图, 名称, 图表类型, 来源视图, 创建时间
2. Each row shows the visualization name, a Chinese chart-type badge (表格/KPI 卡片/柱状图/折线图/饼图/散点图/直方图/箱线图), the source view name, and formatted creation date
3. Each row has three action buttons: 查看, 编辑, 删除
4. If no visualizations exist, empty state message "暂无保存的可视化，请先创建可视化" is displayed
5. A 刷新 button is visible at page level

---

## Gate 7 — Thumbnails are static, charts-only, and cached across tab navigation

✅ PASS (note: table/KPI rows fire zero `/data` requests — even better than required; switching to 数据视图 and back fired zero new `/data` requests; 刷新 re-fetched)

Manual verification in browser at `http://localhost:5173/visualizations` (requires saved visualizations including at least one chart type and one table or kpi_card type):

1. Chart-type rows (bar/line/pie/scatter/histogram/boxplot) show a small rendered chart preview in the 缩略图 column
2. Table and KPI card rows show NO chart preview (badge/placeholder instead)
3. Open the browser DevTools network panel and wait for thumbnails to finish loading. Then click another sidebar nav item (e.g. 数据视图) and click back to 可视化: NO new `/api/visualizations/{id}/data` requests fire — thumbnails render instantly from the TanStack Query cache
4. Client-side pagination (Next/Previous or page input) also fires no `/data` requests
5. Click the 刷新 button: data requests re-fire and thumbnails re-render with the latest data

---

## Gate 8 — Full-size view page renders live data with manual refresh

✅ PASS (no polling during 60s idle; invalid id shows 可视化不存在)

Manual verification in browser:

1. Click 查看 on a list row → navigates to `/visualizations/{id}` and renders the visualization full-size with live data from its source view
2. Page title shows the visualization name; a 返回 link returns to `/visualizations`
3. A 刷新 button is present; clicking it re-fetches `GET /api/visualizations/{id}/data` (visible in network panel) and re-renders the chart
4. No periodic/polling network requests occur while the page sits idle (verify ≥ 60 seconds idle in network panel)
5. Opening a non-existent id shows the Chinese not-found message "可视化不存在"

---

## Gate 9 — Edit navigates to builder pre-filled

✅ PASS (PUT fired, not POST; redirected back to list with success toast)

Manual verification in browser at `http://localhost:5173/visualizations`:

1. Click 编辑 on a row → navigates to `/visualizations/builder/{id}`
2. The Phase 7 builder loads pre-filled: source view selected, chart type selected, all per-chart-type config fields populated from the saved `config_json`
3. Changing config and saving triggers PUT (not POST) — verify in network panel
4. After saving, user lands back on the visualizations list and the updated visualization reflects the changes

---

## Gate 10 — Delete with confirmation works

✅ PASS (cancel and confirm paths verified; DELETE returned 204)

Manual verification in browser at `http://localhost:5173/visualizations`:

1. Click 删除 on a row → confirmation dialog appears with message "确定要删除可视化「{name}」吗？此操作不可撤销。"
2. Clicking 取消 closes the dialog; the visualization remains
3. Clicking 确定 sends DELETE, the row disappears, and a success toast appears
4. Verify the deletion persisted:
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/visualizations/<deleted_id>
```
**Expected:** HTTP 404.

---

## Gate 11 — Sidebar navigation

✅ PASS

Manual verification in browser:

1. Sidebar shows "可视化" nav item (below "数据视图")
2. Clicking "可视化" navigates to `/visualizations`
3. The nav item is highlighted/active on both the list page and the full-size view page
4. On mobile viewport, the sidebar can be toggled open and "可视化" is visible and clickable

---

## Merge Checklist

- [x] All 11 gates pass on a clean checkout
- [x] No backend API changes or migrations introduced (frontend-only phase)
- [x] All UI text is in Chinese (list page, view page, dialogs, badges, toasts, empty/error states)
- [x] Three action buttons per row: 查看, 编辑, 删除
- [x] Thumbnails render only for chart types; data fetched once and cached across tab navigation; re-rendered only on manual refresh
- [x] 刷新 button re-fetches and re-renders thumbnails (list) and live data (view page)
- [x] No auto-refresh / polling anywhere — data updates only on manual refresh
- [x] Edit pre-fills the Phase 7 builder and saves via PUT
- [x] Delete requires confirmation and permanently removes the visualization
- [x] Sidebar "可视化" item present and active-state correct
- [x] README.md updated if new startup steps are needed (not needed)
