# AI Development Instructions

This repository is the AI Recruiter Screening System. Before making code changes, read
`.ai/project-config.yaml` and select the relevant workflow, skill, checklist, and
knowledge files from `.ai/`.

## Project Structure

- `frontend/` - recruiter-facing React and Vite application.
- `frontend-test/` - React/Vite QA testing dashboard.
- `backend/` - Node.js/Express authentication API.
- `api.py` - FastAPI AI resume-analysis API.
- `tests/` - Python unit and integration tests.
- `vector_store/` - locally persisted FAISS index and resume-analysis data.
- `reports/` - generated quality, test, and security reports.

## Required Workflow Selection

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

Read `.ai/skills/coding-standards.skill.md`, `.ai/skills/unit-testing.skill.md`,
`.ai/skills/security.skill.md`, and the corresponding coding, testing, and security
checklists. Run relevant tests with `pytest`.

### React / Vite / frontend changes

Read `.ai/skills/coding-standards.skill.md`, `.ai/skills/unit-testing.skill.md`, and
the coding and testing checklists. Run the relevant frontend build and Playwright
scenarios where applicable.

### Authentication, uploads, LLM, API, or data-storage changes

Also read `.ai/skills/security.skill.md`, `.ai/knowledge/security-test-scenarios.md`,
and `.ai/checklists/security.md`. Review JWT validation, authorization, file type and
size validation, path traversal, prompt injection, sensitive-data exposure, and unsafe logging.

### Documentation changes

Read `.ai/skills/documentation.skill.md`, `.ai/checklists/documentation.md`, and
`.ai/templates/documentation-template.md`.

## Testing Expectations

- Add or update tests for every functional behavior change.
- Prefer deterministic tests; mock external LLM providers, Ollama, Gemini, and network calls.
- Keep Playwright tests independent and clean up generated test data.
- Do not reduce coverage or delete tests simply to make a build pass.
- When a test cannot be run, state why and give the exact command needed to run it.

## Review Expectations

Before finalizing a change, check for security regressions and exposed personal data;
ensure frontend and backend API contracts still match; validate error paths and fallback
behavior; and update documentation when setup, API behavior, configuration, or user
workflow changes. Use the templates in `.ai/templates/` for substantial review, test,
security, and documentation outputs.
