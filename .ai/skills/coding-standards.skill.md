---
name: coding-standards
version: 1.0.0
applies_to: any
---

# Coding Standards Skill

Reusable coding-standards guidance. All numeric limits and style choices come from
`project-config.yaml` so the same skill works on every project.

## Purpose

Apply consistent coding rules (size, complexity, naming, formatting) without
duplicating the rules inside this file.

## When to Invoke

- Before creating or significantly editing source files.
- During self-review of a change.
- When triaging lint or formatter output.

## Inputs

- `project-config.yaml` (required).
- The changed files or proposed change description.
- Optional: linter/formatter output for the change.

## Outputs

- A short Coding Standards report listing violations and suggested fixes.
- References to the exact knowledge sections that apply.

## Scope

- File and function size limits.
- Cyclomatic complexity ceiling.
- Naming casing and file naming.
- Linting and formatting enforcement.
- Identifier prefixes from `naming_standards.identifier_prefixes`.

## Checklist

Apply `.ai/checklists/coding.md`. Mark each item `pass`, `violation`, or `n/a`.
Every violation must cite the offending file and line range when known.

## Expected Report

A Markdown report with:

1. Scope of the review (files, modules).
2. Thresholds actually applied (sourced from config, not invented).
3. Checklist results table.
4. Violations list with location, rule id, and fix.
5. Sign-off: `pass` or `changes-required`.

## Limitations

- Does not run the linter or formatter. It interprets their output if provided.
- Does not modify source files. It only recommends changes.

## Safe Rules

- Never override a threshold defined in `project-config.yaml` with a hardcoded value.
- Never assume a language or framework. Use `technology.*` for context only.
- Never write project-specific business code in the report.

## Verification Steps

1. Every reported threshold matches a key in `code_quality` or `naming_standards`.
2. Every checklist item has a status.
3. The report is shorter than the diff it reviews.

## Related Knowledge

- `.ai/knowledge/coding-standards.md`
- `.ai/checklists/coding.md`
- `.ai/project-config.yaml`
