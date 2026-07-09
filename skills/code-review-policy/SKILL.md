---
name: code-review-policy
description: LLM-driven code review policy for the AI Recruiter Screening System. Reviews backend (Node/Express), frontend (React/Vite), Python AI services, GitHub workflow files, configuration, and tests. Invoked manually in chat or by the pre-push Git hook. Never executes scanners and never modifies code automatically.
modes: [all, backend, frontend, python, github, changed-files]
default_mode: all
safe_mode: true
execution: model-reads-markdown
---

# code-review-policy

This skill is a prompt manifest. There is no CLI, no runner, no registry, no Docker image, and no GitHub Action for this skill. The model reads this file and follows the checklist for the requested mode. The skill **never modifies code automatically**. It returns findings; the developer decides what to do.

## Invocation

The skill is generic and works with any AI coding assistant that supports skills (Codex, Claude, or compatible). Invoke the **Code Review Policy** skill with an optional mode.

- Invoke the skill with no arguments -> reviews every file in scope.
- Invoke the skill with `mode=backend` -> reviews only Node/Express backend files.
- Invoke the skill with `mode=frontend` -> reviews only React/Vite frontend files.
- Invoke the skill with `mode=python` -> reviews only Python AI modules.
- Invoke the skill with `mode=github` -> reviews only GitHub workflow and configuration files.
- Invoke the skill with `mode=changed-files` -> reviews only the files listed in `.code-review/last-changed-files.txt`.

If no mode is specified, `all` is used.

### Examples

```
Invoke the Code Review Policy skill.
Invoke the Code Review Policy skill in mode=backend.
Invoke the Code Review Policy skill in mode=changed-files.
```

## Scope per mode

| Mode | Files |
|---|---|
| `all` | Union of every other mode |
| `backend` | `backend/**/*.js`, `backend/**/*.json` |
| `frontend` | `frontend/src/**/*.{js,jsx,ts,tsx}`, `frontend/index.html`, `frontend/vite.config.js`, `frontend/package.json` |
| `python` | `api.py`, `backend.py`, `tests/**/*.py`, `tests/data/*.py` |
| `github` | `.github/workflows/*.yml`, `.github/dependabot.yml`, `.gitignore`, `start-app.ps1`, `tests/run.ps1`, `tests/render_report.py` |
| `changed-files` | Every path listed in `.code-review/last-changed-files.txt` (one per line) |

`changed-files` is the only mode whose scope is decided at run time. For every other mode, the scope is a static glob that the LLM walks.

## How to use this manifest

1. Read the **Scope** for the selected mode. For `changed-files`, read `.code-review/last-changed-files.txt` first.
2. Read every file in scope. If a file is binary, skip it and note that in the report.
3. Walk the **Review categories** below. For each item, decide: present, absent, or needs verification.
4. Format findings using the **Findings** shape.
5. Apply the **Safe review rules** — never echo secrets, never fabricate issues.
6. End the report with a **Code Quality Summary** and a **Verdict** in GitHub-style terminology.
7. When invoked by the pre-push hook, append a final `VERDICT:` line so the hook can read it.

## Review categories

The skill checks nine categories. For every category, the LLM looks for the listed signals. If a signal is present, it is a finding with a severity. If a signal is absent, that is not a finding (it is the expected state).

### 1. Code Quality

- Duplicate code blocks (copy-paste with minor changes)
- Redundant logic (same condition checked twice, two loops doing the same thing)
- Dead or unused code (unreachable branches, exports that no caller imports, commented-out blocks older than the codebase)
- Functions longer than ~50 lines or with cyclomatic complexity > 10
- Poor naming (`x`, `tmp`, `data`, single-letter names outside tight scopes)
- Magic numbers or hardcoded values that should be named constants or env vars
- Missing comments where the intent is non-obvious (regex, scoring formulas, business rules)

### 2. Architecture

- Follows the existing project layout (`backend/`, `frontend/src/`, `tests/`, `api.py` at repo root)
- Separation of concerns (controllers thin, services do the work, models hold data only)
- SOLID principles: one reason to change, open/closed, substitutable, narrow interfaces, depend on abstractions
- Reusable components (no copy-paste of a React component into two pages)
- Folder organization: feature folders, not type folders, when the project already uses them
- No new top-level dependencies unless they earn their place (justify the size)

### 3. Security

- Hardcoded secrets, API keys, JWT secrets, DB URIs
- Weak authentication logic (no rate limit, weak password floor, plaintext password compare)
- Missing authorization on protected routes
- Missing input validation (no schema, no length cap, no type check)
- Unsafe APIs (`eval`, `new Function`, `child_process` with user input, `dangerouslySetInnerHTML` without sanitization, `pickle.loads` on untrusted data)
- XSS risks (un-escaped user input rendered as HTML, missing CSP)
- Prompt injection risks (user input concatenated into system-bearing prompts, user-editable prompt templates)
- Insecure file handling (`path.join` with user input passed to a shell, path traversal, world-writable temp files)

### 4. Performance

- Unnecessary loops or nested loops over the same collection
- Duplicate database or API calls when one would do
- Expensive operations inside loops (file I/O, regex compile, embedding calls)
- Large object creation that could be lazy
- Missing caching opportunities for repeated identical requests

### 5. Error Handling

- Missing try/catch around calls that can throw (network, disk, JSON parse)
- Poor exception handling (bare `except:` or `except Exception:` that swallows context)
- Stack traces exposed in HTTP responses
- Generic error responses that hide the real cause from operators
- Missing logging for errors that need to be diagnosable post-hoc

### 6. Maintainability

