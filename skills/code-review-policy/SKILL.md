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


## Templates

The skill ships with two reference templates in `skills/code-review-policy/templates/`. The LLM does not need to read them to follow the manifest, but they are the canonical shapes for a structured checklist report.

- `checklist-structured.md` - templated report with placeholders for project name, reviewer, code quality rows, security checks, performance checks, style and best practices, test coverage, additional reviewer feedback, and approval. Use this when a single reviewer wants a printable, table-shaped record of a pass over a PR.
- `checklist-detailed.md` - exhaustive category-by-category checklist covering Correctness, Security, Performance, Testing, Readability and Maintainability, and API and Interface Design. Use this when the developer wants a "tick every box" pass before opening a PR, or when a junior reviewer needs the full list in front of them.

When the user asks for a "checklist report" or a "Code Review Checklist," produce both: the structured template filled in with concrete findings, plus the detailed checklist with the boxes checked based on the same review.




## Auto-render (no manual run)

The skill ships a single PowerShell one-liner that the LLM emits in chat every time it produces a review. The user pastes the one-liner once; the renderer regenerates `skills/code-review-policy/templates/checklist-report.html` from the JSON data the LLM just wrote. The one-liner is fully derived from `SKILL.md` - the user never has to remember or type it.

### One-liner template (what the LLM emits)

```powershell
& "<repo>\venv\Scripts\python.exe" "<repo>\skills\code-review-policy\render_checklist.py" --structured "<repo>\skills\code-review-policy\templates\checklist-structured.md" --detailed "<repo>\skills\code-review-policy\templates\checklist-detailed.md" --data "<repo>\.code-review\last-checklist-data.json" --output "<repo>\skills\code-review-policy\templates\checklist-report.html"
```

`<repo>` is the absolute path of the project root (the folder that contains `skills/`). The LLM resolves it from the current working directory or from the manifest's location. The LLM does NOT leave `<repo>` as a literal in the chat - it substitutes the real path before emitting.

### What the LLM does, every review

1. Build the review in chat as usual. The LLM still produces the chat report, the `VERDICT:` line on the last line, the JSON data file, and the diff hash.
2. Save the JSON to `<repo>\.code-review\last-checklist-data.json` (the folder is created by the hook, gitignored).
3. Save the report to `<repo>\.code-review\last-report.md` with the trailing `VERDICT:` line.
4. Save the diff hash to `<repo>\.code-review\last-report.hash`.
5. Emit the one-liner from the template above, with `<repo>` replaced by the real absolute path. The user pastes it once. The renderer overwrites `checklist-report.html` with the populated version.
6. On non-Windows hosts, the LLM emits the equivalent bash form (`python` instead of `python.exe`, forward slashes). The manifest tells the LLM to detect the host.

### Empty template (no review data)

When the user asks for a blank printable checklist ("just the boxes, no review"), the LLM emits the one-liner WITHOUT `--data`:

```powershell
& "<repo>\venv\Scripts\python.exe" "<repo>\skills\code-review-policy\render_checklist.py" --structured "<repo>\skills\code-review-policy\templates\checklist-structured.md" --detailed "<repo>\skills\code-review-policy\templates\checklist-detailed.md" --output "<repo>\skills\code-review-policy\templates\checklist-report.html"
```

The renderer produces the 39-checkbox blank template ready to tick.

### What the LLM does NOT do

- The LLM never executes the renderer itself. The user runs the one-liner in a terminal. The skill stays LLM-driven; the renderer is deterministic.
- The LLM never edits the markdown templates by hand. The renderer is the single source of truth for the HTML shape.
- The LLM never reads the produced HTML back into the conversation. The user opens it in a browser.
- The LLM never asks the user to type the one-liner from memory. The one-liner is always emitted in the chat reply, in full, with paths substituted.

### Files this section creates or expects

- `<repo>\skills\code-review-policy\templates\checklist-report.html` - the rendered report, overwritten on every render.
- `<repo>\.code-review\last-checklist-data.json` - the JSON the LLM writes when a review is produced. Optional; absent when the user only wants the blank template.

### Verify before rendering

Before the LLM emits the one-liner, it should:

