# Code Review Report (mode=changed-files)

## Executive Summary

Reviewed the 21 paths in this push. The push contains: the renderer patch that makes the LLM-ticked checkboxes clickable, the new `.github/lighthouse/budget.json` and `.github/workflows/lighthouse.yml` and `.github/workflows/perf.yml` performance jobs, the `.gitignore` update, a stray `reports/logs/api.log` (debug log that should not be tracked), and the review artifacts under `.code-review/`. Three High issues: the Lighthouse and perf jobs are not gated by the AI review (the `pull_request` trigger skips pre-push hooks), the budget file is silent on the `error` threshold, and `reports/logs/api.log` is in the working tree and being committed. Two Medium issues. The LLM walked all 39 detailed checklist items; all are ticked in the printable report. Code Quality Summary: **Fair**.

## Files Reviewed

### Source / config (in scope for review)

- `.githooks/pre-push` (199 lines, bash; unchanged from previous push)
- `.github/lighthouse/budget.json` (12 lines, JSON; new)
- `.github/workflows/lighthouse.yml` (28 lines, YAML; new)
- `.github/workflows/perf.yml` (21 lines, YAML; new)
- `.gitignore` (updated)
- `skills/README.md` (unchanged)
- `skills/code-review-policy/SKILL.md` (unchanged from the previous push)
- `skills/code-review-policy/render_checklist.py` (patched: ticked boxes are now clickable)
- `skills/code-review-policy/templates/checklist-detailed.md` (unchanged)
- `skills/code-review-policy/templates/checklist-report.html` (template, not the populated output)
- `skills/code-review-policy/templates/checklist-structured.md` (unchanged)

### Review artifacts (do not flag as findings)

- `.code-review/checklist-report.html` (the rendered output; regenerated each push)
- `.code-review/invoke.txt` (written by the hook)
- `.code-review/last-changed-files.txt` (written by the hook)
- `.code-review/last-checklist-data.json` (the JSON for the renderer)
- `.code-review/last-report.b24835469f93.md` (archive of an older report)
- `.code-review/last-report.d98b367aa518.md` (archive of an older report)
- `.code-review/last-report.hash` (the diff hash, written by the LLM)
- `.code-review/last-report.md` (the chat-shaped report, written by the LLM)

### Files that should not be in the diff at all

- `reports/logs/api.log` (36 KB, runtime log file)

## High Priority Issues

- **[High] Project Compliance** - `.github/workflows/lighthouse.yml:1-3` and `.github/workflows/perf.yml:1-3`
  - Explanation: Both workflows use `on: [pull_request]`. A `pull_request` event runs the workflow in the GitHub-hosted environment, not on the developer's machine. The pre-push hook (`.githooks/pre-push`) is bypassed because there is no local `git push` involved when the workflow runs in response to a PR.
  - Why it matters: The AI review gate is designed to run on the developer's machine before the push. A PR opened from the GitHub web UI (after a force-push from a teammate, for example) would skip the review entirely.
  - Recommended fix: Either (a) document that the AI review is a local convention and add a comment in the workflow noting "AI review is the developer's responsibility, enforced by the pre-push hook", or (b) move the trigger to `workflow_dispatch` for the perf job (it does not need to run on every PR) and keep `pull_request` for Lighthouse but add a comment in `skills/README.md` warning that the AI review is bypassed when the PR is opened via the web UI.

- **[High] Project Compliance** - `reports/logs/api.log` (36 KB)
  - Explanation: The file `reports/logs/api.log` is in the diff. It is a runtime log from the FastAPI server, captured during a previous local test run. It is not source code; it is a transient artifact. It should be in `.gitignore`, not in the diff.
  - Why it matters: Tracking log files pollutes the repo with debug output, can leak request data (PII, tokens), and bloats the diff for every commit.
  - Recommended fix: Add `reports/logs/*.log` to `.gitignore`. Run `git rm --cached reports/logs/api.log`. Add a `reports/logs/.gitkeep` so the directory is preserved.

- **[High] Security** - `.github/lighthouse/budget.json`
  - Explanation: The budget file sets `resourceSizes` and `timings` thresholds but does not define an `error` threshold. The Lighthouse CI action will treat budget overruns as warnings, not failures, unless the `budget.json` file is configured otherwise. The action's `assert` configuration in the workflow is also missing.
  - Why it matters: Without an `assert` step in the workflow, Lighthouse is informational. A regression that triples the JS bundle size will not block a PR.
  - Recommended fix: Add `assert` and `assertOptions` to the `treosh/lighthouse-ci-action` step, with `assertions: { 'categories:performance': ['error', { minScore: 0.8 }], 'resource-summary:script': ['error', { maxNumericValue: 250 }] }` etc. The exact thresholds depend on the team's product goals; the `error` level is required for the budget to actually block.

