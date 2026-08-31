# Phase 12 — Auth & Multi-User: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — User Model & Database Foundation

1. Create `User` SQLAlchemy model in `app/models/user.py`: `id` (PK), `username` (unique, indexed), `password_hash`, `role` (`root` | `admin` | `user`), `is_active` (boolean, default true), `created_at`, `updated_at`. Register in `app/models/__init__.py`.
2. Generate and run Alembic migration creating the `users` table with a unique constraint on `username`.
3. Add auth settings to `app/core/config.py`: `secret_key` (JWT signing), `access_token_expire_minutes` (default 120 — 2 hours), `refresh_token_expire_days` (default 7), `root_username` / `root_password` (seed credentials, no defaults — must come from `.env`). Update `.env.example` with the new variables.
4. Add dependencies to `requirements.txt`: `passlib[bcrypt]` for password hashing, `python-jose[cryptography]` for JWT. Update `requirements-lock.txt`.
5. Create a seed script (`scripts/seed_root.py` or equivalent) that creates the initial root (super admin) user from `root_username` / `root_password` env vars if no root exists. Idempotent — safe to run repeatedly.

## Group 2 — Backend Auth Core

6. Create `app/services/auth.py`: password hashing/verification helpers (bcrypt via passlib), JWT encode/decode for access and refresh tokens (token type claim `access` | `refresh`, subject = user id, expiry from settings).
7. Create `app/routers/auth.py`:
   - `POST /api/auth/login` — accepts username/password, verifies credentials and `is_active`, sets httpOnly cookies (`access_token`, `refresh_token`; `Secure` flag configurable, `SameSite=Lax`, path `/`), returns user profile `{id, username, role}`.
   - `POST /api/auth/refresh` — reads `refresh_token` cookie, validates it, issues a new access token cookie (and rotates the refresh token), returns user profile.
   - `POST /api/auth/logout` — clears both cookies.
   - `GET /api/auth/me` — returns the current user's profile from the access token.
8. Create FastAPI dependencies in `app/core/security.py` (or `app/api/deps.py`): `get_current_user` (reads `access_token` cookie, decodes JWT, loads active user, 401 on failure), `require_admin` (403 unless role is `admin` or `root`), `require_root` (403 unless role is `root`). Return 401 with a consistent error body so the frontend can trigger re-login.
9. Register the auth router in `main.py`.

## Group 3 — Protect Existing API Endpoints

10. Apply `get_current_user` to **all** existing routers (`tables`, `views`, `visualizations`, `dashboards`, `imports`, `schema`) — every endpoint requires a valid access token.
11. Apply `require_admin` (admin or root) to all mutating endpoints: POST/PUT/DELETE on views, visualizations, dashboards, imports (upload), and **all** schema management endpoints. Users (L3) keep read-only GET access.
12. Verify `GET /api/health` remains public (no auth) for uptime checks.

## Group 4 — User Management API (Hierarchy-Enforced)

13. Create `app/routers/users.py` (all endpoints require at least `require_admin`):
    - `GET /api/users` — list users. Root sees all users; admin sees only admins and users (root accounts hidden).
    - `POST /api/users` — create a user with role validation by hierarchy: **root can create admins and users; admin can create only users; the `root` role can never be assigned through the API.** 409 on duplicate username.
    - `PUT /api/users/{id}` — update role and/or reset password, with the same hierarchy rules: root may change roles between `admin` and `user` (never to `root`); admin may only manage `user` accounts and cannot touch other admins or root.
    - `PUT /api/users/{id}/status` — activate/deactivate a user, same hierarchy rules (admin can deactivate users only; root can deactivate admins and users). Deactivating invalidates future token use (user lookup enforces `is_active`).
    - Guards: nobody can modify, deactivate, or demote their own account (409); the seeded root account cannot be deactivated, demoted, or deleted via the API (409).
14. Pydantic schemas in `app/schemas/user.py`: `UserCreate`, `UserUpdate`, `UserOut`, `LoginRequest`, `UserProfile` — role field as a literal enum (`admin` | `user` on input; `root` never accepted), username/password length validation.

## Group 5 — Frontend Auth Foundation

15. Create `AuthContext` (`src/contexts/AuthContext.tsx`) above the router: holds current user `{id, username, role}` + loading state; on mount calls `GET /api/auth/me`; exposes `login()`, `logout()`, `isAdmin` (admin or root), and `isRoot`.
16. Update the API client (`src/lib/`) to send cookies (`credentials: 'include'` / axios `withCredentials`) and, on a 401 response, attempt one silent `POST /api/auth/refresh` then retry the original request; if refresh fails, clear auth state and redirect to `/login`.
17. Create `LoginPage` (`src/pages/LoginPage.tsx`): centered card with username/password inputs, submit button, inline error message on failed login; all UI text in Chinese per project convention. On success, redirect to the originally requested page (or `/`).
18. Add route guards in `App.tsx`: unauthenticated users are redirected to `/login` for every route; `/login` itself is public. While auth state is loading, show a full-page spinner.

## Group 6 — Frontend Role Enforcement & User Management UI

19. Hide/disable admin-only UI for L3 users: sidebar items (Schema Manager, 数据导入, builder pages) hidden; edit/delete buttons on list pages (views, visualizations, dashboards) hidden or disabled. Server-side 403 remains the authoritative enforcement.
20. Add logout control: user menu in the app shell (sidebar footer or header) showing current username + role badge (超级管理员 / 管理员 / 用户), with a 退出登录 action that calls `POST /api/auth/logout` and redirects to `/login`.
21. Create `UsersPage` (`src/pages/UsersPage.tsx`, admin and root only): table of users (username, role badge, status, created date) with actions — 新建用户 (dialog: username, password, role picker), 重置密码, 修改角色, 启用/停用 toggle. The role picker is hierarchy-aware: root sees 管理员/用户 options, admin sees only 用户; admins never see root accounts in the list; the root account row renders without action buttons. All text in Chinese. Sidebar nav item 用户管理 visible to admin and root only.

## Group 7 — Tests

22. Backend tests (`tests/test_auth.py`): login success/failure (wrong password, unknown user, deactivated user), `/me` with valid/expired/missing token, refresh flow issues a new access token, logout clears cookies, password hashing round-trip.
23. Backend tests (`tests/test_authz.py`): unauthenticated requests to protected endpoints return 401; L3 user GET requests succeed; L3 user POST/PUT/DELETE return 403; admin and root mutations succeed.
24. Backend tests (`tests/test_users.py`): hierarchy enforcement — root can create admins and users; admin can create only users (403 when attempting to create admin/root); `root` role is never assignable via API (422/403); admin cannot see or touch root accounts or other admins; duplicate username returns 409; self-modification/self-deactivation returns 409; the seeded root account rejects deactivation/demotion with 409; L3 user gets 403 on all `/api/users` endpoints.
25. Frontend tests: `AuthContext` login/logout flow, route guard redirects unauthenticated users to `/login`, L3 user sees no admin nav items, role picker options differ for root vs admin, 401 → refresh → retry behavior in the API client.
26. Update existing backend test fixtures (`conftest.py`) so all current tests authenticate (seed a test root/admin/user, inject auth cookies) — the full suite must stay green under full lockdown.
