# Phase 15 — Frontend Upgrade (Design System & UX): Requirements

## Scope

Deliver a repair-and-hardening pass over the existing React frontend, covering all four priority tiers from the roadmap (P0–P3). The work makes the already-installed shadcn/ui v4 components render correctly on the project's Tailwind 3.4.19 setup, closes the accessibility gaps that fail baseline WCAG, unifies loading/empty states, code-splits the two oversized builder pages out of the initial bundle, and implements dark mode. It changes how the UI **renders and behaves**, not the app's visual identity — no new accent color, no layout redesign, no home-page design.

## Context (from mission.md)

YKMMgmt is an internal business tool whose value is "surface what matters" through metric cards, charts, and filterable tables, "responsive by default" across devices. A UI that silently drops destructive colors, focus rings, and card padding — and that ships two 100 KB+ builder pages to every visitor — undercuts both the credibility of the data presented and the responsive promise. This phase restores the design system so the interface is trustworthy, accessible to keyboard users, and fast to first paint, directly serving the mission's "reliable, self-updating view of the numbers."

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Tailwind fix strategy | Stay on v3.4.19, patch `tailwind.config.js` + translate v4-only syntax in the 5 primitives | Lowest risk, no dependency churn, unblocks ~40 audit findings; a v4 migration re-validates the entire utility surface mid-project |
| Dark mode | Implement (`.dark` tokens + `ThemeProvider`) | `dark:` variants already ship in button/badge/select/UsersPage; `next-themes` installed and `sonner` already calls `useTheme()` — the wiring is half-done |
| Dark-mode control | System preference default + manual toggle in sidebar footer, persisted to localStorage | Matches user expectation for a modern BI tool; `next-themes` default behavior |
| Home route `/` | Leave blank (real home page is a later phase) | User decision — avoids scope creep into page design |
| Performance scope | Route-level `React.lazy` code-splitting of the two builders only | Clear, high-value win; URL-state sync explicitly deferred |
| Accent color | Keep neutral grayscale, no new accent | Enterprise-neutral; charts remain the only hue; least disruptive |
| CJK font | Geist for Latin/numbers + system CJK fallback (PingFang/YaHei/Noto) | No new dependency, no multi-MB CJK webfont payload |
| Scope tiers | All P0–P3 | User decision — complete the full repair in one phase |
| Visual delta | Accept intended corrections; update broken vitest assertions | The visual changes (red destructive, pill badges, padded cards, focus rings, dark mode) are the intended repair, not regressions |

## Constraints

- **Do not migrate to Tailwind v4.** All fixes must work within Tailwind 3.4.19 + the v3 `tailwind.config.js`.
- **Do not break existing functionality.** The 12 frontend vitest suites, `tsc`, and ESLint must stay green; assertions that break due to intended visual changes are updated, not deleted to force a pass.
- **Work with the existing stack** — React 18, Vite 5, shadcn/ui (`@base-ui/react`), Recharts 3.10, `tailwindcss-animate` (already installed). No new UI framework or styling library.
- **All UI text remains Chinese** per project convention (e.g. `sr-only` "Close" → "关闭"); new empty-state CTA labels and toggle labels in Chinese.
- **No new runtime dependencies** except where already present (`next-themes`, `@fontsource-variable/geist`, `tailwindcss-animate` are installed). No bundled CJK webfont.
- P0 changes are **visibly user-facing**; they must ship together so the UI never sits in a half-repaired state.

## Out of Scope

- Migrating to Tailwind v4.
- A visual identity / brand redesign (new accent color, logo mark, layout changes).
- Designing a real home page for the `/` route (deferred to a later phase).
- URL-state sync for DataBrowser filters/page/sort (deep-linking) — deferred.
- Introducing a new icon set (lucide-react retained).
- Backend or API changes.
- Virtualizing the data grid (already server-paginated at 20 rows).
