# Skills

LLM-driven skills for the AI Recruiter Screening System. Each skill is a markdown manifest the model reads at runtime. There is no CLI, no runner, no registry, no Docker image. The "execution" is the model doing the reasoning.

## security-review

`skills/security-review/SKILL.md` covers five security areas:

- `auth-review` - Express authentication and authorization
- `llm-prompt-safety` - prompt injection and unsafe LLM usage
- `secrets-hygiene` - committed secrets and weak secret config (safe mode)
- `frontend-input` - React/Vite input handling and dependency pinning
- `test-data-pii` - PII in test fixtures (safe mode)

### Invoking

- `run security-review` - runs all five reviews
- `run security-review mode=auth-review` - runs only the auth review
- `run security-review mode=secrets-hygiene` - runs only the secrets review in safe mode

### Output

Two artifacts per run:

1. **Chat findings** - inline in the conversation.
2. **Structured HTML report** - written to `skills/reports/security-review-<mode>-<date>.html`, with `skills/reports/index.html` regenerated each run.

Safe-mode runs (`secrets-hygiene`, `test-data-pii`) use redacted input data in the HTML.

## code-review-policy

`skills/code-review-policy/SKILL.md` is the AI Code Review Policy. It reviews backend, frontend, Python, GitHub workflow, and changed files. Invoked manually in chat or by the pre-push Git hook. Produces a chat report, a JSON data file, and a self-contained HTML checklist. The HTML is rendered by a deterministic Python script that the LLM never runs itself; the LLM emits one PowerShell one-liner at the end of every chat reply.

### Purpose

The skill enforces a consistent review of every change before it reaches the remote repository. It is **not** a scanner. It does not lint, format, run tests, or call any external tool. The LLM reads the changed files and produces findings in the same shape a human reviewer would.

### Review modes

- `all` - union of every other mode.
- `backend` - Node/Express backend files.
- `frontend` - React/Vite frontend files.
- `python` - Python AI modules.
- `github` - GitHub workflow and configuration files.
- `changed-files` - only the files listed in `.code-review/last-changed-files.txt`.

### Review categories

The skill checks nine categories: **Code Quality**, **Architecture**, **Security**, **Performance**, **Error Handling**, **Maintainability**, **Project Compliance**, **Testing**, and **Documentation**. Each finding includes severity, category, file, line, explanation, why it matters, and a recommended fix.

### Code Quality Summary

The summary uses one of four qualitative ratings, with no numeric score:

- **Excellent** - zero High, zero Medium, zero or one Low.
- **Good** - zero High, one or two Medium.
- **Fair** - zero High, three or more Medium.
- **Poor** - one or more High.

### Verdict

The Verdict uses GitHub-style review terminology:

- **Approve** - safe to merge as-is.
- **Approve with Suggestions** - safe to merge; developer should look at findings.
- **Request Changes** - not safe to merge; one or more High findings must be fixed first.

The Verdict is independent of the Code Quality Summary. A `Poor` summary forces `Request Changes`; the other three ratings are compatible with either of the other two verdicts.

### Invoking

In chat, the skill is generic and works with any AI coding assistant that supports skills. Invoke by name with an optional mode:

```
Invoke the Code Review Policy skill.
Invoke the Code Review Policy skill in mode=backend.
Invoke the Code Review Policy skill in mode=changed-files.
```

### Output: chat + JSON + HTML (no manual run of the renderer)

Every invocation produces three artifacts in a single LLM pass. The LLM does not run the renderer itself; it gives the user one PowerShell one-liner to paste.

1. **Chat report** - the full review inline in the conversation, ending with `VERDICT: <verdict>` on the last line.
2. **JSON data file** - `<repo>\.code-review\last-checklist-data.json`. The LLM writes this from the same review that appears in chat. Every section of the JSON is populated; the renderer does not need to invent any data.
3. **HTML checklist report** - written to `<repo>\.code-review\checklist-report.html`. Self-contained, no external assets, no JS, opens offline in a browser. 39 checkboxes in 6 sections, plus the structured table from the review.

The renderer one-liner, emitted verbatim at the end of the chat reply, is:

```powershell
& ".\venv\Scripts\python.exe" ".\skills\code-review-policy\render_checklist.py" `
  --structured ".\skills\code-review-policy\templates\checklist-structured.md" `
  --detailed   ".\skills\code-review-policy\templates\checklist-detailed.md" `
  --data       ".\.code-review\last-checklist-data.json" `
  --output     ".\.code-review\checklist-report.html"
```

