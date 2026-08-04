---
name: architecture
version: 1.0.0
applies_to: any
---

# Architecture Skill

Reusable architecture review and design assistance. Stack-agnostic. All thresholds,
naming, and policy values come from `project-config.yaml`.

## Purpose

Help engineers reason about system structure, boundaries, and trade-offs using the same
standards across every project, without embedding those standards inside the skill.

## When to Invoke

- Designing a new service, module, or subsystem.
- Splitting or merging components.
- Reviewing change requests that touch public APIs, persistence, or cross-cutting
  concerns (auth, observability, messaging).
- Producing an architecture decision record (ADR) when `documentation.adr_required`
  is true.

## Inputs

- `project-config.yaml` (required).
- The change scope (files, modules, services affected).
- Any prior ADRs referenced from the change.

## Outputs

- An Architecture Report using `.ai/templates/architecture-report-template.md`
  (if present) or a structured Markdown response.
- A list of risks, decisions, and follow-ups.

## Scope

- Module / component boundaries.
- Dependency direction and coupling.
- Data ownership and persistence.
- External integrations and contracts.
- Cross-cutting concerns: auth, observability, error handling, deployment.

## Checklist

Apply `.ai/checklists/architecture.md`. Every item must be answered with one of
`pass`, `concern`, or `n/a`. Do not skip items.

## Expected Report

A Markdown report with:

1. Context and scope.
2. Decisions proposed or confirmed.
3. Checklist results table (item, status, note).
4. Risks and trade-offs.
5. Follow-ups and owners.

## Limitations

- This skill does not run tools, build code, or deploy anything.
- It does not replace human architecture review when
  `review_policy.require_architecture_review` is true.

## Safe Rules

- Never hardcode a technology choice inside the skill body.
- Never invent numeric thresholds. Read them from `project-config.yaml`.
- If a required config section is missing, fail loudly and name the missing key.
- Do not produce project-specific business logic.

## Verification Steps

1. `project-config.yaml` is loaded and its schema version matches this skill version.
2. The referenced checklist exists and is non-empty.
3. Every checklist item is answered.
4. The report uses the same section headings listed under "Expected Report".

## Related Knowledge

- `.ai/knowledge/architecture-principles.md`
- `.ai/knowledge/coding-standards.md`
- `.ai/checklists/architecture.md`