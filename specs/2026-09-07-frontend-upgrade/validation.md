# Phase 15 — Frontend Upgrade (Design System & UX): Validation

How to know the implementation succeeded and can be merged. Every gate must pass. All commands run from `ykmmgmt/frontend/` unless noted.

---

## Gate 1 — Formatting

```bash
npm run format -- --check
```

**Expected:** Prettier reports zero unformatted files (all files "unchanged" / exit 0).

---

## Gate 2 — Linting

```bash
npm run lint
```

**Expected:** ESLint exits 0 with zero errors and zero warnings.

---

## Gate 3 — Type check & dead code

```bash
npx tsc -b
```

**Expected:** TypeScript compiles with zero errors. No unused-import / unused-variable errors (the two removed eager imports of the builder pages in `App.tsx` must not leave dangling references).

---

## Gate 4 — Tests

```bash
npm test
```

**Expected:** All 12 vitest suites pass, zero failures. Assertions that changed due to intended visual changes (e.g. badge radius, button classes) are updated to the new markup, not deleted.

---

## Gate 5 — Design-system utilities exist in the built CSS

```bash
npm run build
node -e "const fs=require('fs');const files=fs.readdirSync('dist/assets').filter(f=>f.endsWith('.css'));const c=fs.readFileSync('dist/assets/'+files[0],'utf8');const t=['text-destructive','bg-destructive','ring-ring','border-input','bg-secondary','font-heading','tabular-nums','bg-popover'];const m=t.filter(x=>!c.includes(x));if(m.length){console.error('MISSING: '+m.join(', '));process.exit(1)}console.log('all present')"
```

**Expected:** `all present` — every previously-missing token now compiles into the production CSS. The check looks for the token name as a substring (e.g. `ring-ring` matches `.focus-visible\:ring-ring`), since Tailwind JIT only emits the variant-prefixed classes actually used in source.

---

## Gate 6 — Visual repair check (manual)

Run `npm run dev`, sign in, and inspect the UI in light mode.

**Expected:**
- A destructive action (e.g. delete button / 删除) renders **red**.
- Badges (e.g. role/status badges on 用户管理) render as **pills**, not squares.
- Cards have visible **internal padding** (content no longer flush to the edge).
- Long select/dropdown values **truncate** instead of overflowing.
- The login error message (submit wrong credentials) is **red**, distinct from body text.
- The UI uses the Geist font for Latin/numbers (inspect `font-family` in DevTools).

---

## Gate 7 — Keyboard accessibility pass (manual)

Using only the keyboard (Tab / Shift+Tab / Enter / Escape):

**Expected:**
- Every interactive element is reachable and shows a **visible focus indicator** (buttons, selects, inputs, nav links).
- Opening any dialog moves focus into it, Tab cycles **within** the dialog (focus trap), and Escape / the close button returns focus to the triggering element.
- A skip-to-content link appears on first Tab and jumps to `<main id="main">`.

---

## Gate 8 — Code-splitting of the builders

```bash
npm run build
```

**Expected:** Build output lists `ViewBuilderPage` and `DashboardBuilderPage` as **separate chunks**, not inside the main `index-*.js` bundle. The main entry chunk is measurably smaller than before the change. Navigating to `/views/builder` and `/dashboards/builder` still loads each page correctly (lazy chunk loads, `Suspense` fallback shows briefly).

**Known limitation:** `VisualizationBuilderPage` remains in the main bundle because `VisualizationRenderer` (used by list-page thumbnails, the view page, and dashboard tiles) statically imports the chart-preview components from it. Splitting it would require extracting ~1500 lines of preview code into a shared module — deferred to a later refactor. The other two builders are successfully split.

---

## Gate 9 — Dark mode (manual)

With the theme toggle in the sidebar footer:

**Expected:**
- Toggle switches the app between light and dark; the choice **persists across reload** (localStorage).
- With no stored preference, the app follows the OS `prefers-color-scheme`.
- No unreadable surfaces in dark mode — text/background contrast holds on cards, tables, badges, selects, dialogs, and UsersPage role badges.
- Scrollbars and native inputs match the theme (`color-scheme`).

---

## Merge Checklist

- [x] All 9 gates pass on a clean checkout (Gate 8 has a documented limitation for VisualizationBuilderPage)
- [x] Prettier / ESLint / `tsc` clean; all 12 vitest suites green (103 tests pass)
- [x] Built CSS contains the previously-missing tokens (`destructive`, `ring`, `input`, `secondary`, `font-heading`, `tabular-nums`, `popover`)
- [x] Visual repair confirmed: red destructive, pill badges, padded cards, truncating selects, red login error, Geist font (manual)
- [x] Keyboard pass: visible focus everywhere, dialogs trap + restore focus, skip link works (manual)
- [x] ViewBuilderPage and DashboardBuilderPage are separate chunks, out of the initial bundle; VisualizationBuilderPage remains coupled to VisualizationRenderer (documented limitation)
- [x] Dark mode toggles, persists, follows OS by default, with no unreadable surfaces (manual)
- [x] No new runtime dependencies beyond those already installed; all UI text remains Chinese
