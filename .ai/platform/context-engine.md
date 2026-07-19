# Context Engine

## Purpose
Choose the minimum relevant repository context for each task.

## Include when relevant
- `.ai/project-config.yaml`
- Applicable workflow, skill, checklist, and knowledge file
- Changed source files and directly related tests
- API contracts and persistence schema
- Relevant reports or decision history

## Exclude
Secrets, unrelated modules, real candidate data, large generated artifacts, and logs
unless they are explicitly needed and safe to inspect.
