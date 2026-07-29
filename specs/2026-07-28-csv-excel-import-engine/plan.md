# Phase 3 — CSV & Excel Import Engine: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — Unified Import Endpoint & Schema Validation Gate

1. Create `POST /api/imports` endpoint accepting multipart file upload (`.csv`, `.xlsx`) plus `target_table` field using the English table name (e.g., `service_refund_work_orders`); all user-facing messages display Chinese names (服务退款工单, 退费单, 钱包提现操作)
2. Validate uploaded file: extension whitelist, non-empty, not malformed, size under limit
3. Return appropriate HTTP errors for invalid requests (415 unsupported format, 400 malformed file, 413 too large, 422 empty file)
4. Wire into existing `DataSource` — resolve/create which source the import belongs to
5. **Pre-cleaning schema validation gate** — runs BEFORE any cleaning, fails fast:
   - Introspect the target SQLAlchemy model's columns and extract their `comment` attributes
   - Build a `{chinese_comment → english_column_name}` mapping from the model
   - Handle duplicate comments (e.g., two columns with "备注") by positional order: first occurrence in file → first model column with that comment, second → second, etc.
   - Parse only the header row of the uploaded file (cheap — single row read)
   - Compare each file header against the comment mapping
   - Required columns (non-nullable without default): must have a matching header
   - **If mismatch:** reject with HTTP 422, body `{ "target_table": "...", "missing": ["工单号"], "unexpected": ["无关列"], "expected": ["工单号", "SN", ...] }` listing Chinese names
   - **If match:** produce a `column_mapping: {chinese_header → english_column}` dict for the parser to use

## Group 2 — Common Cleaning Pipeline

1. Build a pipeline runner class (`CleaningPipeline`) that accepts a DataFrame and a list of cleaning steps
2. Implement the standard cleaning steps in order:
   - **Strip whitespace** — trim leading/trailing whitespace from all string columns
   - **Normalize column headers** — lowercase, strip, replace spaces with underscores
   - **Handle missing values** — drop completely blank rows; drop entirely empty columns; fill or drop per configurable strategy for partial nulls
   - **Normalize formats** — parse date columns to ISO format, strip currency/number formatting, detect and fix encoding issues
   - **Deduplicate rows** — identify and remove exact duplicate rows
   - **Validate values** — check against expected ranges/types; flag rows that exceed bounds or have wrong types
3. Produce a `CleaningReport` with: rows dropped (detail per step), rows modified, warnings per column, total rows before/after
4. Support running the pipeline step-by-step and in full — each step is a callable that receives and returns a DataFrame + report accumulator

## Group 3 — Table-Specific Cleaning Rules

1. Design a per-`DataSource` configuration for table-specific cleaning steps (stored in `DataSource.config` JSON)
2. Implement a registry where table-specific rules can be defined as named cleaning functions
3. Merge pipeline: run common steps first, then apply any table-specific rules from the DataSource config
4. Table-specific cleaning report entries are tagged with the rule name in the report for traceability

## Group 4 — CSV & Excel Parsers

1. **CSV parser** using Pandas: `pd.read_csv()` with encoding detection (`chardet` or `charset_normalizer`), infer types
2. **Excel parser** using openpyxl: read all sheets by default (or configurable sheet name), map first row to headers, infer types
3. Apply `column_mapping` from Group 1 to rename DataFrame columns from Chinese → English before feeding to the pipeline
4. Both parsers feed into the same `CleaningPipeline` — no code-path divergence after parsing
5. Graceful handling: malformed CSV (wrong delimiter, encoding), corrupt Excel file, empty sheets, missing expected headers

## Group 5 — ImportJob Integration & Response

1. Create an `ImportJob` record at import start with status `pending`
2. Run parser → cleaning pipeline → DB insert in sequence; update `ImportJob.status` to `running`, then `completed` or `failed`
3. Insert cleaned rows into the target business table (e.g., `service_refund_work_orders`) in bulk via SQLAlchemy
4. Update `ImportJob` with final row count, error count, timestamps (`started_at`, `finished_at`)
5. Return JSON response: `{ import_job_id, target_table, status, rows_imported, rows_rejected, cleaning_report: { steps: [...], warnings_per_column: {...} }, errors: [...] }` — `target_table` echoes the Chinese display name

## Group 6 — Error Handling & Edge Cases

1. Malformed file → 400 with error detail (e.g., "CSV appears to be binary", "Excel file is corrupt")
2. Schema mismatch (missing or unexpected columns) → 422 with `{ missing: [...], unexpected: [...], expected: [...] }` using Chinese column names from comments
3. Unknown `target_table` → 400 with `{ "detail": "未知的目标表 'xxx'。可选：退费单、服务退款工单、钱包提现操作" }`
4. Empty file (0 data rows after header) → 200 with rows_imported=0, informative cleaning report
5. Unrecoverable rows (e.g., entirely unparseable data) → return partial success: rows that could be cleaned are imported, unrecoverable rows are listed in errors array
6. Database errors (connection lost, unique constraint violation) → 500, ImportJob status set to `failed`