- Readability (consistent indentation, sensible line length, no nested ternaries)
- Modular code (small files, single responsibility, named exports)
- Consistent formatting (matches the surrounding code; no mix of tabs and spaces)
- Consistent naming (camelCase in JS, snake_case in Python, PascalCase for React components)
- Documentation updates when behavior or APIs change

### 7. Project Compliance

- Matches the conventions of the AI Recruiter Screening System (Express on Node, FastAPI on Python, Vite + React, pytest for tests)
- Does not break the existing architecture (no new top-level framework, no new build tool, no new package manager)
- Does not introduce a parallel way to do something the codebase already does (two HTTP clients, two config loaders, two logger setups)
- Updates `.gitignore` when introducing a new artifact directory
- Adds or updates tests when changing behavior

### 8. Testing

- Missing unit tests for new or changed logic
- Missing integration tests for new endpoints, hooks, or service boundaries
- Missing regression tests for bug fixes
- Existing tests that should be updated to reflect the change
- Tests that do not actually assert the behavior they claim to
- Test fixtures that drift from production behavior

### 9. Documentation

- README updates when public-facing behavior, setup, or usage changes
- API documentation for new endpoints, request/response shapes, or error codes
- Environment setup (`.env.example`, required env vars, dependency installation)
- Developer documentation (architecture, decisions, contributor guidance)
- Changelog entries when the project maintains one

## Severity rules

Every finding gets one of three severities:

- **High** - must fix before merge. Security issues, broken functionality, missing validation on user input, anything that lets a user reach a state the system cannot recover from.
- **Medium** - should fix before merge. Performance problems, missing error handling on a known failure mode, an architectural rule violation that will hurt later.
- **Low** - nice to fix. Naming, minor duplication, missing comments, formatting drift.

If the LLM is not sure whether something is a real issue, it is **not** a finding. The skill marks it as `Needs Manual Verification` in the report and stops there. Fabricating issues to look thorough is worse than missing a finding.

## Findings

Each finding uses this shape:

- **[Severity] Category** - `path/to/file.js:lineRange`
  - Explanation: <one or two sentences describing what is wrong>
  - Why it matters: <one sentence on the real-world consequence>
  - Recommended fix: <one or two sentences describing how to address it>

Findings are grouped by severity: **High Priority Issues**, **Medium Priority Issues**, **Low Priority Suggestions**. Inside each group, findings are ordered by file path, then by line number.

## Safe review rules

The model must:

- Never echo a secret value. Cite the file:line and the category; do not quote the secret itself.
- Never output a password, API key, JWT, or DB URI in the report. Use placeholders like `[REDACTED: high-entropy hex string]`.
- Never output PII found in test fixtures. Cite the file:line and the category; do not quote the value.
- Never fabricate findings. If the inspected code does not show a problem, do not write one.
- Clearly label uncertain observations as **Needs Manual Verification**. The user will check them.
- Never modify source code automatically. Recommendations only.
- Only provide recommendations. The developer decides what to do.

## Code Quality Summary

Replace numeric scoring with one of four qualitative ratings:

- **Excellent** - zero High, zero Medium, zero or one Low.
- **Good** - zero High, one or two Medium, any number of Low.
- **Fair** - zero High, three or more Medium, any number of Low.
- **Poor** - one or more High.

The rating is independent of the Verdict. A `Poor` rating forces `Request Changes`; the other three are compatible with either `Approve` or `Approve with Suggestions`.

## Verdict

The Verdict uses GitHub-style review terminology:

- **Approve** - the change is safe to merge as-is.
- **Approve with Suggestions** - safe to merge; the developer should look at the findings but is not blocked.
- **Request Changes** - the change is not safe to merge; one or more High findings must be fixed first.

The Verdict rule:

- `Request Changes` - one or more High findings.
- `Approve with Suggestions` - one or more Medium findings, zero High.
- `Approve` - zero High, zero Medium.

The pre-push hook blocks the push only when the Verdict is `Request Changes`. The other two are non-blocking.

## Output format

```
# Code Review Report

## Executive Summary
<one paragraph: what was reviewed, the Code Quality Summary, the Verdict,
and the top 1-3 things the developer should look at first>

## Files Reviewed
<bulleted list of every file inspected; mark "binary, skipped" if applicable>

## High Priority Issues
- **[High] Category** - `path/to/file.js:lineRange`
  - Explanation: ...
  - Why it matters: ...
  - Recommended fix: ...

## Medium Priority Issues
- (same shape)

## Low Priority Suggestions
- (same shape)

## Best Practice Recommendations
<bulleted list, no specific file:line, no severity. Style and convention
observations that apply project-wide.>

## Items Needing Manual Verification
<bulleted list of uncertain observations. Each line cites the file:line
and what the LLM was not sure about. Empty section if nothing is
uncertain.>

## Code Quality Summary
<Excellent | Good | Fair | Poor>

## Verdict
<Approve | Approve with Suggestions | Request Changes>
```

## Hook integration

When invoked by the pre-push hook, the LLM also writes one extra line at the end of the report:

```
VERDICT: <Approve|Approve with Suggestions|Request Changes>
```

The hook reads the **last** line of `.code-review/last-report.md`, strips the `VERDICT:` prefix, and exits non-zero only on `Request Changes`. On `Approve` or `Approve with Suggestions`, the push proceeds and the report is the developer's record.

## Verify before acting

The skill produces findings; the developer decides what to fix. Before merging:

1. Open every High and Medium finding's cited file and line.
2. Confirm the issue exists as described.
3. Test the recommended fix in a non-production environment.
4. For any finding marked `Needs Manual Verification`, decide manually.
