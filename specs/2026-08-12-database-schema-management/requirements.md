# Phase 10 — Database Schema Management: Requirements

## Scope

Deliver a full in-app Database Schema Manager. Users can inspect every table, create new tables (manually or via CSV inference), edit them (add/drop/modify columns), and delete them — all through the UI, with Alembic migrations generated and applied automatically and no manual SQL. Newly created tables become visible to the Data Browser and View Builder immediately, without a server restart.

The full roadmap scope is implemented in a single phase. The three pre-existing business tables (`refund_orders`, `service_refund_work_orders`, `wallet_withdrawals`) are **inspection-only** — they can be viewed but not edited or deleted through the Schema Manager.

During implementation the scope was extended (on request) beyond the original roadmap items: table/column renaming, foreign keys to unique keys, per-table ingestion settings (upsert key + dedup toggle), authoritative import counter semantics, and upload matching robustness. These are documented in the decisions table and plan groups 9–12 below.

## Context (from mission.md)

YKMMgmt is an internal business tool that unifies data from diverse sources into one consistent, curated PostgreSQL store. Until now the schema was fixed at scaffolding time and every new data shape required a developer to hand-write a model and a migration. This phase removes that bottleneck: the team can model new data directly in the product, keeping the "single source of truth" promise of the backend while making ingestion self-serve. It advances the mission's "automate the boring stuff" goal by eliminating manual migration authoring.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Phase scope | Full scope in one phase | All roadmap items (inspect, create manual + CSV, edit, delete, dynamic registry, full UI) delivered together as one shippable feature. |
| New-table visibility | Runtime registry refresh | After the migration runs, register the new model into `schema_validator._MODEL_REGISTRY` and `TABLE_DISPLAY_NAMES` at runtime so the table appears in Data Browser / View Builder with no restart. |
| Operations on existing tables | New tables only; 3 business tables inspection-only | Protects production business data from accidental schema changes while still allowing full visibility. |
| Column type system | Roadmap 6 types + commonly used additions | `String(N)`, `Text`, `Integer`, `BigInteger`, `Numeric(12,2)`, `Boolean`, `DateTime`, `Date`, `JSON` — covers the common cases the base six miss. |
| Schema changes persistence | Auto-generated Alembic migrations | Every create/edit/delete writes and applies a migration so history is captured and reproducible. |
| Dependency safety | Warn on dependent views/visualizations | Before dropping a table/column, surface references from saved views/visualizations so users understand the blast radius. |
| Column metadata | Description + default value per column | Stored in a `column_meta` table; defaults become server defaults and apply when an upload omits the column. |
| Renaming | Table name + display name + column rename supported | English rename is a physical `ALTER TABLE ... RENAME`, blocked when saved views/visualizations embed the old name; display name lives in the table comment. Caveat tooltips on the edit page warn that table names bind cleansing rules and Chinese labels bind upload matching. |
| Foreign keys | May target another table's PK **or unique column** | Matches typical DB tools; the FK picker marks targets as …・主键 / …・唯一. |
| Ingestion settings | Per-table upsert key + dedup toggle in a new `table_meta` table | Upsert key optional (single/composite; defaults to the user PK); dedup can only be disabled when there is no PK, no unique column, and no upsert key; keyless dedup-on tables get a `content_hash` column. Table-specific cleansing rules stay code-level (registered during maintenance) — no UI/API by explicit decision. |
| Import counters | Authoritative four-counter semantics | 新增 = valid row, no match, added; 更新 = matched, ≥1 value changed; 跳过 = matched, identical; 拒绝 = invalid/unwritable. Counters increment only after a successful write; keyed tables get full fetch-compare-write upsert, and partial uploads never null omitted columns. |
| Upload matching | Strict gate: Chinese-label-first matching + clean-file robustness | Every file header must map to a table column and all required columns must be covered, else 422 with missing/unexpected lists; the parser strips multiple UTF-8 BOMs (double-BOM files broke matching). |

## Constraints

- Backend: FastAPI + SQLAlchemy 2.0 (async) + Alembic + Pydantic v2; Pandas for CSV inference (per tech-stack.md).
- Frontend: React 18 + TypeScript + Vite + shadcn/ui + TanStack Query + React Router v6; all UI text in Chinese per project convention.
- Database: PostgreSQL 16+; the dashboard always reads from the curated local DB.
- Table and column names accepted from the UI must be validated as safe SQL identifiers to prevent injection; reserved/system names are rejected.
- The runtime registry must stay consistent with the on-disk migration state; a failed migration must not leave a half-registered table.
- Risk: runtime-generated models must not collide with existing model class names or table names.
- Risk: altering/dropping columns that back saved views or visualizations can break those assets — mitigated by the dependency warning.

## Out of Scope

- Editing or deleting the three pre-existing business tables (inspection-only this phase).
- Row-level data editing inside the Schema Manager (covered by Data Browser for viewing only).
- Index / composite-constraint management beyond single/multi-column unique keys, primary keys, and FKs to PK/unique columns.
- Data seeding as part of table creation — creation still produces an empty table; data lands through the existing import engine (which this phase hardened for dynamic tables: strict matching gate, upsert keys, four counters).
- UI/API for table-specific cleansing rules — kept code-level (registered during maintenance); general cleansing + DB constraints cover new tables early on.
- Multi-step migration rollback UI (Alembic downgrade remains a developer operation).
- Runtime-migration lifecycle management (squash/checkpoint of `runtime_migrations/`) — deferred to Phase 13.

> Note on originally-listed exclusions that were later included: **table and column renaming** was initially out of scope but was pulled in during implementation (with dependency protection and edit-page caveat tooltips).
