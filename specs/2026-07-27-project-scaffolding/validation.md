# Phase 1 — Project Scaffolding: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — Health check round-trip (direct)

```bash
# Terminal 1: start backend
cd ykmmgmt/backend
source .venv/Scripts/activate   # Windows: .venv\Scripts\activate
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

**Expected:** A page rendering the backend health status. The TanStack Query hook shows the `{"status":"ok"}` payload. Loading skeleton appears briefly, then the result. No console errors.

---

## Gate 4 — Backend linting passes

```bash
cd ykmmgmt/backend
ruff check .
```

**Expected:** Zero errors, zero warnings. Exit code 0.

---

## Gate 5 — Frontend linting passes

```bash
cd ykmmgmt/frontend
npm run lint
```

**Expected:** Zero errors, zero warnings. Exit code 0.

---

## Gate 6 — Clean bootstrap

Delete `node_modules/`, `.venv/`, and follow the root `README.md` quick-start from scratch. Both services must start and pass Gates 1–3 without any undocumented steps.

---

## Merge Checklist

- [ ] All 6 gates pass on a clean checkout
- [ ] `README.md` at repo root has accurate prerequisites and quick-start instructions
- [ ] `.gitignore` covers Python, Node, IDE, and OS artifacts
- [ ] No secrets, credentials, or environment-specific paths are committed
- [ ] `requirements.txt` and `requirements-dev.txt` are present and pinned
- [ ] `package.json` has `dev`, `build`, `lint`, `format` scripts defined