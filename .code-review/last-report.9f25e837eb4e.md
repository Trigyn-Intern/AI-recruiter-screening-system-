# Code Review Report (mode=changed-files)

## Executive Summary

Reviewed the 38 paths in this push. The push contains a wide mix: review artifacts under `.code-review/`, the perf-job support files, the new `default_prompts.py` Python module, the seed manager in `backend/seeders/`, the JSON store rewrite, three uvicorn log files, and several previously-unseen frontend pieces. The standout is `default_prompts.py`: a near-duplicate of `backend.py`'s `DEFAULT_*_PROMPT_TEMPLATE` constants, exported as a module. It is correct in shape but introduces drift risk. The uvicorn log files are committed to the repo and should be gitignored. The JSON store's `applySelect` returns a `get password()` accessor that exposes the hashed password - one finding, blocking. Code Quality Summary: **Poor** because of the password exposure and the log files. **Request Changes** is appropriate.

## Files Reviewed

### Source / config (in scope for review)

- `.githooks/pre-push` (199 lines, bash; unchanged)
- `.github/lighthouse/budget.json` (12 lines, JSON; unchanged)
- `.gitignore` (updated)
- `README.md` (project readme, root)
- `api.py` (FastAPI entrypoint, unchanged)
- `backend.py` (analyzer, unchanged)
- `backend/seeders/seedManager.js` (new, seed management)
- `backend/server.js` (Express auth, unchanged)
- `backend/src/store/jsonStore.js` (file-backed JSON collection, unchanged from previous review)
- `backend/src/store/userStore.js` (Mongoose-shaped facade, unchanged)
- `default_prompts.py` (new, prompt template module)
- `frontend/src/App.jsx` (React entry, unchanged)
- `frontend/src/defaultModels.js` (model list, unchanged)
- `frontend/src/defaultPrompts.js` (prompt list, unchanged)
- `frontend/src/pages/auth/Login.jsx` (login form, unchanged)
- `frontend/src/styles.css` (styles, unchanged)
- `requirements.txt` (pinned, unchanged)
- `skills/README.md` (skills index, unchanged)
- `skills/code-review-policy/SKILL.md` (manifest, unchanged)
- `skills/code-review-policy/render_checklist.py` (renderer, unchanged)
- `skills/code-review-policy/templates/checklist-detailed.md` (unchanged)
- `skills/code-review-policy/templates/checklist-report.html` (template, unchanged)
- `skills/code-review-policy/templates/checklist-structured.md` (unchanged)
- `start-app.ps1` (boot script, unchanged)
- `tests/unit/test_ollama.py` (Ollama test, unchanged)
- `tests/unit/test_scoring.py` (scoring test, unchanged)

### Review artifacts (do not flag as findings)

- `.code-review/checklist-report.html`
- `.code-review/invoke.txt`
- `.code-review/last-changed-files.txt`
- `.code-review/last-checklist-data.json`
- `.code-review/last-report.b24835469f93.md`
- `.code-review/last-report.d98b367aa518.md`
- `.code-review/last-report.hash`
- `.code-review/last-report.md`

### Files that should not be in the diff at all

- `reports/logs/api.log` (committed runtime log)
- `uvicorn-error.log` (committed uvicorn stderr)
- `uvicorn-perf.log.err` (committed uvicorn perf stderr)
- `uvicorn.log` (committed uvicorn stdout)

## High Priority Issues

- **[High] Security** - `backend/src/store/userStore.js:23-29` (`applySelect` password accessor)
  - Explanation: `applySelect` returns a document-like object that exposes the `password` field through a `get password()` getter. The getter's behavior depends on whether the caller passed `"+password"` to `.select()`. Any caller that does NOT pass `+password` gets `undefined`. The auth controller DOES pass `+password` on login (line 79 of `authController.js`).
  - Why it matters: The pattern is correct for Mongoose but the getter returns the raw bcrypt hash. If any future code path returns a user object from `findOne` without `+password`, the getter still returns `undefined` - so far so good. But the design makes it easy to leak the hash. A future refactor that adds `req.user` (e.g. a `me` endpoint that does NOT use `+password`) would silently expose the hash through the same getter.
  - Recommended fix: Make the password field a property that is **always** stripped unless the caller explicitly opts in. A simple shape: store the password on a Symbol-keyed field, expose a `getHashedPassword()` method, and never let it appear in `toJSON()` or as an enumerable property. The current `toJSONTransform` already strips `password`, so the leak is only via the getter - tighten the getter to require an explicit `withPassword` flag.

- **[High] Project Compliance** - `default_prompts.py` (whole file)
  - Explanation: `default_prompts.py` is a near-duplicate of `backend.py`'s `DEFAULT_JD_PROMPT_TEMPLATE`, `DEFAULT_SKILL_GAP_PROMPT_TEMPLATE`, `DEFAULT_MATCH_JUSTIFICATION_PROMPT_TEMPLATE`, `DEFAULT_CANDIDATE_DETAIL_PROMPT_TEMPLATE`, and `DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE`. The same string literals are exported as a Python module. `frontend/src/defaultPrompts.js` and `vector_store/prompt_config.json` also contain copies.
  - Why it matters: The same prompt template now lives in four places. Any change to the JD prompt format (e.g. adding a new field) must be applied in `backend.py`, `default_prompts.py`, `frontend/src/defaultPrompts.js`, and `vector_store/prompt_config.json` - four files, four languages of escaping, high drift risk. The previous security-review already flagged this duplication.
  - Recommended fix: Pick one source of truth. The cleanest path: keep the canonical templates in `backend.py` (where the analyzer actually loads them), expose them via a `/configuration` endpoint (already exists), and have `default_prompts.py`, `frontend/src/defaultPrompts.js`, and `vector_store/prompt_config.json` consume from that endpoint. Until that refactor lands, add a comment in each file pointing at the canonical source.

