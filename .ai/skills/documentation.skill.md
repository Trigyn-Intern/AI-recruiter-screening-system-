---
name: documentation
version: 1.0.0
applies_to: any
---

# Documentation Skill

Reusable documentation review and generation guidance. It works on READMEs, ADRs,
API references, and inline docs.

## Purpose

Make sure every change ships with the right level of documentation, using the
project's declared documentation policy.

## When to Invoke

- Adding new public APIs, commands, configuration, or features.
- Removing or renaming existing surfaces.
- When `documentation.adr_required` is true and a significant decision is being made.
- When `documentation.api_docs_required` is true and an API surface changed.

## Inputs

- `project-config.yaml` (required).
- The diff or change description.
- Optional: existing docs to update.

## Outputs

- A Documentation Report using `.ai/templates/documentation-template.md`.
- Draft text for new or updated sections (proposal only, not committed).

## Scope

- README accuracy and completeness.
- ADRs when `documentation.adr_required` is true.
- API docs when `documentation.api_docs_required` is true.
- Diagrams in the configured `documentation.diagram_format`.
- Inline doc comments for public surfaces.

## Checklist

Apply `.ai/checklists/documentation.md`. Mark each item `pass`, `gap`, or `n/a`.

## Expected Report

A Markdown report following the documentation template, with:

1. Scope of docs reviewed or needed.
2. Checklist results table.
3. Gaps and proposed edits.
4. ADR candidate summary when an ADR is warranted.

## Limitations

- Does not publish docs.
- Does not commit changes. The skill proposes edits only.

## Safe Rules

- Never invent features that do not exist in the code.
- Never assume a documentation tool. Use the configured `diagram_format`.
- Never duplicate the documentation standards. Reference the knowledge file.

## Verification Steps

1. Every documentation gate from `documentation.*` is reflected in the report.
2. Every checklist item is answered.
3. Proposed text does not contradict the diff.

## Related Knowledge

- `.ai/knowledge/documentation-guidelines.md`
- `.ai/checklists/documentation.md`
- `.ai/templates/documentation-template.md`