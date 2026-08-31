# Phase 12 — Auth & Multi-User: Requirements

## Scope

Deliver a complete JWT-based authentication and authorization layer for YKMMgmt, plus an admin user-management UI. Concretely:

- **User model & seeding** — a `users` table (username, bcrypt password hash, role, active flag), Alembic migration, and an idempotent seed script that creates the initial root (super admin) from `.env` credentials. No self-registration.
- **Auth API** — login, logout, token refresh, and current-user endpoints. Tokens are delivered as httpOnly cookies; access tokens live 2 hours, refresh tokens 7 days with rotation.
- **Full lockdown** — every API endpoint (except `GET /api/health`) and every frontend page requires authentication. This is an internal tool; there is no anonymous access.
- **Three-level role hierarchy** — `root` (L1, super admin: all rights, creates admins and users; seeded initially, never assignable via API), `admin` (L2: all operational rights — imports, schema management, all mutations — but can only create/manage users), and `user` (L3: read-only — dashboards, visualizations, views, data browsing). Role enforcement is authoritative on the server (403 on forbidden operations); the frontend merely hides admin-only UI.
- **User-management UI (hierarchy-aware)** — root can list all accounts and create/manage admins and users; admins can list and create/manage only user accounts (root accounts hidden, other admins untouchable). Password resets, role changes, and activate/deactivate follow the same hierarchy. Self-demotion/self-deactivation is blocked for everyone; the seeded root account cannot be deactivated or demoted at all.
- **Frontend auth flow** — `AuthContext` above the router, login page (Chinese UI), route guards, silent refresh-and-retry on 401, logout control in the app shell.

## Context (from mission.md)

YKMMgmt is an internal business tool whose mission explicitly includes "Keep it internal — designed for team use within the organization, with role-based access where needed." Until now the app has been fully open; this phase delivers on that mission point by ensuring only authorized team members can access the dashboard, and that destructive capabilities (schema changes, imports, deletions) are restricted to admins while the broader team can still view metrics.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Token storage | httpOnly cookies (`access_token`, `refresh_token`), `SameSite=Lax`, configurable `Secure` flag | Immune to XSS token theft; no token handling in JS; fits same-origin SPA + `/api` proxy |
| Access token lifetime | 2 hours | User-specified modification of the standard 30-min default — fewer interruptions for an internal tool while still bounded |
| Refresh token lifetime | 7 days, rotated on each refresh | Balances convenience and security; rotation limits replay window |
| Password hashing | bcrypt via `passlib` | Mature, widely used, slow-by-design; `passlib[bcrypt]` is the standard FastAPI pairing |
| JWT library | `python-jose[cryptography]` | Standard FastAPI JWT choice, small dependency |
| Route protection | Full lockdown — all API endpoints and all pages require auth; only `GET /api/health` stays public | Internal tool; no anonymous surface; health check stays open for uptime probes |
| Role model | Three levels: `root` (L1) > `admin` (L2) > `user` (L3, read-only) | User-specified hierarchy; separates system ownership (root) from day-to-day administration (admin) and consumption (user) |
| Root provisioning | Seeded from `.env` only; the `root` role can never be assigned via the API | Exactly one super-admin lineage; prevents privilege escalation through the UI |
| Creation rights | Root creates admins and users; admin creates only users | Hierarchy flows downward only |
| Role enforcement | Server-side authoritative (401/403); frontend hides admin UI as a courtesy | Client-side hiding alone is never security; server checks every request |
| User creation | User-management UI for root and admin (beyond the original roadmap) + seed script for root | User-selected scope extension; no self-registration |
| Self-protection guard | Nobody can modify/deactivate/demote their own account (409); the seeded root account is fully immutable via the API | Prevents accidental lockout and protects the recovery account |
| Login page copy | Chinese UI text per project convention | Consistent with the rest of the app |
| 401 handling | Silent `POST /api/auth/refresh` then retry once; on failure redirect to `/login` | Seamless UX across the 2-hour access-token boundary |

## Constraints

- **Dependencies**: adds `passlib[bcrypt]` and `python-jose[cryptography]` to the backend; no new frontend dependencies expected.
- **Config**: `secret_key`, `root_username`, `root_password` must come from `.env` (no hardcoded defaults); `.env.example` updated accordingly. Docker/Phase 13 compatibility — everything is env-driven, no extra infra services.
- **Existing tests**: full lockdown breaks every existing backend test unless `conftest.py` fixtures authenticate; updating fixtures is part of the work, and the whole suite must stay green.
- **Alembic**: one new migration for the `users` table; must not interfere with the runtime-migration mechanism used by Schema Manager.
- **Vite proxy**: cookies flow through the existing `/api` dev proxy; `SameSite=Lax` works because frontend and API are same-origin in both dev (proxy) and prod (Nginx).
- **Risk — lockout**: a misconfigured deployment without seeded root credentials leaves the app inaccessible; the seed script must be idempotent and documented in the spec/README follow-up. The immutable root account is the recovery path if all admins are deactivated.
- **Risk — cookie vs proxy**: if `Secure` is forced on in plain-HTTP dev, cookies won't stick; the flag must be configurable (off in dev, on in prod).

## Out of Scope

- Self-registration / password reset by email (no mail infrastructure)
- OAuth / SSO / LDAP integration
- Fine-grained permissions beyond the three-level hierarchy (per-view, per-dashboard ACLs)
- Multiple root accounts or root delegation
- Session management UI (list/revoke active sessions)
- Audit logging of user actions
- Rate limiting / brute-force lockout on login (acceptable risk for an internal tool behind the LAN; revisit at deployment)
- Multi-tenancy
