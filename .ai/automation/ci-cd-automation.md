---
name: ci-cd-automation
version: 1.0.0
applies_to: any
---

# CI/CD Automation

Defines what the AI framework expects from the continuous integration and
continuous delivery layer. This document is read by the orchestrator and by
the platform's pipeline configuration. It does not contain pipeline files.

## Purpose

Make the CI/CD contract explicit and project-agnostic. The framework owns
the contract; the platform owns the implementation.

## Responsibilities

- Define the pipeline stages the framework expects.
- Define the inputs, outputs, and gate at each stage.
- Define the deployment promotion model.
- Define the rollback contract.

## Inputs

- `project-config.yaml` for environments, branch policy, and review policy.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 2 agents and prompts.
- The Phase 3 decision trees for routing and risk.
- The other Phase 4 automation documents for cross-references.

## Outputs

- A pipeline contract document.
- A list of stage gates with pass criteria.
- A deployment promotion map.

## Pipeline Stages

| Stage | Purpose | Gate |
| --- | --- | --- |
| `build` | Produce the artifact | Build succeeds, artifact is produced and signed when required |
| `test` | Run unit, integration, and contract tests | All tests pass, coverage meets `testing.coverage_threshold` |
| `quality` | Run lint, format, static analysis, and coding-standards checks | `checklists/coding.md` is fully answered |
| `security` | Run SAST, dependency scan, and secret scan | `checklists/security.md` is fully answered, no `risk` items open |
| `documentation` | Verify docs are present and current | `checklists/documentation.md` is fully answered |
| `package` | Validate the artifact's metadata, signature, and provenance | Package validation passes |
| `deploy-<env>` | Deploy to one environment in `deployment.target_environments` | Environment-specific smoke tests pass |
| `release` | Tag and publish | `release-automation.md` gate passes |

## Execution Flow

1. **Build.** Compile or bundle the artifact using the project's declared
   build tool.
2. **Test.** Run the full test suite. Report coverage.
3. **Quality.** Apply coding standards and static analysis.
4. **Security.** Apply the security checklist and run scans.
5. **Documentation.** Apply the documentation checklist.
6. **Package.** Validate the artifact.
7. **Deploy.** Promote the artifact through the environments in
   `deployment.target_environments` in order.
8. **Release.** Tag and publish per `release-automation.md`.
9. **Notify.** Use `notification-engine.md` to route results.

## Automation Rules

- Every stage has an explicit gate. No silent progression.
- Every gate maps to a checklist id or a policy value. No invented
  thresholds.
- Every promotion is recorded. Promotion history is the audit trail.
- Every promotion is reversible. Rollback is a first-class operation,
  not a manual hack.

## Failure Handling

- A stage failure blocks the next stage.
- A flaky stage is retried per the platform's policy, then escalated.
- A failed promotion triggers automatic rollback when the platform
  supports it and the policy allows it.
- A `destructive` failure is escalated immediately and never retried.

## Examples

- A merge to `default_branch` runs build, test, quality, security,
  documentation, and package, then deploys to the first environment in
  `deployment.target_environments`.
- A tagged release runs the same stages plus a deploy to each subsequent
  environment in order, with a manual approval gate before production
  per `deployment-policy.md`.

## Best Practices

- Keep stages independent. A failure in one stage does not corrupt the
  next stage's input.
- Use the same gate definitions across projects. Consistency makes
  incidents easier to triage.
- Treat promotions as events, not as background work. They get noticed
  and they get reviewed.

## Reusable Enterprise Guidelines

- CI/CD is a platform capability. The AI framework consumes it; it does
  not replace it.
- CI/CD history is part of the audit trail. Retention follows the
  project's policy.
- CI/CD must be re-runnable on demand. A pipeline that cannot be
  re-run is a pipeline that cannot be trusted.

## Project Agnostic Design

- Stage names are tokens. The platform maps them to its own concept of a
  job or stage.
- Environments are read from `deployment.target_environments`. No
  environment names appear in this document.
  