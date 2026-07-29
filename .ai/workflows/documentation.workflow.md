---
name: documentation
version: 1.0.0
applies_to: any
---

# Documentation Workflow

Dedicated path for documentation changes. Keeps docs reviewable in their own
right and prevents doc drift from blocking feature work.

## Purpose

Ensure every change ships with the right level of documentation, using the
project's `documentation.*` policy.

## Trigger

- A new feature, command, configuration, or public API is added.
- Existing documentation is found to be inaccurate.
- An ADR is required by `documentation.adr_required`.
- A release is being prepared.

## Inputs

- The change or feature that requires documentation.
- `project-config.yaml` for documentation gates.
- Existing documentation and any related ADRs.

## Steps

1. **Identify audience and level** (project, module, decision, API) using
   `documentation-guidelines.md`.
2. **Draft the content** with the `documentation-agent`.
3. **Validate against the documentation checklist** (`checklists/documentation.md`).
4. **Update diagrams** using `documentation.diagram_format`.
5. **Review** with the `review-agent` (documentation-focused).
6. **Publish** through the project's documentation pipeline.

## AI Skills Used

- `documentation`
- `architecture` (for diagrams and structural docs)
- `code-review` (for changes that ship with the docs)

## Outputs

- Updated README, module docs, ADRs, or API references.
- Diagrams in the configured format.
- A documentation report from the documentation template.

## Next Workflow

- `feature-development.workflow.md` if the docs surfaced missing capability.
- `release.workflow.md` if the docs are tied to a specific release.

## Rollback Strategy

- Revert the documentation commit.
- Re-publish the previous version of the docs.
- For generated docs, re-run generation against the previous source state.

## Quality Gates

- `checklists/documentation.md` is fully answered.
- Examples in the docs are copy-pasteable and tested.
- Links resolve. Diagrams render. Acronyms are defined.

## Required Approvals

- Standard reviewer count, unless the change is docs-only and explicitly marked
  as low-risk in the project policy.
  