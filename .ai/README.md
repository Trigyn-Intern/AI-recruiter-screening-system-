# AI Development Accelerator

Reusable, configuration-driven AI framework that augments engineering workflows across any
stack (front-end, back-end, mobile, data, infra). It is designed to be consumed by AI
coding assistants (Codex, Claude Code, GitHub Copilot, etc.) and by the surrounding Git
hook and automation layer.

## Goals

- Single source of truth for engineering standards, separated from project code.
- Zero hardcoded technology, framework, or naming assumptions.
- Skills remain small, composable, and reference external knowledge/checklists/templates.
- One configuration file (`project-config.yaml`) controls every per-project decision.

## Repository Layout

```
.ai/
  README.md                 # This file
  project-config.yaml       # The ONLY file that should change between projects
  skills/                   # Reusable AI skill definitions
  knowledge/                # Reusable engineering standards documentation
  templates/                # Report and document templates
  checklists/               # Verification checklists used by skills and humans
  agents/                   # Specialist AI roles for development and review
  workflows/                # Task-specific delivery workflows
  prompts/                  # Reusable analysis and test-generation prompts
  decision-tree/            # Routing, prioritization, and failure rules
  automation/               # Hook, CI/CD, PR, release, and notification policies
  analysis/                 # Repository-wide intelligence and risk analysis
  reports/                  # Report contracts for developers and stakeholders
  learning/                 # Approved project knowledge and lessons learned
  platform/                 # Multi-agent coordination, governance, and audit rules
```

## How It Fits Together

1. `project-config.yaml` declares the active stack, conventions, and policies.
2. A skill reads `project-config.yaml` to know which knowledge, checklist, and template to
   apply for the current project.
3. Knowledge files hold long-lived standards (SOLID, OWASP, testing pyramid, etc.).
4. Checklists turn those standards into verifiable steps.
5. Templates turn skill output into consistent reports.
6. Automation policies map quality gates to local hooks and CI.
7. Analysis, reports, learning, and platform files support enterprise-wide governance.

## Operating the Local Platform

Use the repository-local operator to make the framework executable without sending source
code or candidate data to an external service:

```powershell
venv\Scripts\python.exe scripts\ai_platform.py route "Add recruiter export"
venv\Scripts\python.exe scripts\ai_platform.py report
venv\Scripts\python.exe scripts\ai_platform.py learn "Use a focused regression test for cache fixes"
```

`route` selects the workflow, skills, and checklists for a task. `report` generates the
repository-wide reports shown in the testing dashboard. `learn` only accepts non-sensitive
notes and rejects candidate data, secrets, and credentials.

## Authoring Rules

- Skills reference knowledge/checklists/templates; they do not duplicate standards.
- Every Markdown file is plain ASCII unless the surrounding file already uses Unicode.
- Keep skills under ~300 lines so they remain focused and composable.
- Never embed project names, framework names, hardcoded paths, or business logic here.
- This directory must remain framework-agnostic and language-agnostic.

## Versioning

Bump the schema version inside `project-config.yaml` when the structure changes. Skills
should fail gracefully (not silently) when an expected section is missing.

## Integration Boundaries

This directory defines policy and reusable instructions. The executable integrations live
outside it: Git hooks in `.githooks/`, GitHub Actions in `.github/workflows/`, and project
source code in the application folders. MCP server credentials and AI-provider secrets must
remain in environment configuration, never in `.ai/`.
