---
name: risk-matrix
version: 1.0.0
applies_to: any
---

# Decision Tree: Risk Matrix

Reusable rules for scoring the risk of a change. The risk score influences
which agents are mandatory, which approvals are required, and how aggressive
the change can be.

## Purpose

Make risk assessment consistent. Two reviewers looking at the same change
should arrive at the same risk band.

## Responsibilities

- Score a change on impact, likelihood, blast radius, and reversibility.
- Map the score to a risk band.
- Map the risk band to workflow and approval rules.

## Scoring Dimensions

Each dimension is scored `low`, `medium`, or `high`. The overall risk band is
the maximum of the four.

1. **Impact** - How bad is it if this change fails in production?
   - `low`: cosmetic, internal-only, no user-visible effect.
   - `medium`: user-visible but recoverable in a single user session.
   - `high`: user-visible and not recoverable without intervention, or any
     data integrity, security, or compliance impact.
2. **Likelihood of failure** - How likely is the change to fail?
   - `low`: small, well-understood change with good test coverage.
   - `medium`: change touches a known-fragile area or has incomplete tests.
   - `high`: change is large, novel, or has known gaps.
3. **Blast radius** - How many users, tenants, or systems are affected?
   - `low`: single user, single tenant, single environment.
   - `medium`: many users in one environment.
   - `high`: all users, all tenants, or production-wide.
4. **Reversibility** - How easy is it to roll back?
   - `low`: one-command revert with no data effect.
   - `medium`: revert plus a small data backfill.
   - `high`: revert plus a data migration, or revert is not possible.

## Risk Bands

| Band | Score Range | Workflows | Mandatory Agents | Approvals |
| --- | --- | --- | --- | --- |
| `negligible` | all dimensions `low` | any, reduced gates | agent owning the change | `review_policy.required_reviewers` |
| `moderate` | one or two dimensions `medium` | normal | `developer`, `testing`, `review` | `review_policy.required_reviewers` |
| `elevated` | any dimension `high`, or three or more `medium` | normal with security-agent gate | `developer`, `testing`, `security`, `review` | `review_policy.required_reviewers` + security |
| `severe` | two or more dimensions `high` | `hotfix` or `bug-fix` with full gates | all agents | full review board |

## Decision Rules

The orchestrator asks, in order:

1. **Is any dimension `high`?**
   - Yes -> band is at least `elevated`.
2. **Are two or more dimensions `high`?**
   - Yes -> band is `severe`.
3. **Are three or more dimensions `medium`?**
   - Yes -> band is `elevated`.
4. **Otherwise:**
   - All `low` -> `negligible`.
   - One or two `medium` -> `moderate`.

## Inputs

- The change description and the diff.
- The active project policy in `project-config.yaml`.
- The list of environments from `deployment.target_environments`.

## Outputs

- A risk band: `negligible`, `moderate`, `elevated`, or `severe`.
- A list of mandatory agents and approvals.
- A rollback recommendation.

## Examples

- "Fix a typo in the README" -> all `low` -> `negligible`.
- "Add a new API endpoint" -> impact `medium`, blast `medium`, others `low`
  -> `moderate`.
- "Change the auth flow" -> impact `high`, blast `high`,
  reversibility `medium` -> `severe`.
- "Add a new index to a hot table" -> impact `high`, reversibility `medium`
  -> `elevated`.
- "Update a dependency to fix a CVE" -> impact `high`, likelihood `low`
  (scoped) -> `elevated`.

## Best Practices

- Score dimensions independently, then take the maximum. Do not average.
- When in doubt, score up. Risk is cheaper to over-estimate than to
  under-estimate.
- Always pair the band with a rollback recommendation.

## Reusable Rules

- The risk band is one of four tokens. No half-bands.
- The matrix is read by the orchestrator and by the `review-agent`; both
  use the same band.
- The matrix does not store change history. It scores one change at a time.

## Project Agnostic Design

- No project names or technology names appear in the scoring rules.
- The matrix is project-agnostic; project-specific risk overlays belong in
  `project-config.yaml`.
  