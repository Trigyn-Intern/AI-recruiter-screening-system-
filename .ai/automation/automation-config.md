---
name: automation-config
version: 1.0.0
applies_to: any
---

# Automation Config

Defines the configuration shape the AI framework expects for the
automation layer. This document is the contract between the framework
and the project's automation platform. The actual values live in
`project-config.yaml`; this document describes the keys the
automation layer reads.

## Purpose

Keep automation configuration in one place. The framework reads from
`project-config.yaml` and from the keys described here. The
automation platform reads from the same source of truth.

## Responsibilities

- Define the configuration keys the automation layer reads.
- Define the default values.
- Define the override policy.
- Define the validation rules.

## Inputs

- `project-config.yaml`.
- The Phase 4 automation documents.
- The platform's automation capabilities.

## Outputs

- A configuration contract.
- A validation report per change to the configuration.

## Configuration Keys

| Key | Type | Default | Purpose |
| --- | --- | --- | --- |
| `automation.enabled` | boolean | `true` | Master switch for the automation layer |
| `automation.pre_commit.checks` | list of tokens | `formatting`, `linting`, `secret-detection`, `static-analysis`, `unit-tests-smoke`, `coding-standards` | Checks enforced at pre-commit |
| `automation.pre_push.checks` | list of tokens | `unit-tests`, `coverage`, `coding-standards`, `architecture`, `security`, `testing-quality`, `documentation` | Checks enforced at pre-push |
| `automation.pull_request.checks` | list of tokens | `pre-push` plus `dependency-scan` | Checks enforced at PR |
| `automation.ci.checks` | list of tokens | all checks plus `package-validation` and `release-ready` for tagged builds | Checks enforced in CI |
| `automation.release.checks` | list of tokens | all checks plus the release-specific conditions from `release-automation.md` | Checks enforced at release |
| `automation.monitor.schedule` | token | `daily` | Schedule for the repository monitor |
| `automation.monitor.thresholds` | map | per observation type, see `repository-monitor.md` | Thresholds per observation |
| `automation.notifications.deduplication_window_minutes` | integer | `15` | Deduplication window for notifications |
| `automation.notifications.storm_threshold_per_hour` | integer | `10` | Threshold for a notification storm |
| `automation.notifications.off_hours.respect` | boolean | `true` | Whether to respect off-hours for non-critical events |
| `automation.rollback.rehearsal_schedule` | token | `quarterly` | Schedule for rollback rehearsals |
| `automation.deployment.environment_approvals` | map | per environment, see `deployment-policy.md` | Approval requirements per environment |
| `automation.deployment.smoke_test_budget_seconds` | integer | `300` | Budget for the smoke test suite |
| `automation.quality_gates.overrides` | map | empty | Time-bound overrides per gate |

Tokens are resolved by the platform. The framework does not know or
care which tool implements a given token.

## Default Values

Defaults are documented above. The framework uses the defaults when a
key is absent. The framework does not invent values for missing keys;
it surfaces the missing key and escalates per
`decision-tree/failure-handling.md`.

## Override Policy

- Overrides are scoped to a project, an environment, or a time window.
- Overrides require an owner and a documented reason.
- Overrides expire. A key that is overridden forever is not a key.
- Overrides are recorded in the audit trail.

## Validation Rules

- The configuration is validated on every change.
- A change that would remove a gate listed in
  `review_policy.blocking_checks` is rejected.
- A change that would lower `testing.coverage_threshold` below the
  project's documented floor is rejected.
- A change that would disable a security control listed in
  `security.*` is rejected unless the change is itself approved by
  the security reviewer.

## Execution Flow

1. **Load.** The automation layer loads `project-config.yaml` and the
   keys above.
2. **Validate.** The configuration is validated against the rules
   above.
3. **Resolve.** The platform maps tokens to concrete checks,
   channels, and schedules.
4. **Enforce.** The automation layer enforces the resolved
   configuration.
5. **Audit.** Every configuration change is recorded.
6. **Surface.** A drift between the framework's expectations and the
   platform's actual configuration is escalated.

## Failure Handling

- A missing required key is escalated to the project owner.
- An invalid value is rejected and the previous value is retained.
- A configuration drift between the framework and the platform is
  escalated to the platform owner.
- An override that is about to expire is surfaced for renewal or
  removal.

## Examples

- A project enables `automation.pre_commit.checks` and adds
  `dependency-scan` -> the pre-commit stage now runs a dependency
  scan on staged changes. The other stages are unchanged.
- A project sets `automation.notifications.deduplication_window_minutes`
  to `5` -> notifications are deduplicated within a 5-minute window.
  The behavior of other notification keys is unchanged.
- A project sets `automation.deployment.environment_approvals.prod` to
  `security-and-release` -> the production promotion requires both
  the release manager and the security reviewer.

## Best Practices

- Keep the configuration small. The framework's defaults are the
  baseline; only override what you need to override.
- Use overrides sparingly. A configuration that is overridden
  everywhere is a configuration that should be the default.
- Review the configuration on the same cadence as the rest of the
  policy.

## Reusable Enterprise Guidelines

- Configuration is part of the audit trail. Every change is
  recorded.
- Configuration is reviewed. Adding or removing a key is a change
  that requires the same review as a code change.
- Configuration is the single source of truth. The framework, the
  platform, and the humans all read from the same file.

## Project Agnostic Design

- Keys are tokens. The platform resolves them.
- Defaults are framework-wide. The platform does not invent its own
  defaults that contradict the framework.
- Validation rules are universal. The platform enforces them.