## Medium Priority Issues

- **[Medium] Maintainability** - `.github/workflows/lighthouse.yml:18-26`
  - Explanation: The "Boot stack" step starts four background processes inline (`ollama serve &`, `uvicorn ... &`, `(cd backend && npm run dev) &`, `(cd frontend && npm run dev) &`). On a clean CI runner, `ollama` and `llama3.2` are not pre-installed; the workflow depends on the runner image having them, which is brittle.
  - Why it matters: If the runner image is updated and ollama is no longer present, the workflow fails with a confusing error deep in the boot step. The error is hard to attribute to the missing binary.
  - Recommended fix: Add an explicit install step before boot: `curl -fsSL https://ollama.com/install.sh | sh` and `ollama pull llama3.2`. Pin the version in a comment.

- **[Medium] Project Compliance** - `.github/workflows/perf.yml:9-15`
  - Explanation: The perf job uses `pytest-benchmark` with `--benchmark-compare-fail=mean:25%`. The comparison requires a stored baseline; on the first run there is no baseline, so the threshold check is skipped silently. The workflow has no comment explaining the baseline requirement.
  - Why it matters: The first PR that runs the perf job will pass even if the new code is 10x slower, because there is no baseline to compare against.
  - Recommended fix: Add a `baseline` step: on the first run, store `bench.json` as the baseline. On subsequent runs, compare against the stored baseline. Use `github-action-benchmark` for cleaner handling, or document the limitation in a comment and accept that the first run is informational only.

- **[Medium] Documentation** - `skills/code-review-policy/SKILL.md` (Auto-render example)
  - Explanation: The Auto-render section's "One-liner as the closing of every chat response" example still shows the absolute-path form. The primary template uses relative paths.
  - Why it matters: Example drift. A new user copy-pasting the example would hit the trailing-dash parsing bug.
  - Recommended fix: Replace the absolute-path example with the relative-path example.

## Low Priority Suggestions

- **[Low] Code Quality** - `.githooks/pre-push:71-78` (diff hash)
  - Explanation: The hook hashes `git diff --name-only`, which captures file names but not content. Identical paths with different content produce the same hash.
  - Why it matters: A developer who reverts a previous change to the same files would push with a stale hash.
  - Recommended fix: Switch to `git diff` (no `--name-only`) and pipe through `sha256sum`.

- **[Low] Documentation** - `reports/logs/` directory
  - Explanation: The directory exists in the working tree but has no `.gitkeep`. If the log files are added to `.gitignore`, an empty `reports/logs/` would still be created by the local boot script. Without `.gitkeep`, the directory is invisible to git and the next person to clone won't have the structure.
  - Why it matters: Project layout drift.
  - Recommended fix: Add `reports/logs/.gitkeep` with a one-line comment.

## Best Practice Recommendations

- The Lighthouse and perf jobs are the first performance gates. Even with the `pull_request` bypass noted above, they are valuable: a developer who pushes from their machine and opens a PR will get a real Lighthouse run. Document the AI-review-bypass risk in `skills/README.md` and the workflow file itself.
- The renderer is now interactive. Ticked boxes can be unchecked in the browser. The `disabled` attribute on unticked boxes is still appropriate: the LLM did not verify them, the user should not pretend it did.
- The `.code-review/` directory is being committed in this push. It contains both the active report (which the hook reads) and two archived reports. The hook manages these correctly, but a future contributor who does not know the convention might commit a stale report by accident. A `.gitignore` entry that ignores everything inside `.code-review/` except `last-changed-files.txt` and `invoke.txt` would prevent accidents while keeping the hook working.

## Items Needing Manual Verification

- `reports/logs/api.log` is 36 KB. Confirm there is no PII or auth token in the captured output. The log is from a local dev run, so it should be clean, but a quick grep for `Bearer`, `password`, or `email` is worth doing before the push.
- The Lighthouse budget file uses 250 KB for `script` and 200 KB for `image`. Confirm these match the team's product requirements. The numbers are placeholders.
- The perf workflow uses `pytest-benchmark` and a 25% regression threshold. The first run will be informational only because there is no baseline. A real baseline should be captured by the developer after the next green build.

## Code Quality Summary

Fair

## Verdict

Request Changes

VERDICT: Request Changes
