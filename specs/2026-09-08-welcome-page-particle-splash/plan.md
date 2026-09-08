# Phase 16 — Welcome Page (Particle Splash): Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Dependencies & glyph sampling

1. Add `three` and `@types/three` to `ykmmgmt/frontend/package.json` (dependencies / devDependencies respectively); run install and confirm the lockfile updates.
2. Create `src/lib/particles/sampleGlyphs.ts` — a pure module that:
   - Draws the text `"YKM"` in Geist (await `document.fonts.ready` before sampling) and a cat-head `Path2D` (rounded skull + two pointed ears + two eye cut-outs as negative space) onto an offscreen 2D canvas.
   - Reads pixels and samples "ink" positions into a flat `Float32Array` of home coordinates, using a shared pipeline for both the text and the shape.
   - Maps canvas coords to centered world coords and scales the whole group to fit a target viewport.
   - Exposes the pure point-selection logic (ink threshold, sampling stride, coord mapping) as separately testable functions that take raw pixel data, so they can be unit-tested without a real canvas.

## Group 2 — Particle scene

3. Create `src/lib/particles/pointsField.ts` — builds and owns the Three.js scene:
   - `THREE.Points` geometry from the sampled home positions; per-particle spiral spawn positions.
   - A separate, very sparse ambient `THREE.Points` field of dim particles scattered across the whole viewport behind the main glyph, drifting slowly (cosmos-like backdrop); these do not assemble and are not displaced by the mouse.
   - Custom glow shader (point size attenuation, soft radial falloff, ice-white/pale-blue color), additive blending, transparent on a black clear color.
   - `EffectComposer` + `RenderPass` + `UnrealBloomPass` for the luminous bloom.
   - Animation loop: spiral assemble (~2.5s, per-particle stagger) → idle state (slow group rotation, per-particle shimmer). Assemble once, then idle — no loop/replay.
   - Mouse interaction: track cursor world position + per-frame velocity; displace particles within a radius along the mouse-movement vector (closer = stronger push), then apply a per-particle spring-return (velocity + spring toward home, with damping) so they ease back — reusing the assemble's home-position system. CPU per-particle update written to the position buffer each frame.
   - WebGL support detection; expose a flag so the caller can render a static fallback.
   - A `dispose()` that releases geometry, material, composer, and renderer.
4. Create `src/components/welcome/ParticleCanvas.tsx` — a React wrapper that sizes the canvas to its container, initializes `pointsField` on mount, drives `requestAnimationFrame`, handles resize, and calls `dispose()` on unmount.

## Group 3 — Welcome page & routing

5. Create `src/pages/WelcomePage.tsx` (lazy-loaded): full-screen black background, the `ParticleCanvas` filling the viewport, and a single primary CTA button "进入平台" that navigates to `/login`. No headline or tagline text — the particle glyph carries the brand. When WebGL is unavailable, render a static black splash + the same CTA.
6. Update `src/App.tsx`:
   - Add a public `/welcome` route rendered via `React.lazy` + `Suspense` (keeps Three.js out of the initial bundle).
   - In `RequireAuth`, redirect logged-out visits to `/` to `/welcome`; deep links to other paths still go to `/login` preserving `from`.
   - On `/welcome`, redirect already-logged-in users into `/`.
7. Update `src/components/layout/Sidebar.tsx`: logout navigates to `/welcome` instead of `/login`.

## Group 4 — Tests & validation

8. Unit-test the pure point-selection logic in `sampleGlyphs.ts` (ink threshold, stride sampling, coord mapping) with synthetic pixel data — no real canvas required.
9. Render-test `WelcomePage` with Three.js mocked: assert the CTA renders and navigates to `/login`, and that the WebGL-unavailable fallback renders.
10. Confirm `npm run lint`, `npm run test`, and `npm run build` are all green; verify the Three.js code is isolated to the lazy `/welcome` chunk in the build output.

## Group 5 — Drag-to-rotate inspection (added after the initial spec)

11. Extend `pointsField.ts` to extrude the sampled glyph into a volumetric relief (per-ink-point depth layers + slight xy jitter) so the mark reads as a solid from any angle rather than a paper-thin card.
12. Add drag-to-rotate: pointer-down enters drag mode with pointer capture; drag deltas accumulate unbounded yaw + clamped pitch onto the glyph group, composed over the idle sway; particle flow is suppressed while dragging; on release the yaw wraps to the short arc and both offsets spring home to face-on. Cursor shows grab/grabbing; the canvas sets `touch-action: none`.
13. Extract the pure rotation math (`wrapAngle`, `clamp`, `stepToward`) into `src/lib/particles/dragRotation.ts` and unit-test it in `src/test/dragRotation.test.ts`.
