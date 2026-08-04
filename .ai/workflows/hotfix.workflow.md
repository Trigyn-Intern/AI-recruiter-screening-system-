---
name: hotfix
version: 1.0.0
applies_to: any
---

# Hotfix Workflow

Expedited path for production-impacting defects. Mirrors `bug-fix.workflow.md` but
tightens scope, approvals, and observability.

## Purpose

Restore service or stop bleeding fast, without bypassing the quality bar that
keeps production safe.

## Trigger

- A severity-1 or severity-2 production incident.
- A security advisory requiring an out-of-band patch.
- An on-call engineer invokes the workflow explicitly.

## Inputs

- Incident summary and impact.
- Reproduction or log evidence.
- `project-config.yaml` for branch and approval policy.

## Steps

1. **Open a hotfix branch** using the `branch_strategy.hotfix_prefix`.
2. **Reproduce and root-cause** using `bug-analysis` and `root-cause-analysis`.
3. **Implement the minimum viable fix** with the `developer-agent`.
4. **Add or extend a regression test** with the `testing-agent`.
5. **Security pass** with the `security-agent` when the cause is in a security-
   sensitive area.
6. **Fast review** with the `review-agent` focused on the diff and its risk.
7. **Deploy** through the project's emergency release process.
8. **Communicate** status, scope, and follow-ups in the incident channel.
9. **Schedule a follow-up** through `bug-fix.workflow.md` or
   `refactoring.workflow.md` for any non-essential cleanup skipped in the rush.

## AI Skills Used

- `coding-standards`
- `code-review`
- `security`
- `unit-testing`
- `documentation` (for incident notes only, not full docs)

## Outputs

- A minimal, reviewable hotfix change.
- A regression test.
- Incident-ready notes covering what changed, what was rolled forward, and
  what was deferred.

## Next Workflow

- `bug-fix.workflow.md` for any deferred follow-up work.
- `release.workflow.md` to fold the hotfix into the next planned release.
- `refactoring.workflow.md` if the incident exposed structural debt.

## Rollback Strategy

- Pre-defined rollback command documented in the project's runbook.
- Feature flag kill switch when available.
- Data rollback only when the project's recovery path supports it and the
  impact is reversible. Otherwise, contain and compensate.

## Quality Gates

- The hotfix is small enough to be reverted in one step.
- A regression test is included unless the project explicitly waives this gate
  in the incident record.
- Security checklist is answered for any in-scope surface.
- Post-incident review is scheduled before the hotfix branch is closed.

## Required Approvals

- A single approver from the on-call rotation is sufficient to merge.
- Security approver is still required for security-sensitive changes.
- A retrospective owner is recorded.