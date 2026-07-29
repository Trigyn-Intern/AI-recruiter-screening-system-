---
name: release
version: 1.0.0
applies_to: any
---

# Release Workflow

Coordinates the promotion of merged work from `branch_strategy.default_branch`
into target environments, with consistent notes and approvals.

## Purpose

Make releases predictable, traceable, and reversible. Every release is described
in the same format and gated by the same checks.

## Trigger

- A scheduled release window arrives.
- A release manager invokes the workflow explicitly.
- A hotfix has been merged and must be promoted immediately.

## Inputs

- Merged changes since the last release.
- `project-config.yaml` for environment and approval policy.
- The set of ADRs and decisions introduced since the last release.

## Steps

1. **Freeze the release scope** with the `release-agent`. No new features
   enter after this point.
2. **Verify quality gates** by re-running the consolidated checklist outputs
   for every included change.
3. **Generate release notes** using `release-notes`.
4. **Stage the release** in the first target environment declared in
   `deployment.target_environments`.
5. **Smoke test** the staged release against the documented critical paths.
6. **Promote** through the remaining environments in order.
7. **Tag the release** using the project's tagging convention.
8. **Publish notes** to the project's documented audience channels.
9. **Close out** by opening any follow-up issues discovered during release.

## AI Skills Used

- `code-review` (to summarize included changes)
- `security` (release-level threat and dependency review)
- `documentation` (release notes and any versioned docs)
- `unit-testing` (release-level summary of test status)

## Outputs

- A release artifact (build, image, package) per environment.
- Tagged source control state.
- Release notes in the project's standard format.

## Next Workflow

- `documentation.workflow.md` for any post-release doc cleanup.
- `bug-fix.workflow.md` or `hotfix.workflow.md` for any release-found issues.

## Rollback Strategy

- Roll back to the previous tagged artifact in each environment.
- Communicate the rollback and the trigger in the project's incident channel.
- Open a follow-up to investigate the cause before re-attempting the release.

## Quality Gates

- All blocking checks from `review_policy.blocking_checks` pass for every
  included change.
- No unresolved sev-1 or sev-2 defects in the included scope.
- Security and dependency posture has not regressed.

## Required Approvals

- Release manager or designated owner.
- Security approval when `review_policy.require_security_review` is true and
  the release includes security-sensitive changes.