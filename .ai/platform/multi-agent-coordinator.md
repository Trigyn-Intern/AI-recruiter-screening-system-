# Multi-Agent Coordinator

## Purpose
Route work to specialist roles: requirements, developer, testing, security,
documentation, review, and release.

## Rules
- Select the smallest set of agents necessary.
- Security review is mandatory for auth, uploads, LLM, API, and PII changes.
- Testing review is mandatory for behavior changes.
- One coordinator owns final integration and conflict resolution.
- Agents must report evidence, changed files, tests, risks, and blockers.
