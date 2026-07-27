# Phase 1 — Project Scaffolding: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Health check round-trip (direct)

```bash
# Terminal 1: start backend
cd ykmmgmt/backend
conda activate ykmmgmt   # or: source .venv/Scripts/activate
uvicorn main:app --reload --port 8000

# Terminal 2: test
curl http://localhost:8000/api/health
```

**Expected:** `{"status":"ok"}` with HTTP 200.

---

## Gate 2 — Health check round-trip (via Vite proxy)

```bash
# Terminal 1: start backend (same as above)

# Terminal 2: start frontend
cd ykmmgmt/frontend
npm run dev

# Terminal 3: test proxy
curl http://localhost:5173/api/health
```

**Expected:** `{"status":"ok"}` with HTTP 200 — proves Vite proxy routes `/api/*` correctly.

---

## Gate 3 — Frontend displays health status

Open `http://localhost:5173` in a browser.

**Expected:** A page rendering the backend health status. The TanStack Query hook shows the `{"status":"ok"}` payload. Loading skeleton appears briefly, then the result. No console errors. The layout adapts to viewport width — centered card uses full width on narrow screens and is constrained (`max-w-sm`) on wider screens.

---

## Gate 4 — Responsive viewport meta and breakpoints

Open `http://localhost:5173` in a browser. Resize the browser window from desktop width down to 375px (mobile).

**Expected:** The card layout remains usable at all widths — content does not overflow or clip. The `<meta name="viewport">` tag is present in `index.html`. Tailwind responsive breakpoint classes are available and functional.

---

## Gate 5 — Backend linting passes

```bash
cd ykmmgmt/backend
ruff check .
```

**Expected:** Zero errors, zero warnings. Exit code 0.

---

## Gate 6 — Frontend linting passes

```bash
cd ykmmgmt/frontend
npm run lint
```

**Expected:** Zero errors, zero warnings. Exit code 0.

---

## Gate 7 — Vitest tests pass

```bash
cd ykmmgmt/frontend
npm run test
```

**Expected:** Zero test failures. All suites pass. Exit code 0.

---

## Gate 8 — Backend tests pass

```bash
cd ykmmgmt/backend
pytest tests/ -v
```

**Expected:** All tests pass, zero failures.

---

## Gate 9 — Clean bootstrap

Delete `node_modules/`, `.venv/`, and follow the root `README.md` quick-start from scratch. Both services must start and pass Gates 1–3 without any undocumented steps.

---

## Merge Checklist

- [x] All 9 gates pass on a clean checkout
- [x] `README.md` at repo root has accurate prerequisites and quick-start instructions
- [x] `.gitignore` covers Python, Node, IDE, and OS artifacts
- [x] No secrets, credentials, or environment-specific paths are committed
- [x] `requirements.txt` and `requirements-dev.txt` are present and pinned
- [x] `package.json` has `dev`, `build`, `lint`, `format`, `test`, `test:watch` scripts defined
- [x] `ruff.toml` configured with py312 target
- [x] `.eslintrc.cjs` and `.prettierrc` configured
- [x] `tsconfig.json` with `@/*` path alias
- [x] `vite.config.ts` with proxy + Vitest test block
- [x] `tailwind.config.js` and `postcss.config.js` with shadcn/ui theme
- [x] Responsive viewport meta tag in `index.html`