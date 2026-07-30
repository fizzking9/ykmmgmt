---
name: changelog
description: Maintain CHANGELOG.md at the project root from git history. Use when the user asks to update the changelog, before merging branches, or when the changelog is stale. Creates the file if missing, appends new commit entries under date headings otherwise. Entries are written for non-technical stakeholders — plain business language, no code symbols.
---

# Changelog Maintenance

## When to Use

Invoke this skill **after** committing changes and before merging a branch. The changelog is derived from actual git history — never write date headings before commits exist. It ensures CHANGELOG.md reflects all commits since the last update.

## Audience & Voice

**The changelog is for non-technical stakeholders** — managers, operations staff, business users who need to understand what changed and why it matters, not how it was implemented. Read every entry and ask: "Would someone who has never written code understand this?" If not, rewrite it.

### Writing Guidelines

- **Describe the feature, not the implementation.** Say "re-uploading files now updates existing records" not "replaced on_conflict_do_nothing with on_conflict_do_update."
- **No code symbols.** Never use function names, variable names, endpoint paths, HTTP status codes, or database terminology. No backticks.
- **No tool names.** Avoid mentioning specific frameworks, libraries, or tools by name (FastAPI, SQLAlchemy, Alembic, Ruff, etc.). Say "the backend" or "the system" instead.
- **Include business context.** What problem does this solve? Who benefits? What's the real-world impact?
- **Use the application's own terminology.** Refer to tables by both their English and Chinese names (e.g., "Refund Orders (退费单)"). Use terms the actual users see in the UI.
- **Be comprehensive.** Each entry should be a self-contained paragraph — a reader jumping to any date should get the full picture without reading earlier entries.
- **Mention scope.** How many tables affected? How much data? How many tests? Give a sense of scale.

### Good vs Bad Examples

| ❌ Bad (developer-speak) | ✅ Good (business language) |
|---|---|
| Replaced `on_conflict_do_nothing()` with `on_conflict_do_update()` | Re-uploading data now updates existing records instead of creating duplicates |
| Added `rows_inserted`, `rows_updated`, `rows_skipped` columns to `import_jobs` | Import reports now show a detailed breakdown of new vs updated vs skipped records |
| Endpoint `POST /api/imports` returns 422 on schema mismatch | Files with mismatched columns are rejected immediately with a clear explanation |

## Workflow

### Step 1 — Check if CHANGELOG.md exists

Read the file at `CHANGELOG.md` in the project root. If it does not exist, jump to Step 3 (bootstrap from full history).

### Step 2 — Find the most recent date heading

Extract the latest date heading from the file, e.g. `## 2026-07-27`. This is the cutoff — only commits AFTER this date need new entries.

```bash
git log --format="%ad %s" --date=short --after="YYYY-MM-DD"
```

If there are no commits after the cutoff date, stop and report: "CHANGELOG already up to date."

### Step 3 — Bootstrap from full history (no existing file)

When CHANGELOG.md is missing, gather every commit:

```bash
git log --format="%ad %h %s" --date=short
```

### Step 4 — Translate commits into business entries

Group commits by date. For each date:

1. Read the full commit messages and any associated spec files (plan.md, requirements.md) for context
2. Distill the technical changes into business capabilities — what can the user now do that they couldn't before?
3. Combine related commits into a single comprehensive entry (e.g., one commit for models + one for service logic + one for tests = one changelog entry)
4. Write the entry following the Audience & Voice guidelines above
5. Review each entry against the Good vs Bad table — if it resembles the left column, rewrite it

### Step 5 — Write or update the file

**If bootstrapping:** write the full file:

```markdown
# Changelog

All notable changes to YKMMgmt are documented in this file.

---

## YYYY-MM-DD

- **Feature name:** Description in plain business language — what changed, why it matters, who it affects, and the scale of impact. No code symbols, no tool names. Self-contained paragraph understandable without programming knowledge.

## YYYY-MM-DD

- **Another feature:** Another self-contained business description.
```

**If updating:** prepend new date sections after the header and `---` separator. Keep older dates below in reverse chronological order. When updating, also review and refresh older entries if they still use developer-speak.

### Step 6 — Report

List what was added: the dates and the feature titles per date.

## Format Rules

- **Date headings MUST reflect the actual commit date** — use `git log --date=short` to derive them, never guess or hard-code
- Dates in descending order (newest first)
- Use `## YYYY-MM-DD` headings
- One bullet (`-`) per feature or logical group of changes, with a **bold feature name** followed by a colon and a plain-language description
- No code symbols (no backticks, no function names, no endpoint paths, no HTTP codes, no tool/library names)
- Self-contained entries — a reader should understand any entry without reading earlier ones
- Keep the header and `---` separator at the top of the file
- Never delete or reorder existing entries — only prepend
