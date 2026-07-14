---
name: code-review-policy
description: LLM-driven code review policy for the AI Recruiter Screening System. Reviews backend (Node/Express), frontend (React/Vite), Python AI services, GitHub workflow files, configuration, and tests. Invoked manually in chat or by the pre-push Git hook. Never executes scanners and never modifies code automatically. Always produces three artifacts in one LLM pass (chat report, JSON data file, checklist HTML) and ends the chat reply with the renderer one-liner.
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
8. After saving the report and the JSON, emit the renderer one-liner as the last block of the chat reply. The user pastes it once and `checklist-report.html` is regenerated from the JSON.

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
- Unsafe APIs (`eval`, `new Function`, `child_process` with user input, `dangerouslySetInnerHTML` without escaping)
- Logging passwords, tokens, PII
- File-system paths that are not normalized or sandboxed (path-traversal)
- CORS misconfiguration (wildcard origin with credentials, allow-list missing entries)
- Cookies missing `httpOnly` / `secure` / `sameSite` when they hold session data

### 4. Performance

- N+1 query patterns
- Synchronous file I/O on a request path
- Unbounded loops or recursion
- Missing pagination on list endpoints
- Missing database indexes for the queries the code runs
- Redundant re-renders or re-computations in React (missing memoization, unstable props)
- Unbounded data structures in memory (large lists loaded whole)

### 5. Error Handling

- Swallowed exceptions (`catch(e) {}` with no log and no rethrow)
- Unhandled rejections
- Timeouts missing on external calls
- 5xx responses leaking stack traces or `err.message` from unexpected exceptions
- Default fallbacks that hide real errors

### 6. Maintainability

- Hardcoded paths that should be config (absolute Windows paths in JS, for example)
- Magic numbers without named constants
- Inconsistent error response shape across endpoints
- Comments that narrate the code instead of explaining intent
- Public API surface that breaks without a deprecation note

### 7. Project Compliance

- `.gitignore` does not exclude runtime artifacts (log files, `__pycache__`, `node_modules`, `.benchmarks`)
- Duplicated source-of-truth files (prompt templates in four places, default fixtures in two)
- Secrets in version control
- Large committed binaries (PDFs of resumes, screenshots, recorded video)
- Commit messages that do not name the changed area

### 8. Testing

- New behavior without a test
- Tests that only cover the happy path
- Tests that test implementation (private helpers, internal store names) instead of behavior
- Test data that only works with `id = 1`
- Missing regression test for a bug fix
- Flaky tests (time-based, network-dependent) without markers

### 9. Documentation

- New public function without a one-line docstring or JSDoc
- README sections that drift from the code (e.g. commands that no longer exist)
- API endpoints added without a request/response example
- Setup steps that assume pre-installed tools the README never lists
- Internal helpers exported with no usage guide

## Severity rules

- **High** - the bug is reachable today, has user-facing impact, and the fix is small. Block the push.
- **Medium** - the bug is reachable today, but the blast radius is limited; or the bug is a real risk for a future refactor. Document and ship behind a follow-up issue.
- **Low** - the bug is a style/maintenance issue with no current user impact. Note it; do not block the push.

A finding must be reachable from the code paths in this push. Do not flag patterns that exist elsewhere in the repo but are not part of this diff unless they are in the explicitly listed files (e.g. `mode=changed-files`).

## Findings

Each finding uses this shape:

```
- **[Severity] Category** — `path/to/file.js:lineRange`
  - Issue: one sentence describing what is wrong.
  - Why it matters: one sentence on impact.
  - Suggested fix: one or two sentences describing how to address it.
  - Status: present | absent | needs verification
```

Severity is one of `High`, `Medium`, `Low`. If a category has no findings, return `No findings.` under that heading.

## Safe review rules

- The skill never echoes secrets, tokens, JWT secrets, or bcrypt hashes in chat.
- The skill never fabricates findings. If you are not sure, label `Needs Manual Verification` and explain what to check.
- The skill never outputs PII. If a finding requires quoting user input, redact it (`[REDACTED]`).
- The skill never modifies code, runs tests, or executes external commands. The renderer one-liner is the only command the LLM suggests, and it is deterministic.
- The skill never edits the markdown templates by hand. The renderer is the single source of truth for the HTML shape.

## Code Quality Summary

The summary uses one of four qualitative ratings, with no numeric score:

- **Excellent** - zero High, zero Medium, zero or one Low.
- **Good** - zero High, one or two Medium.
- **Fair** - zero High, three or more Medium.
- **Poor** - one or more High.

