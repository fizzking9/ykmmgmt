# Phase 15 — Frontend Upgrade (Design System & UX): Plan

Numbered task groups in implementation order. Each group is independently verifiable and maps to a priority tier from the roadmap. Decisions locked 2026-09-07: stay on Tailwind v3 (patch config, no v4 migration) · implement dark mode (system + manual toggle) · keep `/` home route blank · code-split the two giant builders · keep neutral grayscale · Geist + system CJK fallback.

---

## Group 1 — Restore the design system (P0, root cause)

The shadcn/ui v4 components run on Tailwind 3.4.19 with a v3 config missing most tokens, so destructive/error colors, focus rings, card padding, badge radius, and select truncation silently do not render. Fix the root cause first.

1. **`tailwind.config.js` — add missing color tokens.** Map every CSS variable already defined in `index.css` but not exposed as a utility: `destructive`(+`-foreground`), `secondary`(+`-foreground`), `input`, `ring`, `popover`(+`-foreground`), `chart-1`…`chart-5`, and the full `sidebar-*` set. Adding `popover` also resolves the long-standing transparent-background workaround (components currently fall back to `bg-card`).
2. **`tailwind.config.js` — fonts & radius.** Add `fontFamily.sans` (Geist + system CJK fallback) and `fontFamily.heading`; define `--radius-md` in `index.css` (or remove references to it in `button.tsx`).
3. **Translate v4-only syntax → v3 in the five primitives:**
   - `card.tsx` — `px-(--card-spacing)`/`py-(--card-spacing)`/`gap-(--card-spacing)` → `px-[var(--card-spacing)]` etc.; replace `[--card-spacing:--spacing(4)]` with a static rem value; drop v4-only `has-data-[slot=…]` selectors.
   - `button.tsx` — `focus-visible:ring-3` → `focus-visible:ring-2`; `transition-all` → `transition-colors`.
   - `badge.tsx` — `rounded-4xl` → `rounded-full`; `[&>svg]:size-3!` → `[&>svg]:!size-3`.
   - `select.tsx` — `*:data-[slot=select-value]:line-clamp-1` → `[&_[data-slot=select-value]]:line-clamp-1` (restores value truncation).
   - `sheet.tsx` — replace v4 `data-starting-style:`/`data-ending-style:`/`supports-backdrop-filter:`/`backdrop-blur-xs` with the installed `tailwindcss-animate` `data-[state=open]:animate-in` / `data-[state=closed]:animate-out` patterns.
4. **Wire the font.** `import "@fontsource-variable/geist"` in `main.tsx`; set `font-family` in `index.css` to the Geist + CJK stack (`"Geist Variable"`, `"PingFang SC"`, `"Hiragino Sans GB"`, `"Microsoft YaHei"`, `"Noto Sans SC"`, `sans-serif`), replacing the current system stack.
5. **Fix the Button focus ring (hard WCAG 2.4.7 failure).** Ensure `outline-none` is paired with a working `focus-visible` ring so keyboard focus is visible.

## Group 2 — Correctness & accessibility (P1)

1. **Login error color.** `LoginPage.tsx` error `<p>` renders in `text-destructive` (now valid after Group 1) so it is visually distinct.
2. **Dialog focus management + consolidation.** In `dialog.tsx`: add a focus trap, restore focus to the trigger on close, and link the title via `aria-labelledby`. Replace the ~10 hand-rolled modal backdrops across `ViewsListPage`, `VisualizationsListPage`, `DashboardsListPage`, `DashboardBuilderPage`, `DashboardDisplayPage`, `VisualizationBuilderPage` with the shared `Dialog`.
3. **`aria-label` on icon-only buttons.** Mobile menu trigger (`AppLayout`), back/close buttons (`VisualizationViewPage`, `ViewsListPage`, `DashboardDisplayPage`), and icon buttons in `ViewBuilderPage`, `VisualizationBuilderPage`, `DataBrowserPage`.
4. **`sr-only` text.** `sheet.tsx` "Close" → "关闭".
5. **`min-h-screen` → `min-h-dvh`** on full-height layouts: `AppLayout`, `LoginPage`, `NotFoundPage`, `ErrorBoundary`.
6. **Ellipsis copy.** Replace `...` with `…` in user-facing strings (ViewBuilder placeholders, loading text).
7. **UTC date off-by-one.** In `VisualizationBuilderPage`, replace `end.toISOString().slice(0,10)` (UTC) with a local-date formatter so the date filter is correct for UTC+8.
8. **Skip link + metadata.** Add a skip-to-content link and `<main id="main">`; add `<meta name="theme-color">` and a branded favicon to `index.html` (replace default `/vite.svg`).

## Group 3 — Feel & polish (P2)

1. **`tabular-nums`** on numeric surfaces: KPI tiles (`DashboardTiles`, `VisualizationBuilderPage` KPI), data grids (`table.tsx` numeric cells), Recharts axes/tooltips.
2. **`prefers-reduced-motion`** — provide reduced/disabled variants for animations.
3. **Touch & scroll.** `touch-action: manipulation` on interactive elements; `overscroll-behavior: contain` on modals and the sheet.
4. **Empty states.** Add an icon + a call-to-action button to the bare "暂无…/请先创建…" states (Views/Visualizations/Dashboards lists, ImportHistory, DashboardDisplay, VisualizationRenderer, DataBrowser).
5. **Unified loading.** Replace `Loader2` spinners with layout-matching skeletons where feasible.

## Group 4 — Structure & performance (P3)

1. **Code-split the builders.** Route-level `React.lazy` for `VisualizationBuilderPage` (143 KB) and `ViewBuilderPage` (101 KB) in `App.tsx`, with a route-level `Suspense` fallback, so both leave the initial bundle.
2. **Dark mode.** Add a `.dark` token block in `index.css`; wire `ThemeProvider` (next-themes, already installed) in `main.tsx`; add a theme toggle in the sidebar footer (system preference default + manual override, persisted to localStorage). Validate the existing `dark:` variants in `button.tsx`, `badge.tsx`, `select.tsx`, `UsersPage.tsx`.
3. **`color-scheme`.** Set `color-scheme` (light/dark) so scrollbars and native inputs match the active theme.