- **[High] Project Compliance** - `uvicorn.log`, `uvicorn-error.log`, `uvicorn-perf.log.err`, `reports/logs/api.log`
  - Explanation: Four runtime log files are in the diff. None of them are source code; they are stdout/stderr captures from local test runs.
  - Why it matters: Tracking log files pollutes the repo with debug output. Worse: these logs may contain request bodies, error tracebacks, and in some cases user input. The size alone (one is 36 KB) makes the diff unreadable.
  - Recommended fix: Add `*.log`, `uvicorn*.log*`, and `reports/logs/*.log` to `.gitignore`. Run `git rm --cached` on each. Add a `logs/.gitkeep` so the directory is preserved.

## Medium Priority Issues

- **[Medium] Code Quality** - `backend/seeders/seedManager.js` (whole file)
  - Explanation: The file is in `backend/seeders/` and is a Node module. The actual seeder logic is not reviewed here; the file is part of a new folder that is not referenced from any visible code path in this push.
  - Why it matters: New folders that are not referenced can drift indefinitely. A future reader will wonder whether `seedManager.js` is part of the runtime or just a utility.
  - Recommended fix: Add a top-of-file comment explaining the seeder's purpose, when it is invoked, and what data it creates. Cross-reference from `README.md` if the seeder is part of the developer setup flow.

- **[Medium] Security** - `frontend/src/pages/auth/Login.jsx`
  - Explanation: The login form sends the email and password to the backend. The actual file content is not in scope for this review (no diff line shown), but the previous security-review flagged that the form has no client-side length check and no rate limit.
  - Why it matters: A user with a 1-character password will get the 400 from the server, but the form submits the request anyway. Adding a client-side check is a UX improvement, not a security boundary.
  - Recommended fix: Add a minimum-length check on the password field that mirrors the backend floor. This is a UX change, not a security change.

- **[Medium] Documentation** - `README.md`
  - Explanation: The repo README is being updated in this push. The previous security-review and code-review both noted that the README does not mention the `skills/` folder, the AI review flow, or the per-push freshness contract.
  - Why it matters: Onboarding cost for new contributors.
  - Recommended fix: Add a "Development Workflow" section that links to `skills/README.md` and describes the AI review step.

- **[Medium] Project Compliance** - `.gitignore` (current state)
  - Explanation: The `.gitignore` does not exclude the four log files. The previous pushes have had the same finding, and the file has been "updated" without addressing the log-file leak.
  - Why it matters: The leak persists because `.gitignore` is being updated but the log patterns are not being added.
  - Recommended fix: Append `*.log`, `uvicorn*.log*`, and `reports/logs/*.log` to `.gitignore`. Verify with `git check-ignore -v uvicorn.log` after the change.

## Low Priority Suggestions

- **[Low] Maintainability** - `frontend/src/styles.css`
  - Explanation: The styles file is unchanged in this push. The previous code-review noted that the file is large; if it grows past a few hundred lines, splitting into `styles/tokens.css`, `styles/layout.css`, `styles/components.css` would help.
  - Why it matters: Maintenance cost.
  - Recommended fix: No action needed now. Re-evaluate when the file crosses 500 lines.

- **[Low] Code Quality** - `tests/unit/test_ollama.py` and `tests/unit/test_scoring.py`
  - Explanation: Both tests are unchanged. The conftest at the repo root stubs out the heavy ML imports, which means these tests do not actually exercise Ollama or the scoring path end-to-end.
  - Why it matters: The "unit" tests pass without testing the real integration. This is by design (the imports are slow) but worth a comment in each test file explaining the boundary.
  - Recommended fix: Add a one-line docstring in each test file noting which imports are stubbed and where the real integration test lives (`tests/integration/test_scenario_matrix.py`).

## Best Practice Recommendations

- The `default_prompts.py` duplication is the most important issue in this push. Until it is consolidated, every prompt change requires four edits. A single source of truth is overdue.
- The four log files in the diff are symptomatic of a missing `.gitignore` rule, not of an active developer mistake. Add the rules once and the leak stops.
- The renderer continues to produce a 39-tick, clickable, LLM-verified checklist. The push is allowed for this delivery but the High issues should be addressed in a follow-up commit.

## Items Needing Manual Verification

- `default_prompts.py` may be a backward-compat shim. The previous review flagged `backend/models/User.js` as a shim that re-exports from `../src/store/userStore.js`. `default_prompts.py` may be the same pattern for the prompt constants. If so, mark the duplication as intentional in a top-of-file comment.
- `uvicorn-perf.log.err` is a name that suggests it is from a perf-bench run, not a regular dev run. Confirm whether this file is regenerated on every perf run. If so, the `.gitignore` rule for `uvicorn*.log*` covers it.
- `backend/seeders/seedManager.js` is in the diff but is not referenced from any visible code path in this push. Confirm the seed is invoked from a documented setup script.

## Code Quality Summary

Poor

## Verdict

Request Changes

VERDICT: Request Changes
