---
name: documentation-sync
version: 1.0.0
applies_to: any
---

# Documentation Sync

Defines what the AI framework expects from continuous documentation
maintenance. The goal is to prevent doc drift, not to write all docs.

## Purpose

Make documentation a living artifact. Docs that rot are worse than no
docs.

## Responsibilities

- Identify the documentation surfaces in the project.
- Detect when a change requires a doc update.
- Detect when existing docs are out of date.
- Generate or propose doc updates through the `documentation-agent`.
- Surface doc gaps through the notification engine.

## Inputs

- The change diff (read-only).
- The existing documentation surfaces.
- `project-config.yaml` for documentation gates.
- The Phase 1 documentation knowledge, checklist, and template files.
- The Phase 2 `documentation-agent` and prompts.

## Outputs

- A doc-impact report for every change that touches user-facing
  behavior.
- A doc-drift report on a schedule.
- A list of proposed doc updates for human review.

## Documentation Surfaces

| Surface | Source | Sync Trigger |
| --- | --- | --- |
| `README` | repository root | Any change to the project's public surface or quickstart |
| `CHANGELOG` | repository root | Any change released to a target environment |
| `API reference` | generated or hand-written | Any change to a public API |
| `Architecture docs` | under the project's docs path | Any change flagged by an ADR or architecture review |
| `ADRs` | under the project's ADRs path | Any non-obvious decision |
| `Developer guide` | under the project's docs path | Any change to the dev workflow or setup |
| `Deployment guide` | under the project's docs path | Any change to `deployment.*` or `ci-cd-automation.md` |
| `Release notes` | generated per release | Any release per `release-automation.md` |

The surfaces above are tokens. The platform maps them to the project's
actual file paths.

## Execution Flow

1. **On change.** When a PR or local change is opened, classify the
   change and identify which surfaces it affects.
2. **On schedule.** Periodically, scan the docs for drift against the
   code and configuration.
3. **Generate.** For each affected surface, generate a proposed update
   through the `documentation-agent` and the documentation template.
4. **Validate.** Apply `checklists/documentation.md` to the proposed
   update.
5. **Propose.** Open a docs PR or attach the proposal to the originating
   PR. Do not auto-merge.
6. **Notify.** Route doc gaps and drift through the notification engine.

## Automation Rules

- Docs are never auto-merged. A human reviews every doc change.
- Docs are generated from the same source of truth as the code. The
  documentation template is the contract.
- Docs use the same diagram format as the rest of the project, declared
  in `documentation.diagram_format`.
- Docs are versioned with the code. A doc that survives a refactor it
  should not have is a bug.

## Failure Handling

- A missing or stale doc is a doc gap, not a doc failure. The framework
  raises a gap and proposes a fix.
- A doc that cannot be generated (for example, missing context) is
  escalated to the documentation owner.
- A doc PR that is ignored for too long is escalated through the
  notification engine.

## Examples

- A PR adds a new public API -> the doc-sync flow proposes an API
  reference update and a README quickstart update.
- A release is cut -> the doc-sync flow proposes a CHANGELOG entry and
  release notes.
- A weekly scan finds the deployment guide out of date with the
  current `deployment-policy.md` -> the doc-sync flow proposes an
  update.

## Best Practices

- Keep docs close to the code they describe. Far-away docs rot.
- Use the same template for every doc surface. Consistency is the point.
- Treat doc gaps as defects, not as nice-to-haves.

## Reusable Enterprise Guidelines

- Docs are part of the audit trail. Doc history is retained per the
  project's policy.
- Docs are owned. Every surface has a named owner.
- Docs are reviewed in the same review as the code they describe.

## Project Agnostic Design

- Surfaces are tokens. The platform resolves them to the project's
  actual file paths.
- Diagram format and other style decisions are read from
  `documentation.*` in `project-config.yaml`.