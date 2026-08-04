---
name: quality-gates
version: 1.0.0
applies_to: any
---

# Quality Gates

Defines the reusable quality gates the AI framework expects to be enforced
at every relevant stage. Gates are tokens; the platform maps them to
concrete checks.

## Purpose

Make quality enforcement consistent. A blocker at pre-commit is the same
blocker at pre-push, PR, and CI. A passing gate is the same passing gate
everywhere.

## Responsibilities

- Define the gate catalog.
- Define the pass criteria per gate.
- Define the stage at which each gate is enforced.
- Define the override policy.

## Inputs

- `project-config.yaml` for thresholds and policy.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 3 risk matrix for severity scoring.

## Outputs

- A pass or fail verdict per gate.
- A consolidated pass or fail verdict per stage.

## Gate Catalog

| Gate | Source | Pass Criterion |
| --- | --- | --- |
| `formatting` | `code_quality.enforce_formatting` | Staged and committed code matches the project's formatting |
| `linting` | `code_quality.enforce_linting` | Staged and committed code passes the project's lint rules |
| `static-analysis` | `code_quality.*` (when enabled) | No findings at or above the configured severity |
| `secret-detection` | `security.sast_enabled` and secret scan | No secret-like content in the diff or in the committed files |
| `unit-tests` | `testing.*` | Unit test suite passes for the affected scope |
| `coverage` | `testing.coverage_threshold` | Coverage meets or exceeds the threshold for the affected scope |
| `coding-standards` | `checklists/coding.md` | All items answered; no `violation` at blocker or major |
| `architecture` | `checklists/architecture.md` (when in scope) | All items answered; no `concern` at blocker or major |
| `security` | `checklists/security.md` (when in scope) | All items answered; no `risk` unmitigated |
| `testing-quality` | `checklists/testing.md` | All items answered; no `gap` at blocker or major |
| `documentation` | `checklists/documentation.md` (when in scope) | All items answered; no `gap` at blocker or major |
| `dependency-scan` | `security.dependency_scan_enabled` | No advisory at or above the configured severity |
| `package-validation` | `deployment.*` and release policy | Artifact metadata, signature, and provenance are valid |
| `release-ready` | `release-automation.md` | All release conditions met |

## Stage Enforcement

| Stage | Gates Enforced |
| --- | --- |
| `pre-commit` | `formatting`, `linting`, `secret-detection`, `static-analysis` (when enabled), `unit-tests` (smoke), `coding-standards` |
| `pre-push` | `unit-tests` (full), `coverage`, `coding-standards`, `architecture` (when in scope), `security` (when in scope), `testing-quality`, `documentation` (when in scope) |
| `pull-request` | `pre-push` gates plus `dependency-scan` |
| `ci` | All gates including `package-validation` and `release-ready` for tagged builds |
| `release` | All gates plus the release-specific conditions from `release-automation.md` |

## Override Policy

- A gate is a gate. Overrides are explicit, recorded, and time-bound.
- Overrides require an owner and a documented reason.
- Overrides expire. A gate that is overridden for the lifetime of a
  project is not a gate.
- Overrides are surfaced in the audit trail.

## Execution Flow

1. **Collect.** Each stage collects the gate verdicts from the
   relevant checks.
2. **Score.** Apply the risk matrix to each failed gate.
3. **Consolidate.** Produce a single pass or fail verdict per stage.
4. **Surface.** Route the verdict through the notification engine.
5. **Block.** A failed gate blocks the next stage.

## Failure Handling

- A failed gate blocks the next stage. The remediation is in the
  gate's checklist entry.
- A gate that cannot run (for example, missing tool) is escalated to
  the platform owner.
- A gate that is flaky is retried per the platform's policy, then
  escalated.

## Examples

- A pre-push stage runs `unit-tests`, `coverage`, `coding-standards`,
  `security`, and `documentation`. A coverage drop below threshold
  fails the `coverage` gate and blocks the push.
- A release stage runs every gate plus the release-specific
  conditions. An open `risk` in the security checklist fails the
  release.

## Best Practices

- Keep the gate list small. Too many gates is too many to maintain.
- Map every gate to a checklist id. If a gate is not in a checklist,
  it is not a gate.
- Treat overrides as exceptions, not as a way of life.

## Reusable Enterprise Guidelines

- Gates are part of the audit trail. Every verdict is recorded.
- Gates are reviewed. Adding or removing a gate is a change that
  requires the same review as a code change.
- Gates are the same across projects. Differences are thresholds, not
  the gate list.

## Project Agnostic Design

- Gate names are tokens. The platform maps them to its own check
  names.
- Thresholds are read from `project-config.yaml`.