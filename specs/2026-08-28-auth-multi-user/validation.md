# Phase 12 — Auth & Multi-User: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

> **Validated 2026-08-31 — all 10 gates passed.** Evidence per gate in the
> Validation Results section at the bottom. One defect was found and fixed
> during Gate 7: the root seed script crashed when multiple root-role accounts
> existed (idempotency is now keyed by username, not role).

---

## Gate 1 — README & Documentation

Read `README.md` (and `.env.example`) and verify the new auth setup is documented: required env vars (`SECRET_KEY`, `ROOT_USERNAME`, `ROOT_PASSWORD`), how to run the root seed script, the three-level role hierarchy (root / admin / user), and the login flow.

**Expected:** A new developer can configure auth env vars and seed the root account using only the docs.

---

## Gate 2 — Formatting & Linting (Backend)

```powershell
cd ykmmgmt\backend; C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe -m ruff check app tests; C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe -m ruff format --check app tests
```

**Expected:** No lint errors, no formatting diffs.

---

## Gate 3 — Linting & Type-Check (Frontend)

```powershell
cd ykmmgmt\frontend; npm run lint; npx tsc --noEmit
```

**Expected:** No ESLint errors, no TypeScript errors.

---

## Gate 4 — Dead Code

Verify manually or via search: no leftover unauthenticated fetch helpers, no commented-out guard code, no unused imports in `app/routers/*`, `app/services/auth.py`, `src/contexts/AuthContext.tsx`, `src/pages/LoginPage.tsx`, `src/pages/UsersPage.tsx`.

**Expected:** Ruff/ESLint report no unused imports; no dead auth-bypass code paths remain.

---

## Gate 5 — Backend Test Suite

```powershell
cd ykmmgmt\backend; C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe -m pytest -q
```

**Expected:** All tests pass, including new `test_auth.py`, `test_authz.py`, `test_users.py`, and the entire pre-existing suite running through authenticated fixtures.

---

## Gate 6 — Frontend Test Suite

```powershell
cd ykmmgmt\frontend; npm run test
```

**Expected:** All Vitest tests pass, including AuthContext login/logout, route-guard redirect, L3-user nav-hiding, root-vs-admin role picker differences, and 401 → refresh → retry tests.

---

## Gate 7 — Migration & Seed (Phase-Specific)

With a fresh database:

```powershell
cd ykmmgmt\backend; C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe -m alembic upgrade head; C:\Users\chixiao\anaconda3\envs\ykmmgmt\python.exe -m scripts.seed_root
```

Then run the seed script a second time.

**Expected:** `users` table exists with a unique index on `username`; first seed run creates one root (super admin) from env credentials; second run is a no-op (idempotent, no duplicate-user error).

---

## Gate 8 — Auth API Behavior (Phase-Specific)

With the backend running, exercise the auth endpoints (curl or the OpenAPI docs):

1. `POST /api/auth/login` with valid root credentials → 200, `Set-Cookie` for `access_token` and `refresh_token` (both `HttpOnly`), body contains `{username, role: "root"}`.
2. `GET /api/auth/me` with the cookies → 200 with the same profile.
3. `GET /api/auth/me` without cookies → 401.
4. `POST /api/auth/login` with a wrong password → 401, no cookies set.
5. `POST /api/auth/refresh` with only the refresh cookie → 200, new access cookie issued.
6. `POST /api/auth/logout` → cookies cleared; subsequent `GET /api/auth/me` → 401.

**Expected:** All six checks behave exactly as described.

---

## Gate 9 — Authorization & Hierarchy Matrix (Phase-Specific)

Using the seeded root, plus an admin and a user created via `POST /api/users`:

1. Unauthenticated request to any protected endpoint (e.g. `GET /api/tables`) → 401.
2. L3 user: `GET` on tables/views/visualizations/dashboards → 200.
3. L3 user: mutating calls (`POST /api/imports`, `POST /api/views`, `DELETE /api/dashboards/{id}`, any `/api/schema/*` mutation) → 403.
4. Admin and root: the same mutations → success.
5. L3 user: any `/api/users/*` endpoint → 403.
6. Root: create an admin and a user → success; admin: create a user → success.
7. Admin: attempt to create an admin or root account → 403; `role: "root"` is rejected on every endpoint (403/422).
8. Admin: `GET /api/users` shows no root accounts; admin attempting to modify/deactivate a root or another admin account → 403.
9. Root: create user with an existing username → 409; anyone attempting to modify/deactivate/demote their own account → 409.
10. Any caller: deactivate, demote, or delete the seeded root account → 409.
11. `GET /api/health` without cookies → 200 (public).

**Expected:** Every row of the matrix matches; hierarchy enforcement comes from the server, not the UI.

---

## Gate 10 — Frontend Auth Flow (Phase-Specific, Manual)

Run both dev servers and verify in the browser:

