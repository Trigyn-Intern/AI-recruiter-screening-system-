---
name: code-review
version: 1.0.0
applies_to: any
---

# Code Review Skill

Reusable code-review assistance. The skill coordinates the other skills (coding
standards, security, testing, documentation) and produces a single consolidated review.

## Purpose

Provide a predictable, project-agnostic code review that surfaces risks, asks
focused questions, and respects the active review policy.

## When to Invoke

- Reviewing a pull request or a substantial local change.
- Preparing a self-review before opening a PR.
- Triaging review feedback for consistency.

## Inputs

- `project-config.yaml` (required).
- The diff or change description.
- Optional: related checklist or template paths the user wants emphasized.

## Outputs

- A Code Review Report using `.ai/templates/code-review-template.md`.
- A clear `approve`, `comment`, or `request-changes` verdict.

## Scope

- Correctness and edge cases.
- Readability and maintainability.
- Test coverage and test quality.
- Security implications (delegate to `security` skill when needed).
- Documentation impact (delegate to `documentation` skill when needed).
- Adherence to the configured `review_policy`.

## Checklist

Apply `.ai/checklists/coding.md` first, then any blocking checks listed under
`review_policy.blocking_checks` in `project-config.yaml`.

## Expected Report

A Markdown report following the code-review template, with:

1. Summary (one paragraph).
2. Findings grouped by severity: blocker, major, minor, nit.
3. Checklist results table.
4. Questions for the author.
5. Verdict and rationale.

## Limitations

- Does not run tests, linters, or security scanners.
- Does not merge code or modify branches.
- Should defer to a human reviewer when `review_policy.require_code_review` is true.

## Safe Rules

- Never approve a change that fails a `blocking_checks` item.
- Never invent policy. Read it from `project-config.yaml`.
- Never duplicate the underlying standards. Reference the knowledge files.

## Verification Steps

1. The verdict matches the count of blockers and majors.
2. Every blocking check listed in config has a status.
3. The report references the templates and checklists used.

## Related Knowledge

- `.ai/knowledge/coding-standards.md`
- `.ai/knowledge/testing-guidelines.md`
- `.ai/checklists/coding.md`
- `.ai/templates/code-review-template.md`
