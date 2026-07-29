---
name: changelog
description: Maintain CHANGELOG.md at the project root from git history. Use when the user asks to update the changelog, before merging branches, or when the changelog is stale. Creates the file if missing, appends new commit entries under date headings otherwise.
---

# Changelog Maintenance

## When to Use

Invoke this skill **after** committing changes and before merging a branch. The changelog is derived from actual git history — never write date headings before commits exist. It ensures CHANGELOG.md reflects all commits since the last update.

## Workflow

### Step 1 — Check if CHANGELOG.md exists

Read the file at `CHANGELOG.md` in the project root. If it does not exist, jump to Step 3 (bootstrap from full history).

### Step 2 — Find the most recent date heading

Extract the latest date heading from the file, e.g. `## 2026-07-27`. This is the cutoff — only commits AFTER this date need new entries.

```bash
git log --oneline --format="%ad %s" --date=short --after="YYYY-MM-DD"
```

If there are no commits after the cutoff date, stop and report: "CHANGELOG already up to date."

### Step 3 — Bootstrap from full history (no existing file)

When CHANGELOG.md is missing, gather every commit:

```bash
git log --format="%ad %h %s" --date=short
```

### Step 4 — Group commits by date

Sort commits into date buckets. For each date, create a `## YYYY-MM-DD` heading. Under each heading, extract the essence of each commit message as a bullet point:

- Strip the conventional-commit prefix if present (e.g. `feat:`, `fix:`, `chore:`)
- Keep it concise — one line per commit
- Use the full commit message body for additional detail if it adds context

### Step 5 — Write or update the file

**If bootstrapping:** write the full file:

```markdown
# Changelog

All notable changes to YKMMgmt are documented in this file.

---

## YYYY-MM-DD

- Bullet point from commit 1
- Bullet point from commit 2

## YYYY-MM-DD

- Bullet point from commit 3
```

**If updating:** prepend new date sections after the header and `---` separator. Keep older dates below in reverse chronological order.

### Step 6 — Report

List what was added: the dates and number of entries per date.

## Format Rules

- **Date headings MUST reflect the actual commit date** — use `git log --date=short` to derive them, never guess or hard-code
- Dates in descending order (newest first)
- Use `## YYYY-MM-DD` headings
- One bullet (`-`) per commit, distilled to a single meaningful line
- Keep the header and `---` separator at the top of the file
- Never delete or reorder existing entries — only prepend
