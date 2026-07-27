# Phase 1 — Project Scaffolding: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Backend skeleton

1. Create `ykmmgmt/backend/` directory structure
2. Initialize Python virtual environment (`python -m venv .venv`)
3. Install FastAPI, uvicorn, Pydantic v2 via pip
4. Create `requirements.txt` (pinned) and `requirements-dev.txt` (Ruff, httpx, pytest)
5. Create `main.py` with a single `GET /api/health` endpoint returning `{"status": "ok"}`
6. Add CORS middleware (allow localhost origins for dev)
7. Confirm backend starts with `uvicorn main:app --reload` and responds on `http://localhost:8000`

## Group 2 — Frontend skeleton

1. Scaffold React + TypeScript + Vite project in `ykmmgmt/frontend/` via `npm create vite@latest`
2. Install dependencies: React Router v6, TanStack Query, Tailwind CSS, shadcn/ui, Vitest, @testing-library/react, @testing-library/jest-dom, jsdom
3. Initialize shadcn/ui (creates `components.json`, `src/lib/utils.ts`)
4. Configure Tailwind CSS with shadcn/ui preset and responsive breakpoints
5. Create a single-page app that calls `GET /api/health` and displays the response
6. Use responsive layout: full-width on mobile, constrained card on desktop
7. Use TanStack Query for the API call with loading/error/success states
8. Apply minimal shadcn/ui styling (Card component wrapping the health status)

## Group 3 — Dev tooling & integration

1. Configure Vite proxy: `vite.config.ts` routes `/api/*` → `http://localhost:8000`
2. Add `package.json` scripts: `dev`, `build`, `lint`, `format`, `test`, `test:watch`
3. Set up ESLint with TypeScript and React plugins
4. Set up Prettier with consistent config
5. Set up Ruff for backend linting (`pyproject.toml` or `ruff.toml`)
6. Create root `.gitignore` (Python, Node, IDE, OS files)
7. Create root `README.md` with:
   - Project overview (one-liner from mission.md)
   - Prerequisites (Python 3.12+, Node 20+)
   - Quick-start: two terminals — `uvicorn` and `npm run dev`

## Group 4 — End-to-end verification

1. Start backend (`uvicorn main:app --reload` on port 8000)
2. Start frontend (`npm run dev` on port 5173)
3. Verify: browser at `http://localhost:5173` shows the health status from the backend
4. Verify: `curl http://localhost:8000/api/health` returns `{"status":"ok"}`
5. Verify: `curl http://localhost:5173/api/health` also returns `{"status":"ok"}` (proxy works)
6. Run `ruff check .` in backend — zero errors
7. Run `npm run lint` in frontend — zero errors
8. Run `npm run test` in frontend — all tests pass, zero failures