1. Confirm the JSON it wrote to `last-checklist-data.json` is valid (no trailing commas, all keys quoted).
2. Confirm the one-liner it is about to emit has the correct absolute paths (no `<repo>` placeholder left in).
3. Re-state the one-liner in the chat so the user can copy-paste it without scrolling back.

### One-liner as part of the chat response

The LLM always ends its chat response with the one-liner, on its own line, in a fenced code block so the user can copy it cleanly. Example closing of a chat response:

```
[review body here]



VERDICT: Approve with Suggestions

## Render the checklist report

Run this one-liner to populate `checklist-report.html` from the JSON above:

```powershell
& "D:\trigyn\trigyn project\AI-recruiter-screening-system-\venv\Scripts\python.exe" "D:\trigyn\trigyn project\AI-recruiter-screening-system-\skills\code-review-policy\render_checklist.py" --structured "D:\trigyn\trigyn project\AI-recruiter-screening-system-\skills\code-review-policy\templates\checklist-structured.md" --detailed "D:\trigyn\trigyn project\AI-recruiter-screening-system-\skills\code-review-policy\templates\checklist-detailed.md" --data "D:\trigyn\trigyn project\AI-recruiter-screening-system-\.code-review\last-checklist-data.json" --output "D:\trigyn\trigyn project\AI-recruiter-screening-system-\skills\code-review-policy\templates\checklist-report.html"
```
```

The user pastes the line, the HTML is regenerated, the push proceeds.

## Per-push freshness contract

The pre-push hook blocks the push unless the report is **fresh** for the current diff. A report is fresh when its diff hash matches the hash of the changed-files list about to be pushed.

### What the LLM must do, every time it produces a report

1. Build the JSON for the renderer and save it to `<repo>/.code-review/last-checklist-data.json`.
2. Save the report to `<repo>/.code-review/last-report.md` with a trailing `VERDICT:` line.
3. Save the diff hash to `<repo>/.code-review/last-report.hash` so the next push can verify freshness. The hash is computed by the hook and is shown in the chat when the user pastes the invocation prompt. The LLM reads the hash from the prompt and writes it to the file.

Concretely, when the user pastes the contents of `<repo>/.code-review/invoke.txt`, the prompt contains a line like:

```
Diff hash: 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
```

The LLM extracts that hash, saves the report, and then writes:

```
echo 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08 > <repo>/.code-review/last-report.hash
```

If the user is on Windows PowerShell, the equivalent is `Set-Content -Path <repo>/.code-review/last-report.hash -Value <hash>` (no `echo` quoting issues).

### What the hook does

- On every `git push`, the hook recomputes the diff hash from the current `git diff` against the upstream branch.
- If a report exists from a previous push, the hook archives it to `<repo>/.code-review/last-report.<oldhash>.md` and deletes `<repo>/.code-review/last-report.md` and `<repo>/.code-review/last-report.hash`. The push is blocked until a fresh report is written.
- If a report exists but its hash does not match the current diff, the push is blocked. The developer must regenerate the report.
- If the report matches, the hook reads the `VERDICT:` line and either allows the push or blocks it according to the verdict rules.

### Why this matters

Without the hash check, the developer can save a report once, then push any number of unrelated commits and the old report stays valid. With the hash check, every push must be paired with a fresh review. The dependency graph between "what code is about to be pushed" and "what was reviewed" is enforced by the hook, not by the developer's memory.

### What the LLM does NOT do

- The LLM never recomputes the diff hash. The hook is the only source of truth for "what is about to be pushed." The LLM only copies the hash from the prompt into `<repo>/.code-review/last-report.hash`.
- The LLM never edits an existing report to make it match a new diff. A stale report is archived, the LLM produces a new one.

### File layout for the per-push flow

```
<code-review dir>/
├── last-changed-files.txt            <-- written by the hook every push
├── invoke.txt                        <-- written by the hook every push
├── last-report.md                    <-- the LLM writes this fresh every push
├── last-report.hash                  <-- the LLM writes the diff hash here
├── last-checklist-data.json          <-- the LLM writes the JSON for the renderer
└── last-report.<oldhash>.md          <-- archives from previous pushes
```


