# Phase 16 — Welcome Page (Particle Splash): Requirements

## Scope

A public, standalone welcome page shown before login. A luminous particle spiral assembles "YKM" plus a cat-head silhouette on a pure-black background (inspired by OpenAI's release-page hero), then settles into a calm idle. A sparse field of dim, slowly drifting particles fills the rest of the viewport, giving a cosmos-like backdrop. The only on-screen UI is the particle art and a single "进入平台" CTA that leads to `/login` — no headline or tagline text. The glyph can also be dragged to rotate for a full 360° inspection — particle flow is suspended during the drag — and springs back face-on when released.

This is a separate, beyond-core feature: self-contained and lazy-loaded so it never touches the main app bundle, auth logic, or data. Hero splash only.

## Context (from mission.md)

YKMMgmt is an internal business tool that unifies scattered data into a single live dashboard. While the welcome page is not a data feature, it is the first thing a team member sees — a polished, branded entry point reinforces the product's identity (云客猫 → the "YKM" + cat mark) and sets a quality bar before the user reaches the working dashboard.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Render engine | Three.js `Points` + custom glow shader + `UnrealBloomPass` | Most faithful to the reference look (real GPU bloom, thousands of glowing particles, smooth 60fps); lazy-loaded so the main bundle is unaffected |
| Glyph source | Offscreen 2D canvas sampling | Font-agnostic; "YKM" text (Geist) and the cat-head `Path2D` share one ink-sampling pipeline |
| Cat glyph | Filled silhouette, two pointed ears, eye cut-outs | Reads clearly at particle scale; matches the glowing aesthetic; 云客猫 brand mascot |
| On-screen copy | Particle art + single CTA only | Most minimal; the glyph carries the brand |
| Motion | Assemble once (~2.5s), then idle | Calm ambient motion (slow rotation, shimmer); not a distracting loop |
| Mouse interaction | Particles flow with the cursor, then spring back | Matches the reference page: moving the mouse across the particles displaces them along the direction of movement, then they ease back to their home positions; implemented CPU per-particle with a spring-return, reusing the assemble's home-position system |
| Drag-to-rotate | Full-360° extruded relief; flow suppressed while dragging; spring home on release | Lets the user inspect the mark from any aspect; extruding the sampled ink into depth layers avoids the flat cloud collapsing edge-on; suspending hover-flow during the drag keeps the two pointer semantics from competing; spring-home matches the piece's existing return language |
| Ambient cosmos | Sparse field of dim drifting particles behind the glyph | A very sparse scatter of faint, slowly drifting particles fills the viewport around/behind the main "YKM + cat" body, giving a cosmos-like depth without competing with the glyph |
| Performance posture | Max fidelity always | Full particle count/effects on every device; only fall back when WebGL is unavailable |
| Particle color | Ice-white / pale-blue on black | Matches the reference aesthetic; clean and premium |
| Placement | Standalone public `/welcome`, full flow | Realizes "welcome page before login"; logged-out `/` → `/welcome`, logout → `/welcome` |

## Constraints

- All UI text in Chinese per project convention (the CTA).
- Three.js must stay isolated to the lazy `/welcome` chunk — the main app bundle and dashboard performance must be unaffected.
- Must not break the existing auth flow: deep links still redirect to `/login` preserving `from`; already-logged-in users never see the splash.
- WebGL-unavailable browsers get a static black splash + CTA (never a blank page).
- Full WebGL resource disposal on unmount to avoid GPU memory leaks.
- Frontend stack per tech-stack.md: React 18, TypeScript, Vite, Vitest + RTL as the validation gate.

## Out of Scope

- A fuller marketing/landing page (headline block, scroll sections, feature copy).
- Looping assemble/scatter animation or replay control.
- Per-device particle scaling, DPR capping, or reduced-motion simplification (max fidelity always; only a WebGL-absent fallback).
- Any backend, auth, or data changes.
- Dark-mode theming of the splash (it is always black by design).
