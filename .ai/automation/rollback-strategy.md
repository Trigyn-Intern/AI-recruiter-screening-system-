---
name: rollback-strategy
version: 1.0.0
applies_to: any
---

# Rollback Strategy

Defines the rollback conditions, the rollback mechanisms, and the recovery
procedures the AI framework expects to be available. The framework
describes the contract; the platform performs the work.

## Purpose

Make rollback a first-class operation. Every change that reaches
production must be reversible, and the path back must be rehearsed.

## Responsibilities

- Define the rollback conditions.
- Define the rollback mechanisms per environment.
- Define the recovery procedures for data and configuration.
- Define the post-rollback follow-ups.

## Inputs

- `project-config.yaml` for environments, branch policy, and review
  policy.
- The platform's rollback capabilities.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 2 hotfix and bug workflows.
- The Phase 3 risk matrix and failure handling.

## Outputs

- A rollback plan per environment.
- A rollback runbook.
- A post-rollback follow-up list.

## Rollback Conditions

A rollback is triggered when any of the following is true:

- A `blocker` or `critical` event is observed in production.
- A failed smoke test after promotion.
- A failed health check or SLO breach after promotion.
- A security finding that cannot be mitigated in place.
- A failed migration that cannot be completed.
- An explicit human request from the release manager or on-call.

## Rollback Mechanisms

| Mechanism | When | Reversibility |
| --- | --- | --- |
| Redeploy previous artifact | application or service failure | full |
| Database migration rollback | failed migration | per migration |
| Configuration revert | configuration error | full |
| Feature flag disable | feature-level failure | full, when flags exist |
| Traffic shift | partial outage | partial |
| Data backfill | data corruption or loss | per backfill, recorded |

The framework does not own the implementations. It owns the contract.

## Execution Flow

1. **Detect.** A condition is observed through monitoring, the
   notification engine, or a human report.
2. **Classify.** The `failure-handling.md` rules classify the
   condition.
3. **Decide.** The release manager or on-call decides to roll back,
   roll forward, or hold.
4. **Execute.** The chosen rollback mechanism runs against the
   affected environment.
5. **Verify.** Smoke tests and health checks confirm the rollback.
6. **Communicate.** The rollback and its cause are communicated
   through the notification engine.
7. **Follow up.** A post-rollback follow-up is opened through the
   `bug-fix.workflow.md` or `refactoring.workflow.md` from Phase 2.

## Recovery Procedures

### Application

- Redeploy the previous artifact.
- Verify the previous artifact's health checks and smoke tests.
- Open a follow-up to investigate the failed artifact.

### Database

- Roll back the migration using the migration tool's documented
  reverse operation.
- Verify the database state against the pre-migration snapshot.
- Open a follow-up to investigate the failed migration.

### Configuration

- Revert the configuration to the last known-good state.
- Verify the configuration against the environment's expected state.
- Open a follow-up to investigate the configuration drift.

### Data

- When the data corruption is reversible, run the documented
  backfill.
- When the data corruption is not reversible, contain and compensate
  per the project's data playbook.
- Notify stakeholders per the project's policy.

## Failure Handling

- A rollback that fails is escalated immediately. The on-call rotation
  is engaged.
- A rollback that succeeds but leaves the system in an inconsistent
  state is escalated as a separate incident.
- A rollback that is rehearsed for the first time during an incident
  is a process failure. Rehearsals are scheduled, not improvised.

## Examples

- A new release causes a spike in error rate -> the on-call triggers
  a redeploy of the previous artifact -> the spike clears -> a
  follow-up bug is opened.
- A migration fails halfway -> the migration tool's reverse operation
  is run -> the database is restored to the pre-migration state ->
  a follow-up bug is opened.
- A configuration change causes a security finding -> the
  configuration is reverted -> the security finding is reviewed ->
  a follow-up bug is opened.

## Best Practices

- Rehearse rollback before the release, not during the incident.
- Keep the previous artifact available and reachable. A rollback that
  cannot find its target is a rollback that cannot run.
- Prefer the smallest reversible change. Big bangs are hard to roll
  back.
- Treat every rollback as a learning opportunity. The post-rollback
  follow-up is mandatory.

## Reusable Enterprise Guidelines

- Rollback is part of the audit trail. Every action is recorded.
- Rollback is a planned capability, not a panic reaction.
- Rollback is rehearsed on a schedule, not on the day of the incident.

## Project Agnostic Design

- Environments are read from `deployment.target_environments`.
- Rollback mechanisms are tokens. The platform maps them.