---
name: deployment-policy
version: 1.0.0
applies_to: any
---

# Deployment Policy

Defines the deployment environments, the promotion model, and the approval
checkpoints the AI framework expects. The framework describes the policy;
the platform performs the deployment.

## Purpose

Make deployments predictable. Every environment has the same gate, the
same smoke test, and the same rollback plan.

## Responsibilities

- Define the supported environments.
- Define the promotion order.
- Define the approval checkpoints.
- Define the smoke test contract.
- Define the rollback contract per environment.

## Inputs

- `project-config.yaml` for `deployment.target_environments` and
  `review_policy.*`.
- The platform's deployment capabilities.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 4 rollback strategy and release automation.

## Outputs

- A deployment policy declaration.
- A promotion map per environment.
- An approval matrix per environment.

## Environments

The framework supports the following environment tokens. The project
declares which ones it actually uses in
`deployment.target_environments`.

| Token | Purpose | Promotion From |
| --- | --- | --- |
| `dev` | Inner loop, developer-owned | local |
| `qa` | Quality assurance, shared | `dev` |
| `uat` | User acceptance, stakeholder-owned | `qa` |
| `staging` | Pre-production parity | `uat` |
| `prod` | Production | `staging` |

A project can use any subset. The order of promotion is the order in
`deployment.target_environments`.

## Promotion Model

- A build artifact is produced once and promoted through the
  environments in order.
- A promotion never rebuilds the artifact. The same bytes move
  through the chain.
- A promotion records the artifact identifier, the environment, the
  approver, and the timestamp.
- A failed promotion triggers the rollback strategy for the affected
  environment.

## Approval Checkpoints

| Environment | Approval Required | Approver |
| --- | --- | --- |
| `dev` | no | developer or automation |
| `qa` | no | QA owner or automation |
| `uat` | yes | product owner or stakeholder |
| `staging` | yes | release manager or designated owner |
| `prod` | yes | release manager, with security sign-off when in scope |

A project can require additional approvals by declaring them in
`project-config.yaml`. The framework does not invent approvers.

## Smoke Test Contract

Every promotion runs a smoke test suite. The smoke test suite must:

- Cover the documented critical paths.
- Run in under the configured budget.
- Be hermetic. It must not depend on production data.
- Be maintained alongside the application. A stale smoke test is a
  risk.

The smoke test suite is the same across environments. Differences are
in the test data and the thresholds, not in the scenarios.

## Rollback Contract

Every environment has a documented rollback path. The contract is:

- The previous artifact is available and reachable.
- The rollback can be triggered by the on-call rotation.
- The rollback records the artifact identifier, the environment, the
  approver, and the timestamp.
- The rollback is rehearsed on the schedule defined in
  `rollback-strategy.md`.

## Execution Flow

1. **Build.** The artifact is built once.
2. **Promote to dev.** The artifact is deployed to `dev` (when in the
   project's list).
3. **Promote to qa.** The artifact is deployed to `qa` (when in the
   list). Smoke tests run.
4. **Promote to uat.** The artifact is deployed to `uat` (when in the
   list). Approval is recorded. Smoke tests run.
5. **Promote to staging.** The artifact is deployed to `staging` (when
   in the list). Approval is recorded. Smoke tests run.
6. **Promote to prod.** The artifact is deployed to `prod` (when in
   the list). Approval is recorded. Smoke tests run.
7. **Verify.** The production smoke tests confirm the deployment.
8. **Notify.** The deployment is announced through the notification
   engine.
9. **Rollback if needed.** A failed verification triggers the
   rollback strategy.

## Automation Rules

- The promotion order is the order in `deployment.target_environments`.
  The framework does not invent a different order.
- The same artifact is promoted through every environment. Rebuilds
  are not allowed mid-promotion.
- The approval matrix is enforced by the platform. The framework
  reads the matrix and respects it.

## Failure Handling

- A failed smoke test blocks promotion. The release is held.
- A failed approval is escalated to the project owner.
- A failed deployment triggers the rollback strategy for the
  affected environment.
- A failed verification in production triggers an immediate rollback
  and an incident.

## Examples

- A project uses `[dev, qa, staging, prod]` -> the artifact is
  promoted through each in order, with approvals at `staging` and
  `prod`.
- A project uses `[qa, uat, prod]` -> the artifact is promoted
  through each, with approvals at `uat` and `prod`.

## Best Practices

- Promote the same artifact through every environment. Rebuilds
  invite drift.
- Keep the smoke test suite small and fast. A slow suite is a suite
  that gets skipped.
- Treat approvals as decisions, not as rubber stamps.

## Reusable Enterprise Guidelines

- Deployments are part of the audit trail. Every action is recorded.
- Deployments are owned. Every environment has a named owner.
- Deployments are rehearsed. The smoke test suite and the rollback
  path are tested on a schedule.

## Project Agnostic Design

- Environments are tokens. The platform maps them.
- Approvers are tokens. The platform resolves them against the
  project's identity provider.
- The smoke test contract is described in terms of capabilities, not
  tools.