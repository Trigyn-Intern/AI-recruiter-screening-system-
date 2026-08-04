# AI Development Instructions

This repository is the AI Recruiter Screening System.

Before making code changes, read `.ai/project-config.yaml` and select the relevant
workflow, skill, checklist, and knowledge files from `.ai/`.

## Project Structure

- `frontend/` — recruiter-facing React and Vite application.
- `frontend-test/` — React/Vite QA testing dashboard.
- `backend/` — Node.js/Express authentication API.
- `api.py` — FastAPI AI resume-analysis API.
- `tests/` — Python unit and integration tests.
- `frontend-test/` — Playwright scenario testing and reporting tools.
- `vector_store/` — locally persisted FAISS index and resume-analysis data.
- `reports/` — generated quality, test, and security reports.

## Required Workflow Selection

Choose the workflow that matches the task:

- New functionality: `.ai/workflows/feature-development.workflow.md`
- Bug correction: `.ai/workflows/bug-fix.workflow.md`
- Refactor: `.ai/workflows/refactoring.workflow.md`
- Production issue: `.ai/workflows/hotfix.workflow.md`
- Documentation-only change: `.ai/workflows/documentation.workflow.md`
- Release work: `.ai/workflows/release.workflow.md`

## Mandatory Engineering Rules

1. Never commit secrets, credentials, tokens, API keys, uploaded resumes, or real candidate data.
2. Use environment variables for configuration and secrets.
3. Preserve the local-first privacy model. Resume data must not be sent to a hosted LLM unless the configured provider explicitly permits it.
4. Validate all API inputs and LLM-generated structured data.
5. Treat LLM output as untrusted input. Do not execute generated code, commands, or URLs.
6. Keep FastAPI routes thin; place reusable business logic in focused functions or modules.
7. Keep React components focused and avoid mixing API logic, rendering, and state-heavy business rules in one component.
8. Maintain backward compatibility for persisted `vector_store/` data, or provide an explicit migration.
9. Do not modify generated reports, dependency folders, virtual environments, build output, or runtime logs unless the task explicitly requires it.

## Required Checks by Change Type

### Python / FastAPI changes

Read:

- `.ai/skills/coding-standards.skill.md`
- `.ai/skills/unit-testing.skill.md`
- `.ai/skills/security.skill.md`
- `.ai/checklists/coding.md`
- `.ai/checklists/testing.md`
- `.ai/checklists/security.md`

Run relevant tests with:

```powershell
pytest