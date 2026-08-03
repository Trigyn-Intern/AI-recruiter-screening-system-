# Git Hooks Automation

## Purpose
Run fast, local quality checks before code enters the shared branch.

## Pre-commit checks
- Reject secrets, API keys, JWT tokens, resumes, and candidate PII.
- Run formatting and linting for changed source files.
- Run focused unit tests for changed backend code.
- Validate YAML, JSON, and Markdown syntax where applicable.

## Pre-push checks
- Run the complete relevant test suite.
- Run Bandit and dependency-security checks.
- Build changed frontend applications.
- Block a push when a required check fails.

## Rules
- Hooks must not upload source code or candidate data to external services.
- Hooks must be deterministic and complete within a practical developer wait time.
- A bypass requires an explicit documented reason and follow-up CI validation.
