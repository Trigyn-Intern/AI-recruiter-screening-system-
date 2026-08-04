---
name: refactoring
version: 1.0.0
applies_to: any
---

# Refactoring Workflow

Behavior-preserving structural improvement. Separates refactor work from feature
work so each change is reviewable on its own terms.

## Purpose

Pay down structural debt in small, safe steps without mixing refactor and feature
work in the same change.

## Trigger

- An ADR or architecture review identifies structural debt.
- A recurring bug or test smell traces to the same module.
- The `developer-agent` or `review-agent` flags a violation of the
  `checklists/coding.md` size or complexity limits.

## Inputs

- ADR or design note describing the target structure.
- `project-config.yaml` thresholds for size and complexity.
- Existing tests for the affected module.

## Steps

1. **Define the target structure** with the `architecture-agent`.
2. **Capture the existing behavior** with the `testing-agent`. Tests must
   already cover the behavior that will be preserved.
3. **Sequence the refactor** into small, individually mergeable steps.
4. **Apply each step** with the `developer-agent`, keeping the diff focused.
5. **Run the full test suite** after each step.
6. **Review each step** with the `review-agent`. Refactor steps should have
   zero behavior change.
7. **Update documentation** only when the public surface changes.
8. **Record completion** in the originating ADR or design note.

## AI Skills Used

- `architecture`
- `coding-standards`
- `code-review`
- `unit-testing`
- `documentation`

## Outputs

- A sequence of small merged refactor steps.
- A green test suite at every step.
- An updated ADR or design note.

## Next Workflow

- `feature-development.workflow.md` when the refactor unblocks planned work.
- `release.workflow.md` if the refactor must ride with a specific release.

## Rollback Strategy

- Each step is independently revertible. Revert the most recent step first.
- Re-run the test suite to confirm parity.
- For multi-step refactors, revert in reverse order when a step depends on
  the previous one.

## Quality Gates

- Zero behavior change in each step, verified by existing tests.
- No drop in coverage below `testing.coverage_threshold`.
- Each step is reviewable in under `code_quality.max_function_lines` of
  conceptual change (not literal line count).

## Required Approvals

- Standard reviewer count from `review_policy.required_reviewers`.
- Architecture review when `review_policy.require_architecture_review` is true.