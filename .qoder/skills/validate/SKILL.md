---
name: validate
description: Plan validation steps when starting a new roadmap phase. Use when creating a feature spec directory, writing a validation.md, or defining what "done" means for a phase. Does NOT run checks — it plans them.
---

# Validation Planning

## When to Use

Invoke this skill when starting a new roadmap phase to define its validation gates — the concrete, verifiable checks that prove the phase is complete and mergeable. The output is the content for the phase's `validation.md`.

Do NOT use this to run checks. Use it to plan what checks belong in a phase.

## Workflow

For the current phase, work through these dimensions and decide which ones apply. For each that does, write a specific, verifiable gate.

### 1. README and documentation

Does this phase add new directories, commands, prerequisites, or setup steps?

If yes, add a gate: "README.md reflects X, Y, Z." Make it concrete — name the specific section or file that must be updated.

### 2. Formatting

Are there new files or languages introduced in this phase?

If yes, add a gate: "Run `<formatter>` — zero unformatted files." Specify the exact command so another developer can copy-paste it.

### 3. Linting

Are there new source files?

If yes, add a gate: "Run `<linter>` — zero errors, zero warnings." Specify the exact command.

### 4. Dead code and unused imports

Does this phase produce code that could accumulate dead paths, unused variables, or dangling imports?

If yes, add a gate describing how to detect and remove dead code. Reference the relevant compiler or linter rules.

### 5. Tests

Does this phase introduce logic that should be tested?

If yes, add a gate: "Run `<test command>` — all suites pass, zero failures." Specify the exact command. If the phase introduces a new test framework or test file convention, note it.

### 6. Phase-specific gates

Every phase has unique deliverables beyond the standard checks. Look at the phase's `plan.md` and `requirements.md` and add gates that verify:

- Does the feature actually work end-to-end?
- Can the deliverable be demonstrated?
- Would a new team member know how to verify it?

Write each gate with:
- A descriptive name (e.g. "Health check round-trip")
- The exact command or manual steps to run
- The expected output or behavior

### 7. Merge checklist

End `validation.md` with a bullet checklist that distills every gate into a single togglable item. This is what the reviewer checks before merging.

## Output format

Write the phase's `validation.md` using this structure:

```markdown
# Phase N — <Name>: Validation

How to know the implementation succeeded and can be merged. Every gate must pass.

---

## Gate 1 — <Descriptive name>

```bash
<exact command>
```

**Expected:** <concrete expected output>

---

## Gate N — <Descriptive name>

...

---

## Merge Checklist

- [ ] All N gates pass on a clean checkout
- [ ] <distilled checklist item>
```

## Example

For Phase 1 — Project Scaffolding, the validation plan produced gates for: health check round-trip (direct + proxy), frontend page rendering, responsive viewport, linting (backend + frontend), tests, and clean bootstrap. See `specs/2026-07-27-project-scaffolding/validation.md` for the concrete result.
