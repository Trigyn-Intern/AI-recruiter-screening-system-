---
name: release-automation
version: 1.0.0
applies_to: any
---

# Release Automation

Defines what the AI framework expects from the release process. The
framework reads the policy; the platform performs the work.

## Purpose

Make releases predictable, traceable, and reversible. Every release is
described in the same format and gated by the same checks.

## Responsibilities

- Define the release inputs and outputs.
- Define the release gate and the conditions for a `go`, `hold`, or
  `no-go` decision.
- Define the release notes contract.
- Define the tag and publish contract.
- Define the post-release follow-up contract.

## Inputs

- The set of merged changes since the last release.
- `project-config.yaml` for environments, branch policy, and review
  policy.
- The Phase 1 knowledge, checklist, and template files.
- The Phase 2 `release-agent` and the `release-notes` prompt.
- The Phase 3 risk matrix and priority selection.

## Outputs

- A go or no-go decision with rationale.
- A tagged artifact per environment.
- Release notes in the standard format.
- A list of post-release follow-ups.

## Release Gate

A release proceeds when:

- All `review_policy.blocking_checks` pass for every included change.
- No unresolved severity-1 or severity-2 defects in the included scope.
- The security and dependency posture has not regressed.
- The release notes are generated and reviewed.
- Rollback readiness is confirmed for every target environment.
- The required approver per `deployment-policy.md` has signed off.

A release is held when a non-blocking gap is acceptable but must be
tracked. A release is a no-go when any blocking check fails or rollback
is not ready.

## Execution Flow

1. **Freeze scope.** The `release-agent` freezes the included changes.
2. **Verify gates.** Re-run the consolidated checklist outputs for every
   included change.
3. **Generate notes.** Use the `release-notes` prompt and the standard
   format.
4. **Stage.** Deploy to the first environment in
   `deployment.target_environments`.
5. **Smoke test.** Run the documented critical paths.
6. **Promote.** Promote through the remaining environments in order.
7. **Tag.** Tag the source control state using the project's convention.
8. **Publish.** Publish the release notes and any versioned docs.
9. **Close out.** Open any post-release follow-ups.

## Automation Rules

- A release is a planned event. Manual dispatch is the norm; fully
  automatic releases require an explicit policy declaration in
  `project-config.yaml`.
- Every release produces a tag. Tags are the audit trail.
- Every release produces release notes in the standard format.
- Every release is reversible. Rollback is rehearsed, not improvised.
- Hotfix releases follow `hotfix.workflow.md` from Phase 2 and the
  hotfix branch in `branch-policy.md`.

## Failure Handling

- A failed smoke test blocks promotion. The release is held.
- A failed promotion triggers automatic rollback when the platform
  supports it and the policy allows it.
- A release that cannot be tagged (for example, dirty tree) is
  escalated to the release manager.
- A release with a contested go or no-go decision is escalated to the
  project owner.

## Examples

- A scheduled release includes 12 merged PRs -> the release flow
  verifies gates, generates notes, stages, smoke tests, and promotes
  through each environment in order.
- A hotfix release includes one PR from a `hotfix/` branch -> the
  hotfix flow runs with reduced gates and the same release notes
  contract.

## Best Practices

- Cut releases from a known-good state, not from `default_branch` head
  unless the policy explicitly says so.
- Rehearse rollback before the release, not during the incident.
- Use the same release notes format across every release and every
  project.
- Treat the release manager as a role, not a person. The role survives
  the person.

## Reusable Enterprise Guidelines

- Releases are part of the audit trail. Every action is recorded.
- Releases are announced through the standard channels per
  `notification-engine.md`.
- Releases are owned. Every release has a named release manager.

## Project Agnostic Design

- Environments are read from `deployment.target_environments`.
- Branch types are read from `branch_strategy.*`.
- Release notes format is the standard format from the `release-notes`
  prompt. No project-specific sections are invented here.