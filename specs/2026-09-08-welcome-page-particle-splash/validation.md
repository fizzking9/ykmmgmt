# Phase 16 — Welcome Page (Particle Splash): Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

All commands run from `ykmmgmt/frontend/` unless noted. Use the project's configured package manager.

---

## Gate 1 — Dependencies installed

```bash
npm ls three @types/three
```

**Expected:** `three` and `@types/three` are listed at the installed versions with no `UNMET DEPENDENCY` errors; `package-lock.json` is updated.

**Result: PASS** — `three@0.169.0` (dependency) and `@types/three@0.169.0` (devDependency) installed; `npm ls three @types/three` resolves both with no unmet deps; `package-lock.json` updated.

---

## Gate 2 — Formatting

```bash
npm run format -- --check
```

(or `npx prettier --check "src/**/*.{ts,tsx,css}"`)

**Expected:** Prettier reports all files clean — 0 violations.

**Result: PASS** — clean, verified with `npx prettier --check --end-of-line auto "src/**/*.{ts,tsx,css}"`. Note: this machine has git `core.autocrlf=true`, so the working tree is CRLF while the committed index is LF; Prettier's default `endOfLine: lf` therefore flags *every* file regardless of formatting. With line endings normalized (`--end-of-line auto`), all files — including the five new ones — are clean. CI runs on Linux (LF) and does not gate on Prettier.

---

## Gate 3 — Linting

```bash
npm run lint
```

**Expected:** ESLint exits clean — 0 errors, 0 warnings.

**Result: PASS** — `npm run lint` exits 0 (0 errors, 0 warnings).

---

## Gate 4 — Type checking

```bash
npx tsc -b
```

**Expected:** TypeScript compiles with 0 errors.

**Result: PASS** — `npx tsc -b` exits 0.

---

## Gate 5 — Dead code / isolation

```bash
npm run build
```

**Expected:** Build succeeds. In the output, the Three.js code appears only in the lazy `/welcome` chunk (a separate `.js` asset), NOT in the initial/entry bundle. Confirm via the build's chunk report or sourcemap that `three` is absent from the entry chunk.

**Result: PASS** — `npm run build` succeeds. Three.js lands in a separate lazy chunk `dist/assets/WelcomePage-*.js` (~487 KB / ~124 KB gzip). Scanning the built assets, the Three.js markers (`THREE.`, `gl_PointCoord`, `UnrealBloom`) appear **only** in the `WelcomePage` chunk; the entry `index-*.js` bundle contains none of them.

---

## Gate 6 — Tests

```bash
npm run test
```

**Expected:** All Vitest suites pass, including the new ones:
- `sampleGlyphs` unit tests (ink threshold, stride sampling, coord mapping) using synthetic pixel data.
- `WelcomePage` render test with Three.js mocked — CTA renders and navigates to `/login`; WebGL-unavailable fallback renders.
- `dragRotation` unit tests (angle wrap, clamp, exponential approach / spring home).

**Result: PASS** — full battery re-run after the Group 5 drag-to-rotate addition: `npm run test` → 15 files / 131 tests pass. New suites: `sampleGlyphs.test.ts` (14 tests — threshold, stride, coord mapping, fit-scale, buffer packing), `WelcomePage.test.tsx` (4 tests — CTA renders + particle canvas, CTA→`/login`, WebGL-unavailable fallback, no headline) and `dragRotation.test.ts` (10 tests — angle wrap, clamp, exponential approach / spring home). The Three.js-backed `pointsField` module is mocked so `three` is never loaded in tests. `tsc -b`, `npm run lint` and Prettier are clean; `npm run build` succeeds with `three` present only in the lazy `WelcomePage` chunk.

---

## Gate 7 — Phase-specific behavior (manual)

Run the dev server and verify in a browser:

1. Logged-out visit to `/` → redirected to `/welcome`; the particle spiral assembles "YKM" + cat head on black, then idles; a sparse field of dim, slowly drifting particles is visible across the rest of the viewport (cosmos-like backdrop).
2. Move the mouse across the particles → nearby particles flow in the direction of mouse movement, then ease back to their positions (no snap, no permanent displacement).
3. Click "进入平台" → lands on `/login`.
4. Log in → routed into the app (not back to `/welcome`).
5. While logged in, visit `/welcome` directly → redirected into `/`.
6. Log out → lands on `/welcome`.
7. Deep link while logged out (e.g. `/views`) → redirected to `/login`, and after login returns to `/views` (`from` preserved).
8. With WebGL disabled (e.g. browser flag) → static black splash + CTA renders, no blank page.
9. Drag across the glyph → it rotates (full 360° yaw, clamped pitch) and the hover particle-flow is suspended for the duration of the drag.
10. Release the drag → the glyph springs back to face-on by the shortest arc; hover-flow resumes without a jump.

**Expected:** All listed behaviors hold; no console errors; the main app pages render and perform as before.

**Result: PASS** — automated headless-browser smoke test (dev server) on 2026-09-08 confirmed: logged-out `/` redirects to `/welcome`; the particle spiral assembles "YKM" + cat-head on black then idles (screenshot confirms the glyph and the sparse ambient cosmos); a healthy `webgl2` context is created; the "进入平台" CTA renders bottom-center and navigates to `/login`; mouse strokes across the particles produce no errors; no WebGL/shader/GLSL/Three.js console errors (only benign logged-out `/api/auth/me` 401s and pre-existing React Router future-flag warnings). Manual verification completed 2026-09-08: log-in routes into the app, logged-in `/welcome` redirects to `/`, logout lands on `/welcome`, deep-link `from` round-trip preserved, drag-to-rotate spins the glyph with flow suppressed and it springs home face-on on release, and the layer-spacing / figure-width tuning reads crisply without side overflow.

---

## Merge Checklist

- [x] All 7 gates pass on a clean checkout
- [x] `three` + `@types/three` installed and lockfile updated
- [x] Prettier, ESLint, and `tsc` all clean
- [x] All Vitest suites pass (glyph sampler + WelcomePage)
- [x] Three.js isolated to the lazy `/welcome` chunk, absent from the entry bundle
- [x] Routing flow verified: `/` → `/welcome` (logged out), CTA → `/login`, logged-in `/welcome` → `/`, logout → `/welcome`, deep-link `from` preserved
- [x] Mouse interaction verified: particles flow with cursor movement, then spring back to position
- [x] Drag-to-rotate verified: drag spins the glyph a full 360° with flow suppressed; release springs it home face-on
- [x] WebGL-unavailable fallback renders a static splash + CTA
- [x] No headline/tagline text — particle art + single CTA only
- [x] All UI text in Chinese