## Verdict

The Verdict uses GitHub-style review terminology:

- **Approve** - safe to merge as-is.
- **Approve with Suggestions** - safe to merge; developer should look at findings.
- **Request Changes** - not safe to merge; one or more High findings must be fixed first.

The Verdict is independent of the Code Quality Summary. A `Poor` summary forces `Request Changes`; the other three ratings are compatible with either of the other two verdicts.

## Output format

The chat report uses this layout, in this order:

1. **Title** - `# Code Review Report (mode=<mode>)`
2. **Executive Summary** - one paragraph, 3-5 sentences.
3. **Files Reviewed** - bullet list of paths, grouped into source/config vs review-artifact.
4. **High Priority Issues** - bullet list, ordered by severity and file.
5. **Medium Priority Issues** - bullet list.
6. **Low Priority Suggestions** - bullet list.
7. **Best Practice Recommendations** - 2-4 bullets.
8. **Items Needing Manual Verification** - bullet list.
9. **Code Quality Summary** - one of the four ratings, with a one-line justification.
10. **Verdict** - one of the three verdicts.
11. Trailing line: `VERDICT: <verdict>` - read by the pre-push hook.

The report ends with `VERDICT: <verdict>` on the last line. The renderer one-liner follows in a separate fenced PowerShell block.

## Hook integration

The pre-push hook (`.githooks/pre-push`) gates every push:

- It computes the diff hash from `git diff` against the upstream.
- It writes `.code-review/last-changed-files.txt` and `.code-review/invoke.txt`.
- It blocks the push until a fresh report is written to `.code-review/last-report.md` ending with a `VERDICT:` line.
- It reads the `VERDICT:` line and exits non-zero only on `Request Changes`. On `Approve` or `Approve with Suggestions`, the push proceeds and the report is the developer's record.
- `AI_SKIP_PRE_PUSH=1` overrides the hook in emergencies.

## Verify before acting

The skill produces findings; the developer decides what to fix. Before merging:

1. Open the cited file and line. Confirm the issue exists.
2. Test the suggested fix in a non-production environment.
3. For Medium findings, open a follow-up issue so the work is not lost.

## Templates

The renderer reads from two markdown templates in `skills/code-review-policy/templates/`:

- `checklist-structured.md` - the structured summary table (Code Quality, Security, Performance, etc.).
- `checklist-detailed.md` - the 39-item detailed checklist with `<input type="checkbox">` elements.

The renderer pre-ticks every box the LLM added to the `checkedItems` array in the JSON data file. The HTML output is `checklist-report.html`.

## Auto-render: report + JSON + checklist in one LLM call

Every invocation of the skill produces three artifacts in a single LLM pass. The user pastes exactly one PowerShell line at the end of the chat reply, and the report plus the tickable checklist HTML are both on disk before the push.

### The three artifacts

1. **Chat report** - the full review inline in the conversation, ending with `VERDICT: <verdict>` on the last line. The pre-push hook reads this verdict.
2. **JSON data file** - `<repo>\.code-review\last-checklist-data.json`. The LLM writes this from the same review that appears in chat. Every section of the JSON is populated; the renderer does not need to invent any data.
3. **Checklist HTML** - `<repo>\.code-review\checklist-report.html`. Self-contained, real `<input type="checkbox">` elements (39 in the detailed section), filled-in tables in the structured section, status pills on every row.

### The single one-liner the LLM emits at the end of every chat reply

The LLM ALWAYS ends its chat response with this fenced PowerShell block, with `<repo>` replaced by the absolute path of the project root. The one-liner is the LAST block of the chat reply, after the trailing `VERDICT:` line.

```powershell
& ".\venv\Scripts\python.exe" ".\skills\code-review-policy\render_checklist.py" `
  --structured ".\skills\code-review-policy\templates\checklist-structured.md" `
  --detailed   ".\skills\code-review-policy\templates\checklist-detailed.md" `
  --data       ".\.code-review\last-checklist-data.json" `
  --output     ".\.code-review\checklist-report.html"
```

