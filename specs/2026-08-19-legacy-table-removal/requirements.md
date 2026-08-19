# Phase 11 — Legacy Business Table Removal & System Reset: Requirements

## Scope

Remove the three hardcoded legacy business tables (退费单, 服务退款工单, 钱包提现操作) and all table-specific cleansing pipelines from the system. The end state is a fully generic data platform where:

- Zero business tables exist on a fresh database
- All business tables are created dynamically via Schema Manager
- The import pipeline runs general cleaning only (no table-specific rules ship with the system)
- No seed script or legacy sample data files remain

Explicitly in scope:
- Single Alembic migration handling both table drops and dependent-object cleanup
- Deletion of all code references (models, registry entries, hardcoded constants)
- Deletion of table-specific cleansing rule modules
- Deletion of `seed.py` and legacy CSV files
- Test updates using dynamic Schema Manager fixtures

## Context (from mission.md)

YKMMgmt is an internal business tool for financial and operational data management. It serves as a centralized hub where teams can monitor key business metrics, ingest data from diverse external sources, and make data-driven decisions. The original design was built around three specific business tables; this phase completes the transition to a truly generic platform that can accommodate any business table shape without code changes.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Dependent object handling | Hard delete with CASCADE | User confirmed full reset; no archival needed |
| Migration strategy | Single migration with CASCADE | Atomic, reversible via downgrade, no partial states |
| Test fixture strategy | Dynamic Schema Manager fixtures | Tests exercise the real API surface, ensuring Schema Manager works end-to-end |
| Legacy CSV files | Delete (not archive) | User confirmed removal; files are sample data, not production data |
| Seed script | Delete entirely | No longer needed; users create tables and import via UI |

## Constraints

- The general architecture must not break: Schema Manager → data source → cleaning pipeline → database flow must work for any dynamically created table
- `table_specific/__init__.py` registry must remain functional (empty registry = no rules)
- All existing tests must pass after updates
- Frontend must show zero tables on first launch
- Backend must start without import errors or registry warnings

## Out of Scope

- Creating new business tables to replace the legacy ones
- Building a generic rule engine for table-specific cleansing (code-level registration remains the pattern)
- Migrating legacy data to new tables (data is discarded, not migrated)
- UI changes beyond removing references to deleted tables
- Backup/archival of legacy data before deletion
