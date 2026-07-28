---
name: feature-spec
description: Scaffolds a feature specification directory for the next incomplete roadmap phase. Finds the next unchecked phase in specs/roadmap.md, creates a git branch, asks 3 clarifying questions (Scope/Decisions/Context) via AskUserQuestion, then writes plan.md, requirements.md, and validation.md into specs/YYYY-MM-DD-feature-name/. References specs/mission.md and specs/tech-stack.md for context. Use when starting a new roadmap phase or when the user says "feature spec," "next phase," "start phase," or "spec out."
---

# Feature Spec Scaffolding

## When to Use

Invoke this skill when starting work on the next roadmap phase. It discovers the next incomplete phase, gathers requirements from the user, and writes the three spec files — without implementing anything.

## Workflow

### Step 1 — Find the next phase

Read `specs/roadmap.md`. Scan for the first `- [ ]` (unchecked) item. That item's parent heading is the next phase.

Extract:
- **Phase number** (e.g., `2` from `## Phase 2 — Database & Core Models`)
- **Phase name** (e.g., `Database & Core Models`)
- **All unchecked items** under that heading (the raw task list)

If every phase is checked (`- [x]`), stop and report: "All roadmap phases are complete."

### Step 2 — Build the directory name

Format as `YYYY-MM-DD-slug`:

- Date: today's date in ISO format (use the current system date)
- Slug: the phase name lowercased, spaces replaced with hyphens, special characters stripped

Example: `## Phase 2 — Database & Core Models` → `2026-07-28-database-core-models`

### Step 3 — Create the git branch

```bash
git checkout -b phase-N-slug
```

Use the phase number and the slug from Step 2. Example: `phase-2-database-core-models`.

### Step 4 — Read project context

Read `specs/mission.md` and `specs/tech-stack.md`. These inform the requirements and decisions sections.

### Step 5 — Ask clarifying questions (MANDATORY)

Use **AskUserQuestion** with exactly 3 questions in one call:

| Header | Question focus |
|--------|---------------|
| Scope | What the feature collects, exposes, or does — fields, behaviour, data shape |
| Decisions | Key implementation choices — storage, visibility, validation, UX pattern |
| Context | Tone, constraints, or anything shaping the spec — copy style, stack limits, open questions |

Do not write any files until the user has answered all three questions.

### Step 6 — Write the spec files

After the user answers, create `specs/<dir>/` with these three files. Use the exact format below.

#### plan.md

```markdown
# Phase N — Name: Plan

Numbered task groups in implementation order. Each group is independently verifiable.

---

## Group 1 — <Group name>

1. <Task>
2. <Task>

## Group 2 — <Group name>

1. <Task>
2. <Task>
```

- Derive task groups from the unchecked roadmap items. Group related items logically.
- Turn each `- [ ]` item into a concrete, verifiable task with enough detail that someone else could execute it.
- Order groups so each builds on the previous.

#### requirements.md

```markdown
# Phase N — Name: Requirements

## Scope

<What is delivered and what is explicitly out of scope. Synthesize from the user's Scope and Context answers.>

## Context (from mission.md)

<One paragraph tying this phase back to the project mission.>

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| <Decision> | <Choice> | <Rationale> |

## Constraints

<Constraints, dependencies, risks from the user's Context answer plus tech-stack.md.>

## Out of Scope

<Bullet list of what is explicitly NOT included.>
```

- Fill the Key Decisions table from any decisions gathered during Step 5.

#### validation.md

Use the **validate skill** workflow (seven dimensions: README, formatting, linting, dead code, tests, phase-specific gates, merge checklist) to produce the content.

```markdown
# Phase N — Name: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — <Descriptive name>

<exact command or manual steps>

**Expected:** <concrete expected output>

---

## Merge Checklist

- [ ] All N gates pass on a clean checkout
- [ ] <distilled checklist item>
```

- Gate numbering must be sequential starting from 1.
- Each gate must have an exact command and expected output.
- Phase-specific gates MUST verify the actual deliverables listed in `plan.md`.
- The merge checklist distills every gate into togglable items.

### Step 7 — Report

List what was created: the branch name, the spec directory path, and the three files. Remind the user that `plan.md` tasks are ready for implementation.
