---
name: feature-development
version: 1.0.0
applies_to: any
---

# Feature Development Workflow

End-to-end orchestration for taking a feature from intent to merged change. Stack-
agnostic. All thresholds and policies are read from `project-config.yaml`.

## Purpose

Drive a feature from requirement to reviewed, tested, and documented change with
consistent quality gates and clear ownership.

## Trigger

- A new requirement or feature ticket is opened.
- A user invokes this workflow explicitly (for example, "start feature flow").
- A `requirement-agent` raises a completed requirement that is ready for design.

## Inputs

- Requirement artifact (from the `requirement-agent` or the issue tracker).
- `project-config.yaml`.
- Relevant existing knowledge, checklist, and template files under `.ai/`.

## Steps

1. **Analyze requirement** using the `requirement-analysis` prompt.
2. **Break down the feature** into reviewable units using `feature-breakdown`.
3. **Design** with the `architecture-agent`, applying
   `architecture-principles.md` and `checklists/architecture.md`.
4. **Implement** with the `developer-agent`, applying
   `coding-standards.md` and `checklists/coding.md`.
5. **Test** with the `testing-agent`, applying `testing-guidelines.md` and
   `checklists/testing.md`. Include security-driven test scenarios from
   `knowledge/security-test-scenarios.md` when the surface is exposed.
6. **Document** with the `documentation-agent`, applying
   `documentation-guidelines.md` and `checklists/documentation.md`.
7. **Review** with the `review-agent`, coordinating `code-review` and
   `security` skills as required by `review_policy.*`.
8. **Generate PR description** using `generate-pr-description`.
9. **Merge** once all quality gates pass and the required approvals are in.

## AI Skills Used

- `architecture`
- `coding-standards`
- `code-review`
- `security`
- `unit-testing`
- `documentation`

## Outputs

- One or more small, focused change sets.
- Updated tests and documentation.
- A PR description from the `code-review` template.
- Updated ADRs when the design introduces a non-obvious decision.

## Next Workflow

- `release.workflow.md` when the change is part of a release train.
- `documentation.workflow.md` when a doc-only follow-up is required.
- `refactoring.workflow.md` when the design surfaces pre-existing debt.

## Rollback Strategy

- Revert the merge commit using the project's standard revert flow.
- Disable the feature flag or kill switch when the project uses one.
- Open a follow-up bug using `bug-fix.workflow.md` if the rollback uncovers a
  defect in the revert itself.

## Quality Gates

- All `review_policy.blocking_checks` pass.
- Coverage meets `testing.coverage_threshold`.
- Lint, format, and any required security scans pass.
- `checklists/architecture.md`, `checklists/coding.md`,
  `checklists/testing.md`, and `checklists/documentation.md` are fully answered.

## Required Approvals

- Reviewer count from `review_policy.required_reviewers`.
- Security review when `review_policy.require_security_review` is true.
- Architecture review when `review_policy.require_architecture_review` is true.
