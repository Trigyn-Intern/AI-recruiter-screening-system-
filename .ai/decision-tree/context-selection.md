# Decision Tree: Context Selection

Reusable routing for "which files should be loaded as context for this task?"
Use this before invoking any skill or prompt.

## Inputs

- The current task (skill name, prompt name, or workflow step).
- The active project policy in `project-config.yaml`.
- The set of files already in context.

## Root Question

> "What does this task need to know to do its job well, and nothing more?"

## Context Categories

- **Policy** (always load)
  - `project-config.yaml`
- **Standards** (load the one(s) named by the skill)
  - `.ai/knowledge/coding-standards.md`
  - `.ai/knowledge/architecture-principles.md`
  - `.ai/knowledge/security-guidelines.md`
  - `.ai/knowledge/testing-guidelines.md`
  - `.ai/knowledge/documentation-guidelines.md`
  - `.ai/knowledge/security-test-scenarios.md` (when the security agent is in
    scope)
- **Checklists** (load the one(s) the skill must answer)
  - `.ai/checklists/coding.md`
  - `.ai/checklists/architecture.md`
  - `.ai/checklists/security.md`
  - `.ai/checklists/testing.md`
  - `.ai/checklists/documentation.md`
- **Templates** (load the one the skill must fill)
  - `.ai/templates/code-review-template.md`
  - `.ai/templates/security-review-template.md`
  - `.ai/templates/test-report-template.md`
  - `.ai/templates/documentation-template.md`
- **Change context** (load the smallest set that fully describes the change)
  - The diff or change description.
  - The originating requirement, if any.
  - The most recent prior review report, if any.

## Skill-Specific Loads

- `architecture` -> policy + architecture principles + architecture checklist
- `coding-standards` -> policy + coding standards + coding checklist
- `code-review` -> policy + coding standards + testing guidelines +
  documentation guidelines + code-review template + the four checklists
- `security` -> policy + security guidelines + security checklist +
  security-review template + security-test-scenarios knowledge
- `unit-testing` -> policy + testing guidelines + testing checklist + test
  report template + security-test-scenarios knowledge (when in scope)
- `documentation` -> policy + documentation guidelines + documentation
  checklist + documentation template

## Context Size Discipline

- Prefer one checklist over many when only one applies.
- Drop a context file once the skill has extracted the rule it needs.
- Never load two templates that serve the same purpose.
- Never load a knowledge file the skill does not reference.

## When to Stop Loading

Stop and escalate when:

- The required context contradicts `project-config.yaml`.
- A needed knowledge, checklist, or template file is missing.
- The change context is too large to summarize; ask the human to scope it
  down before continuing.