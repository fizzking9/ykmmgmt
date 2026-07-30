# Changelog

All notable changes to YKMMgmt are documented in this file.

---

## 2026-07-30

- **Phase 3.5 — Smart Data Refresh (Upsert):** Re-uploading a data file now intelligently updates existing records instead of creating duplicates or silently discarding them. For Refund Orders (退费单) and Service Refund Work Orders (服务退款工单), the system matches records by their business ID numbers — if a record already exists, its data is refreshed with the latest values and the import timestamp is updated. For Wallet Withdrawals (钱包提现操作), which lack a natural business ID, the system computes a digital fingerprint of all column values and skips identical rows to prevent duplication. Import job reports now provide a detailed breakdown: how many rows were newly created, how many were updated, and how many were skipped as duplicates — while keeping the total count backward-compatible. Added 6 integration tests covering all three business tables, plus an Excel file import test. All 14 validation gates passed. Updated project documentation with upsert behavior reference and import API examples.

## 2026-07-29

- **Phase 3 — Data Import Engine:** A single file upload interface now accepts both CSV and Excel files. Chinese column headers in uploaded files are automatically matched to the correct database fields — no manual column renaming needed. Every file goes through a six-step data cleaning process before entering the database: whitespace trimming, empty row and column removal, duplicate row elimination, date and number format standardization, value validation, and table-specific structural fixes. Each import produces a detailed cleaning report showing exactly what was modified, removed, or flagged. If a file has mismatched or missing columns, the system rejects it immediately with a clear explanation of what's wrong. All three sample datasets were successfully imported — totaling approximately 60,000 rows across Refund Orders (退费单), Service Refund Work Orders (服务退款工单), and Wallet Withdrawals (钱包提现操作). 19 automated tests verify the cleaning pipeline, file parsers, and validation logic. All code quality checks passed.
- **Changelog format:** Updated changelog entries to use plain business language accessible to non-technical stakeholders, avoiding code symbols and database jargon. Each entry now describes what changed, why it matters, and the real-world impact.

## 2026-07-28

- **Phase 2 — Database & Business Tables:** Set up the PostgreSQL database that powers the entire application. Created the core data tables by analyzing the actual sample data files — three business tables (Refund Orders 退费单, Service Refund Work Orders 服务退款工单, Wallet Withdrawals 钱包提现操作) with columns matching the real data structure, plus two system tables for tracking data sources and import jobs. All tables use Chinese descriptions on every column so the system can auto-match uploaded file headers. A seed script loads the first 20 rows from each sample file for development and testing. Added a database health check to confirm the connection is working. All 10 validation gates passed.
- **Feature planning tool:** Added an automated workflow for creating new feature specifications — discovers the next planned phase from the roadmap, asks three clarifying questions about scope and decisions, then generates structured planning documents.

## 2026-07-27

- **Phase 1 — Project Foundation:** Built the two-application foundation: a backend data service and a React-based web dashboard. The backend runs on Python and provides a health-check endpoint to confirm the system is operational. The frontend is a modern single-page application that displays live system status, with automatic data refreshing. Both applications are configured to communicate seamlessly during development. Set up the full toolchain: code formatting and quality checks for both applications, automated testing frameworks (19 total tests across backend and frontend), mobile-responsive layout, and comprehensive setup instructions for new developers.
- **Project documentation:** Created the project roadmap, technical standards document, mission statement, and this changelog. Established the specification workflow for planning future phases with structured requirements and validation criteria.