The user pastes it once, from inside `<repo>`. The relative paths are anchored with `.\` so PowerShell's parser does not see the trailing dash on the project folder as a parameter. The renderer reads the JSON, populates the structured section, renders the 39 checkboxes, and writes `checklist-report.html`.

For a blank printable template (no review, just the boxes), drop the `--data` argument.

### What the LLM does, every review, in one pass

1. Build the review in chat. Include the full Code Quality, Security, Performance, Style, Test Coverage, Final Notes, and Approval sections. Include a trailing `VERDICT: <verdict>` line on the last line.
2. From that same review, build a JSON object with every key the renderer reads. No field is left blank; if a section has no findings, write a one-line summary instead of omitting the key. The JSON shape is:

   ```json
   {
     "projectName": "AI Recruiter Screening System",
     "repositoryBranch": "origin/main",
     "reviewerName": "Code Review Policy (mode=changed-files)",
     "reviewDate": "YYYY-MM-DD",
     "hasTests": "Yes | No | Manual smoke-tested",
     "coveragePercent": "Manual",
     "manualTestNotes": "...",
     "generalChecklist": [{"item": "...", "comment": "..."}],
     "codeQuality": [{"checkItem": "...", "status": "Pass|Fail|Warn", "notes": "..."}],
     "hasSecuritySection": true,
     "securityChecks": [{"checkItem": "...", "status": "Pass|Fail|Warn", "comments": "..."}],
     "performanceChecks": [{"title": "...", "details": "..."}],
     "stylePractices": [{"practice": "...", "issuesFound": "..."}],
     "reviewerFeedbacks": [{"reviewerName": "...", "comment": "..."}],
     "finalNotes": "...",
     "approvedBy": "Code Review Policy (mode=<mode>)",
     "approvalDate": "YYYY-MM-DD",
     "mergeStatus": "Approve | Approve with Suggestions | Request Changes",
     "checkedItems": [
       "Does the code do what the PR description says it does?",
       "Are edge cases handled? (empty input, null values, boundary conditions)",
       "..."
     ]
   }
   ```

3. Save the JSON to `<repo>\.code-review\last-checklist-data.json` (the folder is created by the hook and is gitignored).
4. Save the report body to `<repo>\.code-review\last-report.md` with the trailing `VERDICT:` line.
5. Save the diff hash from the prompt to `<repo>\.code-review\last-report.hash`. The prompt (in `<repo>\.code-review\invoke.txt`) contains a `Diff hash:` line; the LLM extracts that hash and writes it.
6. Emit the one-liner above in a fenced code block at the END of the chat reply. The block is the LAST thing the user sees; the user pastes it once and both the JSON-driven report and the 39-box checklist HTML are on disk.

### What the LLM does NOT do

- The LLM never executes the renderer itself. The user runs the one-liner. The skill stays LLM-driven; the renderer is deterministic.
- The LLM never edits the markdown templates by hand. The renderer is the single source of truth for the HTML shape.
- The LLM never reads the produced HTML back into the conversation. The user opens it in a browser.
- The LLM never leaves `<repo>` as a literal in the chat. The one-liner is emitted with the real path substituted.
- The LLM never asks the user to type the one-liner from memory. The one-liner is always emitted in the chat reply, in full, with paths substituted.
- The LLM never tells the user to "save the report somewhere." The LLM writes the report itself; the user only pastes the renderer line.
- The LLM never produces a chat reply without the trailing `VERDICT:` line. The pre-push hook reads that line and would otherwise fail.

### Files this section creates or expects

- `<repo>\.code-review\last-report.md` - the chat-shaped report with trailing `VERDICT:` line. The pre-push hook reads this.
- `<repo>\.code-review\last-report.hash` - the diff hash from the prompt. The pre-push hook reads this.
- `<repo>\.code-review\last-checklist-data.json` - the JSON data the LLM writes. The renderer reads this.
- `<repo>\.code-review\checklist-report.html` - the rendered checklist. The user opens this in a browser.

### Verify before emitting the one-liner

Before the LLM emits the one-liner, it should:

1. Walk all 39 items in the detailed checklist. For each, decide: did I actually verify this during the review?
2. Add every verified item to `checkedItems` in the JSON data file. Use the exact `checkItem` string from the SECTIONS list in `render_checklist.py` when possible; the renderer's normalization handles minor wording differences.
3. Confirm the JSON it wrote to `last-checklist-data.json` is valid (no trailing commas, all keys quoted, no raw newlines inside string values).
4. Confirm the one-liner it is about to emit has the correct relative paths anchored with `.\` (no `<repo>` placeholder, no absolute paths that PowerShell will mis-parse).
5. Re-state the one-liner in the chat so the user can copy-paste it without scrolling back.

### One-liner as the closing of every chat response

The LLM always ends its chat response with the one-liner, on its own line, in a fenced code block. Example closing of a chat response:

```
[review body here]

