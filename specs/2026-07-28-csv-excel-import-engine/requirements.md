# Phase 3 — CSV & Excel Import Engine: Requirements

## Scope

**Delivered:**
- A unified `POST /api/imports` endpoint accepting `.csv` and `.xlsx` file uploads plus a `target_table` field chosen by the user
- **Pre-cleaning schema validation gate** — before any data processing, file headers are compared against the target table's expected columns using the model's Chinese `comment` attributes; mismatched files are rejected immediately with a detailed diff
- A **common cleaning pipeline** (6 standard steps): whitespace stripping, header normalization, missing value handling, format normalization, deduplication, value validation
- **Table-specific cleaning rules** — each `DataSource` can define custom cleaning steps in its config that run after the common pipeline
- CSV parser (Pandas) and Excel parser (openpyxl) feeding into the same pipeline; Chinese headers are mapped to English column names using the comment mapping from the validation gate
- Cleaned rows stored in the target business table, linked to an `ImportJob` record
- `CleaningReport` returned in the API response: steps executed, rows dropped/modified, warnings per column
- Error handling for malformed files, schema mismatches, unknown target tables, empty files, and unrecoverable rows

**Explicitly out of scope:**
- Upload UI (moved to Phase 4 — App Shell & CSV/Excel Upload UI)
- Scheduled/recurring imports
- API-based or scraped data ingestion (Phase 8)
- Chunked/streaming uploads for large files
- Custom column mapping by the end user

## Context (from mission.md)

YKMMgmt aims to automate ingestion of business data from spreadsheets and CSVs into a unified view. Phase 3 delivers the engine that makes this possible — it is the backbone for all future data import paths (file upload in Phase 4, platform scraping in Phase 8). Every subsequent data-driven phase depends on this pipeline producing clean, validated data in the database.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Target table selection | User specifies `target_table` at upload time using the English table name (e.g., `service_refund_work_orders`). API responses and error messages display Chinese names (服务退款工单, 退费单, 钱包提现操作). | Users know their data structure well. Explicit choice avoids ambiguity and enables cross-checking the file against the intended destination. Chinese display names keep the API approachable for the internal team. |
| Schema validation strategy | Compare file headers to model column **comments** (Chinese), not column names (English) | Source files use Chinese headers (e.g., "工单号", "退款金额"). Every SQLAlchemy model column already has a `comment=` with the Chinese label. No separate mapping config to maintain. |
| Ambiguous comment resolution | Positional tiebreaker — when two model columns share a comment prefix (e.g., "备注" for both `customer_remark` and `internal_remark`), the first occurrence in the file maps to the first matching model column | Deterministic, requires zero config, and matches the real ambiguity found in the sample data. |
| Schema validation timing | Before cleaning — fail fast at the gate | Rejecting early avoids wasting processing cycles on data that can't be imported. Users get immediate, actionable feedback. |
| Cleaning rule configuration | Common pipeline with per-DataSource table-specific overrides | Different business tables have different data problems (e.g., remark column formatting, date conventions). A shared baseline + per-table hooks balances simplicity with flexibility. |
| Invalid row handling | Counted and flagged in cleaning report; **not** stored separately | Keeps the database clean and avoids an error-row table that would need its own schema. Users can review the report and fix the source file. |
| Import execution model | Synchronous — request waits for completion | Simplifies the API and error handling. File sizes for this use case are modest (operational CSVs/Excel). Async/polling can be added later if needed. |
| Parser technology | Pandas for CSV, openpyxl for Excel | Both are already in requirements-lock.txt from Phase 2 seed script. Pandas handles encoding detection and type inference; openpyxl reads `.xlsx` natively. |
| File format support | `.csv` and `.xlsx` only | Explicitly scoped in the roadmap. No `.xls` (legacy), `.json`, or `.tsv`. |

## Constraints

- **Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async, PostgreSQL 16+. Pandas and openpyxl already available.
- **Database:** All cleaned data must end up in existing business tables (`service_refund_work_orders`, `refund_orders`, `wallet_withdrawals`). The `ImportJob` model from Phase 2 is reused as-is.
- **API design:** RESTful conventions — proper HTTP status codes, JSON responses, multipart file upload. `target_table` is a required form field alongside `file`.
- **Column matching:** File headers are in Chinese. The model's `comment=` attributes (also in Chinese) provide the mapping. No separate mapping file needed — the models are the single source of truth.
- **Encoding:** CSV files may use UTF-8, GBK, or GB2312. Auto-detect encoding before parsing.
- **File size:** No hard limit initially, but synchronous model means files should be moderate (operational data, not multi-GB dumps).

## Out of Scope

- Async/background import processing (polling pattern)
- Upload progress via WebSocket or SSE
- Custom column mapping UI — headers must match the target table schema
- Support for `.xls` (legacy Excel), `.json`, `.tsv`, or other formats
- Scheduled imports via cron/APScheduler
- Streaming/chunked upload for very large files
- User-facing upload page (Phase 4)