Run it from inside the repo root. The relative paths are anchored with `.\` so PowerShell's parser does not see the trailing dash on the project folder as a parameter. For a blank printable template (no review, just the boxes), drop the `--data` argument.

### LLM-only checking contract

The detailed checklist (39 boxes across 6 sections) is ticked by the LLM, not by the user. The user opens the rendered HTML to review the LLM's work, not to do the review themselves. The renderer pre-ticks every box the LLM added to the `checkedItems` array in the JSON data file and adds a small green `verified by LLM` badge next to each ticked item.

### Safe review rules

The skill never echoes secrets, never fabricates findings, never outputs PII, never modifies code, and only provides recommendations. Uncertain observations are labeled `Needs Manual Verification` instead of being reported as findings.

### Developer workflow

```
Developer writes code
        |
git add
        |
git commit
        |
pre-commit hook         <-- formatting, linting, Python syntax
        |                   (no LLM, runs in <1 second)
        v
git push
        |
pre-push hook           <-- writes changed-files list, blocks until
        |                   the developer pastes an AI review into
        v                   .code-review/last-report.md
Push to GitHub          <-- the hook reads the final VERDICT: line
        |                   and blocks only on 'Request Changes'
        v
GitHub Actions          <-- CI, unit tests, security scans, build,
                            deployment validation
        |
Merge Pull Request
```

### Relationship between AI Skill, Git Hooks, and GitHub Actions

- **AI Skill** (`skills/code-review-policy/`) - LLM-driven contextual review. Catches things scanners cannot: architectural drift, missing tests for a new feature, unclear naming, documentation gaps. The reasoning is qualitative. Produces a chat report and an HTML checklist.
- **Git Hooks** (`.githooks/`) - Local gate at commit and push time. Run in <1 second. The pre-commit hook is purely mechanical. The pre-push hook is the bridge that turns an AI review into a workflow gate.
- **GitHub Actions** (`.github/workflows/`) - Server-side CI. Deterministic, fast, exhaustive. Unit tests, dependency checks, static analysis, build verification, deployment validation.

The three layers do not duplicate each other:

| Layer | Purpose | Speed | Deterministic | Catches |
|---|---|---|---|---|
| AI Skill | Contextual reasoning + HTML report | Seconds | No | Architecture, intent, documentation, design |
| Git Hooks | Local gate at commit/push | <1s | Yes | Format, lint, syntax, missing review |
| GitHub Actions | Server-side CI | Minutes | Yes | Tests, deps, security, build |

The AI Skill complements CI by providing the reasoning CI cannot do. CI complements the AI Skill by providing the deterministic checks the LLM cannot do.

### Git hooks

`.githooks/pre-commit` runs formatting, linting, and a Python syntax check on staged files. It blocks direct commits to `main`.

`.githooks/pre-push` writes the changed-file list to `.code-review/last-changed-files.txt` and an invocation prompt to `.code-review/invoke.txt`. The developer runs the AI review in chat, saves the report to `.code-review/last-report.md`, and the hook reads the final `VERDICT:` line. `Request Changes` blocks the push. The other two verdicts allow the push. `AI_SKIP_PRE_PUSH=1` overrides the hook in emergencies.

To install the hooks for this repo:

```bash
git config core.hooksPath .githooks
```

### Reports catalog (single source of truth)

The recruiter-side dashboard and the testing dashboard each render a "Reports & test runs" panel. They share the same shape but live in two files; keep them in sync by editing this README, not the JSON.

- **Recruiter-side static catalog**: `frontend/public/reports.json` (consumed by `frontend/src/pages/dashboard/ReportsPanel.jsx`).
- **Testing-side catalog**: `frontend-test/src/reportCatalog.js` (consumed by the testing dashboard on :5174). This catalog also carries the `command` and `cwd` for the "Run" button; the testing dashboard derives the project root from `import.meta.url` so the catalog is portable across machines.

The two catalogs must agree on:

- Report `id`, `name`, `category`, `prerequisites`, and `expectedOutput`.
- The `command` string (must not embed secrets; reference env vars instead).
- The artifact path (relative to the repo root).

When you add a new report, update **both** files in the same push, or note the divergence in the code-review report.

## Verify before acting

Findings from these skills are hints to investigate, not verified issues. Always open the cited code, confirm the issue exists, and test the suggested fix before merging.

## Opening reports

PowerShell:
```powershell
Start-Process .\skills\reports\index.html
Start-Process .\skills\code-review-policy\templates\checklist-report.html
```

bash / Git Bash:
```bash
open skills/reports/index.html
open skills/code-review-policy/templates/checklist-report.html
```
