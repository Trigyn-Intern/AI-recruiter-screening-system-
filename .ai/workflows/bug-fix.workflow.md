---
name: bug-fix
version: 1.0.0
applies_to: any
---

# Bug Fix Workflow

Structured response to a defect. Designed to prevent the same class of bug from
recurring without slowing down normal fixes.

## Purpose

Resolve a defect with a clear root cause, a regression test, and a record of what
was learned.

## Trigger

- A bug report is filed.
- A monitoring signal, log, or test failure is triaged into a bug.
- A `review-agent` or `testing-agent` finds a defect during normal work.

## Inputs

- Bug report (issue tracker, log excerpt, failing test).
- `project-config.yaml`.
- Relevant code, logs, and reproduction steps.

## Steps

1. **Triage** the bug with the `requirement-agent` and `bug-analysis` prompt.
2. **Reproduce** the defect. A fix without a reproduction is a guess.
3. **Analyze root cause** using `root-cause-analysis`.
4. **Plan the fix** with the `developer-agent`. Prefer the smallest correct change.
5. **Add a regression test** through the `testing-agent` before changing
   production code when feasible.
6. **Implement the fix** with the `developer-agent`.
7. **Review** with the `review-agent`, including a security pass when the bug
   touches auth, input, secrets, persistence, or external integrations.
8. **Document** the change when user-facing behavior changes.
9. **Generate PR description** with `generate-pr-description`.

## AI Skills Used

- `coding-standards`
- `code-review`
- `security`
- `unit-testing`
- `documentation`

## Outputs

- A regression test that fails before the fix and passes after.
- A focused code change.
- A PR description that includes root cause, scope, and risk.
- An updated checklist of related code paths when broader cleanup is needed.

## Next Workflow

- `feature-development.workflow.md` if the fix requires a new capability.
- `refactoring.workflow.md` if the bug exposes structural debt.
- `release.workflow.md` if the fix must ship ahead of the next planned release.

## Rollback Strategy

- Revert the fix commit.
- Re-enable any disabled feature or guard.
- If the bug had data integrity impact, follow the project's data-recovery
  playbook and notify the on-call rotation.

## Quality Gates

- Regression test added and verified to fail without the fix.
- Coverage on the affected module does not drop below
  `testing.coverage_threshold`.
- Security checklist passes when the surface is in scope.
- Documentation checklist passes when user-facing behavior changes.

## Required Approvals

- Default reviewer count from `review_policy.required_reviewers`.
- Security reviewer when the bug is in a security-sensitive area, regardless of
  `review_policy.require_security_review`.