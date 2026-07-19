---
name: pre-commit-automation
version: 1.0.0
applies_to: any
---

# Pre-Commit Automation

Defines what the AI framework expects to happen automatically before a commit
is accepted. This document is read by the orchestrator and by the commit-time
automation layer. It does not contain scripts.

## Purpose

Catch the cheapest, most local issues at the cheapest, most local moment. The
goal is that a developer who runs through pre-commit never has a "trivial"
comment on their PR.

## Responsibilities

- Enforce formatting and linting on staged changes.
- Enforce secret detection on staged changes.
- Enforce static analysis on staged changes when configured.
- Run the smallest meaningful unit of tests.
- Notify the developer of any failure that blocks the commit.

## Inputs

- The staged diff (read-only).
- `project-config.yaml` for thresholds and tool enablement.
- The relevant knowledge, checklist, and template files from Phase 1.

## Outputs

- A pass or fail verdict for the commit.
- A list of violations mapped to checklist ids.
- A short developer-facing summary.

## Execution Flow

1. **Load context.** Read `code_quality.*` and the `coding` checklist.
2. **Format check.** Confirm staged changes match the project's formatting
   policy. Auto-format is allowed only when `code_quality.enforce_formatting`
   is true.
3. **Lint check.** Confirm staged changes pass the project's lint policy.
4. **Secret detection.** Scan the staged diff for credentials, tokens, and
   keys. Use the detection rules defined in the `security` knowledge file.
5. **Static analysis.** When enabled in `code_quality.*`, run the configured
   static analysis rules against the staged diff only.
6. **Unit smoke tests.** Run the smallest unit test scope that exercises the
   changed files. Full suite does not run at commit time.
7. **Coding standards check.** Apply `checklists/coding.md` to the staged
   diff. Flag any size, complexity, or naming violation.
8. **Notify.** Surface any failure to the developer with file, line, and
   remediation link.

## Automation Rules

- Pre-commit never modifies the working tree silently. Auto-fixes are applied
  only when the project's policy explicitly enables them.
- Pre-commit never runs the full test suite. That belongs to pre-push and CI.
- Pre-commit never uploads code. All checks are local.
- Pre-commit honors `code_quality.max_file_lines`,
  `code_quality.max_function_lines`, and
  `code_quality.max_cyclomatic_complexity`.

## Failure Handling

- A format or lint failure blocks the commit. The remediation is
  "run the formatter, run the linter, re-stage."
- A secret-detection finding blocks the commit. The remediation is
  "remove the secret, rotate the credential, re-stage."
- A static analysis finding at the configured severity blocks the commit.
  Lower severities are reported but do not block.
- A test failure blocks the commit. The remediation is "fix the failing
  test or fix the code under test."
- A coding standards violation at blocker or major severity blocks the
  commit. Minor and nit do not block at commit time.

## Examples

- Developer stages a 600-line file when `max_file_lines` is 400 -> pre-commit
  blocks with a coding-standards violation referencing the checklist id.
- Developer stages a hard-coded API key -> pre-commit blocks with a
  secret-detection finding and a rotation reminder.
- Developer stages a one-line comment fix -> pre-commit runs formatting
  and lint, then passes.
- Developer stages code that fails a smoke unit test -> pre-commit blocks
  with the test name and the failing assertion.

## Best Practices

- Keep pre-commit under a few minutes. If it is slow, move checks to pre-push.
- Use the same checklist ids everywhere so a violation in pre-commit and a
  comment on the PR are obviously the same thing.
- Never let pre-commit auto-fix without a recorded reason. Auto-fixes are
  easy to miss in code review.

## Reusable Enterprise Guidelines

- Pre-commit is a local convenience. It is not a security control. Secret
  detection at commit time is a safety net, not a primary defense.
- Pre-commit results are advisory until a CI run confirms them. Do not
  assume a green pre-commit is a green CI.

## Project Agnostic Design

- No project names, languages, frameworks, or tool names appear in the
  rules. The orchestrator resolves tool names from `project-config.yaml`.
- Adding a new check is a matter of declaring it in
  `automation-config.md` and pointing the orchestrator at the
  corresponding checklist id.
  