---
name: pre-push-automation
version: 1.0.0
applies_to: any
---

# Pre-Push Automation

Defines what the AI framework expects to happen automatically before a push
is accepted. This document is read by the orchestrator and by the
push-time automation layer. It does not contain scripts.

## Purpose

Catch the issues that are too expensive for commit time but too important to
leave for CI. Pre-push is the developer's last local gate.

## Responsibilities

- Run the full unit test suite for the affected modules.
- Run AI-assisted code review on the outgoing diff.
- Run a security review on the outgoing diff when the surface is in scope.
- Run a performance review when the diff touches a known-hot area.
- Validate architecture conformance for changes that touch public surfaces.
- Validate documentation completeness for changes that affect user-facing
  behavior.
- Run the consolidated quality gate.

## Inputs

- The outgoing diff (read-only).
- `project-config.yaml` for review policy, coverage threshold, and risk band.
- The relevant Phase 1 knowledge, checklist, and template files.
- The Phase 2 agents and prompts for code review, security, and testing.
- The Phase 3 decision trees for routing and risk.

## Outputs

- A pass or fail verdict for the push.
- A code review report using `.ai/templates/code-review-template.md`.
- A security review report when in scope.
- A list of quality-gate failures with checklist ids.

## Execution Flow

1. **Load context.** Read `review_policy.*`, `testing.*`, and
   `quality-gates.md`.
2. **Classify the diff.** Use `priority-selection.md` to set priority and
   `risk-matrix.md` to set the risk band.
3. **Full unit tests.** Run the unit test suite for affected modules.
   Coverage must meet `testing.coverage_threshold`.
4. **AI code review.** Invoke the `review-agent` with the `code-review`
   skill and the `code-review` template.
5. **Security review.** When the diff is in scope per the `security`
   checklist, invoke the `security-agent` and produce a security report.
6. **Performance review.** When the diff is in scope per the
   `risk-matrix.md` performance flag, invoke the `testing-agent` with
   performance scenarios from `testing-guidelines.md`.
7. **Architecture validation.** When the diff touches a public surface,
   invoke the `architecture-agent` and apply
   `checklists/architecture.md`.
8. **Documentation check.** When user-facing behavior changes, invoke the
   `documentation-agent` and apply `checklists/documentation.md`.
9. **Consolidated quality gate.** Apply `quality-gates.md`. Any failure
   blocks the push.

## Automation Rules

- Pre-push may take longer than pre-commit, but should still target minutes,
  not tens of minutes. Long checks belong in CI.
- Pre-push never modifies the working tree. Fixes are the developer's job.
- Pre-push results are advisory until CI confirms them.
- The risk band drives which reviews are mandatory, not which are optional.

## Failure Handling

- A test failure blocks the push.
- A blocker or major in code review blocks the push.
- A `risk` in the security checklist blocks the push when the surface is in
  scope.
- A coverage drop below `testing.coverage_threshold` blocks the push.
- A `severe` risk band forces a hotfix workflow, not a normal push.

## Examples

- Developer pushes a feature that touches auth -> pre-push runs code review
  and security review in parallel. A missing authorization check blocks the
  push.
- Developer pushes a refactor that drops coverage from 85 to 70 when the
  threshold is 80 -> pre-push blocks with the coverage delta and the
  affected files.
- Developer pushes a hotfix with severity 1 -> pre-push routes to the
  hotfix workflow and bypasses the normal review queue.

## Best Practices

- Use the same template for code review at pre-push and at PR review. The
  only difference is the actor (local vs. remote).
- Treat pre-push as the safety net for CI, not a replacement for it.
- When pre-push and CI disagree, trust CI. The push is advisory until CI
  confirms it.

## Reusable Enterprise Guidelines

- Pre-push is a developer-side convenience. Security and compliance still
  live in CI and at the platform layer.
- Pre-push results are logged for the workflow, not for the developer.
  Logging is for audit, not surveillance.

## Project Agnostic Design

- No project names or technology names appear in the rules. The
  orchestrator resolves the in-scope rules from `project-config.yaml` and
  the checklists.
- New review types are added by extending `quality-gates.md`, not by
  editing this file.