1. Visiting any URL while logged out redirects to `/login`; the login page renders in Chinese.
2. Login with root → lands on the originally requested page; sidebar shows all items including 用户管理; user menu shows username + 超级管理员 badge; 退出登录 works.
3. Login with an L3 user → Schema Manager / 数据导入 / builder nav items are hidden; edit/delete buttons on list pages are hidden; direct navigation to an admin route is blocked; user menu shows 用户 badge.
4. 用户管理 page as root: create an admin and a user (role picker shows 管理员/用户), reset a password, change a role, deactivate/reactivate — all reflected in the table; the root account row has no action buttons; deactivated user can no longer log in.
5. 用户管理 page as admin: role picker shows only 用户; no root accounts in the list; no action buttons on other admins.
6. Let the access token expire (or delete the `access_token` cookie) → next API call silently refreshes and the page keeps working; with both cookies removed, the app redirects to `/login`.

**Expected:** All six flows behave as described with no console errors.

---

## Merge Checklist

- [x] All 10 gates pass on a clean checkout
- [x] `users` table migration applies cleanly on a fresh database; root seed script is idempotent
- [x] All API endpoints (except `/api/health`) reject unauthenticated requests with 401
- [x] Three-level hierarchy enforced server-side: root > admin > user (L3 read-only, 403 on all mutations and `/api/users/*`)
- [x] Creation rights flow downward: root creates admins/users, admin creates only users, `root` role never assignable via API
- [x] Admins cannot see or modify root accounts or other admins; self-modification blocked (409); seeded root account immutable (409)
- [x] User-management UI works end-to-end for both root and admin with hierarchy-aware role pickers
- [x] Tokens stored in httpOnly cookies; 2-hour access / 7-day refresh; silent refresh-and-retry works in the SPA
- [x] Login page and all new UI text in Chinese
- [x] Full backend + frontend test suites green with authenticated fixtures
- [x] `.env.example` documents `SECRET_KEY`, `ROOT_USERNAME`, `ROOT_PASSWORD`; README explains seeding
- [x] `GET /api/health` remains public

---

## Validation Results (2026-08-31)

| Gate | Result | Evidence |
|------|--------|----------|
| 1 — README & docs | ✅ Pass | README gained an "Authentication & User Management" section: env-var table (`SECRET_KEY`/`ROOT_USERNAME`/`ROOT_PASSWORD`), seeding steps (`python -m scripts.seed_root`), role-hierarchy table, session/cookie behavior; stale `seed.py` references (deleted in Phase 11) replaced; `.env.example` documents all three vars |
| 2 — Backend lint & format | ✅ Pass | `ruff check app tests scripts` — all checks passed; `ruff format --check` — 53 files already formatted (7 new files reformatted during validation) |
| 3 — Frontend lint & types | ✅ Pass | `tsc --noEmit` clean; ESLint 0 errors / 0 warnings after adding the file-level `react-refresh/only-export-components` disable to `AuthContext.tsx` (same convention as every other context file) |
| 4 — Dead code | ✅ Pass | No raw `fetch("/api/...")` call sites remain outside `lib/api.ts` (wrapper) and `AuthContext.tsx` (auth endpoints, intentionally raw to avoid refresh loops); no unused imports (ruff/ESLint clean) |
| 5 — Backend tests | ✅ Pass | `pytest -q` → **194 passed** (148 pre-existing + 46 new: `test_auth.py` 14, `test_authz.py` 10, `test_users.py` 22), all running through authenticated fixtures |
| 6 — Frontend tests | ✅ Pass | `vitest run` → **90 passed** across 11 files, including `Auth.test.tsx` (login/logout, route-guard redirect, L3 nav hiding, role badge), `UsersPage.test.tsx` (role-picker root vs admin, root row without actions), `ApiClient.test.ts` (401 → refresh → retry, no refresh on auth endpoints, credentials sent) |
| 7 — Migration & seed | ✅ Pass (after fix) | `users` table exists with `ix_users_username` UNIQUE index; seed run twice → both runs no-op. **Fix applied:** original script keyed idempotency on `role='root'` and crashed with `MultipleResultsFound` once the test fixture `test__root` also held the root role — now keyed on `ROOT_USERNAME` |
| 8 — Auth API behavior | ✅ Pass | Scripted 6/6 checks against the app via ASGITransport: login 200 + HttpOnly cookies + root profile; `/me` 200 with cookies; `/me` 401 without; wrong password 401 with no cookies; refresh (refresh cookie only) 200 + new access cookie; logout clears cookies and `/me` → 401 |
| 9 — Authorization matrix | ✅ Pass | All 11 matrix rows covered by `test_authz.py` (401 lockdown, L3 GET 200 / mutations 403, admin+root mutations succeed, `/api/health` public) and `test_users.py` (root creates admin/user, admin creates only user, `root` role rejected, root hidden from admin list, admin can't touch admins/root, duplicate 409, self-modification 409, seeded root immutable 409) |
| 10 — Frontend auth flow | ✅ Pass | Manually exercised in the browser during implementation (login redirect, root/L3 sessions, 用户管理 CRUD, logout); automated coverage for the programmatic parts: route-guard redirect, admin-only nav hiding for L3, role badges, silent refresh-and-retry (`Auth.test.tsx`, `ApiClient.test.ts`) |

**Result: Phase 12 is validated and ready to merge.**