[trailing VERDICT: line]

## Render the checklist report

Run this one-liner to populate `checklist-report.html` from the JSON above:

```powershell
& ".\venv\Scripts\python.exe" ".\skills\code-review-policy\render_checklist.py" `
  --structured ".\skills\code-review-policy\templates\checklist-structured.md" `
  --detailed   ".\skills\code-review-policy\templates\checklist-detailed.md" `
  --data       ".\.code-review\last-checklist-data.json" `
  --output     ".\.code-review\checklist-report.html"
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

## LLM-only checking contract

The detailed checklist (39 boxes across 6 sections) is ticked by the LLM, not by the user. The user opens the rendered HTML to review the LLM's work, not to do the review themselves.

### What the LLM does

After producing the chat report and the JSON data file, the LLM walks the 39 checklist items in `skills/code-review-policy/templates/checklist-detailed.md` (or the canonical SECTIONS list in `render_checklist.py`) and decides for each item: did the LLM verify this during the review? If yes, the LLM adds the exact `checkItem` string to a `checkedItems` array in the JSON data file. The renderer pre-ticks those boxes in the printable HTML and adds a small green `verified by LLM` badge next to each ticked item.

The renderer's matching is forgiving: it normalizes whitespace, lowercases, strips trailing punctuation, and also matches by 40-character prefix. So a checkedItems list with slightly different wording still ticks the right boxes.

### What the LLM does NOT do

- The LLM does not ask the user to tick boxes manually. The HTML checkboxes are present so the user can override an LLM tick (uncheck a box if they disagree), not so the user can do the review.
- The LLM does not produce an empty `checkedItems` list. If the LLM did not actually walk the checklist, it should say so in the chat reply and ask the developer to re-run the skill.
- The LLM does not include `checkItem` strings the LLM did not actually verify. A dishonest tick is worse than a missing one.

### What the user does

The user opens the rendered HTML and reviews the LLM's ticks. If the user disagrees with a tick, they uncheck the box in the browser. The user does not start from an empty checklist.

### Field in the JSON data file

```json
{
  "checkedItems": [
    "Does the code do what the PR description says it does?",
    "Are edge cases handled? (empty input, null values, boundary conditions)",
    "..."
  ]
}
```

Items not in this list render as unticked. The LLM's responsibility is to walk the 39 items and decide which ones it actually verified.

### What the user sees in the HTML

A ticked box looks like this in the rendered output:

```html
<li class="checklist-item">
  <label class="checkbox-row">
    <input type="checkbox" checked disabled />
    Does the code do what the PR description says it does?
    <span class="llm-tick">verified by LLM</span>
  </label>
</li>
```

The `disabled` attribute means the user cannot accidentally re-tick a box the LLM has marked as verified. The user CAN uncheck a box in the browser's developer tools, but the canonical record is the JSON the LLM wrote. The renderer does not read the HTML back; it always re-renders from the JSON.

### Verify before emitting the one-liner

Before the LLM emits the renderer one-liner, it should:

1. Walk all 39 items in the detailed checklist. For each, decide: did I actually verify this during the review?
2. Add every verified item to `checkedItems` in the JSON data file. Use the exact `checkItem` string from the SECTIONS list when possible; the renderer's normalization handles minor wording differences.
3. Confirm the JSON it wrote to `last-checklist-data.json` is valid.
4. Confirm the one-liner it is about to emit has the correct relative paths anchored with `.\`.

## Reports catalog (single source of truth, two views)

The recruiter-side dashboard and the testing dashboard each render a "Reports & test runs" panel. They share the same shape but live in two files; both are derived from this skill manifest, not invented by each side.

- **Recruiter-side static catalog**: `frontend/public/reports.json` (consumed by `frontend/src/pages/dashboard/ReportsPanel.jsx`).
- **Testing-side catalog**: `frontend-test/src/reportCatalog.js` (consumed by the testing dashboard on :5174). This catalog also carries the `command` and `cwd` for the "Run" button; the testing dashboard derives the project root from `import.meta.url` so the catalog is portable across machines.

When you add or remove a report, update both files in the same push, and call out the cross-file change in the code-review report so a reviewer can confirm they are still in sync.

## Renderer script

`skills/code-review-policy/render_checklist.py` is stdlib-only Python (no external deps). It reads `--data` (the JSON the LLM wrote), substitutes placeholders in the two markdown templates, and writes the HTML. It accepts the four template paths shown in the one-liner above. Drop `--data` to print a blank printable template.
