---
name: priority-selection
version: 1.0.0
applies_to: any
---

# Decision Tree: Priority Selection

Reusable rules for assigning a priority to a change. Priority drives which
workflow runs, which agents are mandatory, and how aggressively the change
moves through review.

## Purpose

Turn a change description into a single priority token so the orchestrator can
route it consistently.

## Responsibilities

- Apply the priority matrix.
- Map the priority to workflow and approval rules.
- Escalate when a priority conflict appears.

## Decision Rules

The orchestrator asks, in order:

1. **Is there an active production incident?**
   - Yes -> `priority=blocker`, workflow=`hotfix`.
2. **Is there a security risk that is exploitable or unmitigated?**
   - Yes -> `priority=critical`, workflow depends on impact (hotfix if
     exploited, otherwise feature or bug with security-agent gate).
3. **Is there a user-visible regression or a documented SLA breach?**
   - Yes -> `priority=high`.
4. **Is the change a planned feature or improvement with no SLA pressure?**
   - Yes -> `priority=medium`.
5. **Is the change a cosmetic, internal, or low-risk change?**
   - Yes -> `priority=low`.

## Inputs

- The change description.
- The active project policy in `project-config.yaml`.
- Any explicit priority declared by the user or the issue tracker.

## Outputs

- A priority token: `blocker`, `critical`, `high`, `medium`, or `low`.
- The matching workflow name from `.ai/workflow/`.
- A list of mandatory agents and approvals.

## Priority Matrix

| Priority | Workflow | Mandatory Agents | Approvals | Notes |
| --- | --- | --- | --- | --- |
| `blocker` | `hotfix.workflow.md` | `security-agent`, `developer-agent`, `testing-agent` | on-call + security | Production-impacting. |
| `critical` | `hotfix.workflow.md` or `bug-fix.workflow.md` | `security-agent`, `developer-agent`, `review-agent` | security + standard reviewers | Exploit risk or compliance. |
| `high` | `bug-fix.workflow.md` or `feature-development.workflow.md` | `developer-agent`, `review-agent`, `testing-agent` | `review_policy.required_reviewers` | User-visible regression. |
| `medium` | `feature-development.workflow.md` | `developer-agent`, `review-agent`, `testing-agent` | `review_policy.required_reviewers` | Planned work. |
| `low` | `documentation.workflow.md` or `refactoring.workflow.md` | `developer-agent` or `documentation-agent`, `review-agent` | reduced review | Cosmetic or internal. |

## Examples

- "Production is down" -> `blocker`, `hotfix.workflow.md`.
- "Login bypass possible with crafted header" -> `critical`, `hotfix` or
  `bug-fix` with `security-agent` mandatory.
- "Search is slow for large tenants" -> `high`, `bug-fix` or `feature` with
  performance review.
- "Add a settings page" -> `medium`, `feature-development.workflow.md`.
- "Fix a typo in the docs" -> `low`, `documentation.workflow.md`.

## Best Practices

- When a user explicitly sets a priority, honor it unless the matrix would
  upgrade it. Downgrades require an explicit reason.
- Never downgrade a `blocker` to anything other than `critical` after a
  full rollback.
- Surface the priority and the rationale to the user, not just the routing
  decision.

## Reusable Rules

- The matrix is the single source of truth. Agents do not re-derive
  priorities.
- The workflow mapping is by name, not by inline logic, so workflows can be
  added or replaced without changing priority rules.
- "Business impact" is interpreted through the project's documented SLAs, not
  by guessing.

## Project Agnostic Design

- No project names or product-specific SLAs appear here.
- The matrix uses generic tokens that map to any project's policy.