# Code Review Report (mode=changed-files)

## Executive Summary

Reviewed the 17 paths in this push. The push adds CI for Lighthouse and pytest-benchmark, wires the same tools into the dashboard's Reports panel via a static `frontend/public/reports.json` catalog, fixes a manager-login bug by letting the seeder rotate `SEED_MANAGER_PASSWORD` on every restart, and refreshes the `start-app.ps1` launcher (testing dashboard on :5174, idempotent `npm install`, free stale ports, full README quick-start). The standout changes: the `seedManager.js` seeder now correctly refreshes stored credentials on every backend start, and `start-app.ps1` is genuinely a one-click stack for new users. There are still a few residuals from previous pushes: a few stray `.log` files in the working tree, four copies of the prompt templates, and the password-getter leak risk in `backend/src/store/userStore.js` (unchanged here, but worth re-flagging). Code Quality Summary: **Good** - this push closes a real authentication regression and makes the onboarding story honest. **Approve with Suggestions** is appropriate.

## Files Reviewed

### Source / config (in scope for review)

- `.github/workflows/lighthouse.yml` (CI, Lighthouse on PR)
- `.github/workflows/perf.yml` (CI, pytest-benchmark on PR)
- `README.md` (project readme, rewritten Quick Start + Configuration)
- `backend/seeders/seedManager.js` (refresh-on-restart, bcrypt rotation)
- `frontend-test/src/reportCatalog.js` (catalog of reports for the testing dashboard)
- `frontend/public/reports.json` (static catalog consumed by `ReportsPanel`)
- `frontend/src/pages/auth/Login.jsx` (collapsed manager branch, single redirect)
- `frontend/src/pages/dashboard/Dashboard.jsx` (mounts `ReportsPanel`)
- `frontend/src/pages/dashboard/ReportsPanel.jsx` (renders the catalog)
- `frontend/src/pages/dashboard/reportsPanel.css` (styling for the panel)
- `requirements.txt` (Pydantic, NumPy, PyYAML, python-dotenv, Playwright, pytest-mock, pytest-benchmark, Scalene, Safety, lighthouse, @lhci/cli, axe-playwright added)
- `scripts/run-zap.ps1` (Docker-based ZAP baseline scan)
- `start-app.ps1` (testing dashboard on :5174, idempotent npm install, port 5174 cleanup, Testing UI banner)

### Review artifacts (do not flag as findings)

- `reports/junit.json` (single passing test, kept for the catalog)
- `reports/lighthouse-report.html` (static copy for local reference)
- `skills/code-review-policy/templates/checklist-report.html` (renderer output)
- `skills/reports/index.html` (catalog of past runs)

## High Priority Issues

None. The push closes a real authentication regression (`SEED_MANAGER_PASSWORD` is now honored after the first run), makes `start-app.ps1` a genuine one-click stack for new users, and adds Lighthouse + pytest-benchmark to CI without leaking secrets or expanding the trusted surface. Items that would be High in a vacuum are already tracked in earlier reports; they were not made worse here.

## Medium Priority Issues

- **[Medium] Security** - `frontend/src/pages/dashboard/ReportsPanel.jsx` (HTML rendering of user-visible strings)
  - Explanation: the panel renders the `command` field inside `<pre><code>...r.command...</code></pre>`. The catalog is a static JSON in the repo today, but the same component will eventually receive `command` from a server endpoint. If a future server returns a malicious catalog, the `<code>` element escapes HTML by default - that is fine - but `prerequisites`, `expectedOutput`, and `artifact.lastModified` are also rendered with `{}` interpolation inside `<li>`/`<p>` and rely on React's text escaping, not on the JSON being trusted.
  - Why it matters: as long as the catalog comes from the static `frontend/public/reports.json` and the strings are written by the team, this is a non-issue. The day the dashboard fetches the catalog from `/api/reports` or any other user-influenced path, the panel must re-validate the shape and refuse to render unknown fields.
  - Recommended fix: keep the catalog contract narrow: every entry has `id`, `name`, `category`, `command`, `prerequisites[]`, `expectedOutput[]`, `actualLastRun.artifact`, `actualLastRun.exists`, `actualLastRun.lastModified`. Reject unknown fields server-side and at the parser.

- **[Medium] Security** - `frontend/public/reports.json` is shipped inside the JS bundle
  - Explanation: the dashboard reads `/reports.json` at runtime. Vite serves it from `frontend/public/`, so the file is part of the static deploy. Today it lists only commands, prerequisites, and artifact paths - no secrets, no tokens. Anyone who can read the public bundle can also read the catalog, which is by design. The risk would be if a future PR adds a row whose `command` includes a token (e.g. `curl -H "Authorization: Bearer $GITHUB_TOKEN"`).
  - Why it matters: a future PR could easily embed a long-lived token in the catalog and the dashboard would happily display it.
  - Recommended fix: add a one-line guard to the catalog's PR template: "do not put secrets in `command`; if a command needs a token, document the env var name in `prerequisites` and reference `$VAR` in the command". Optionally redact obvious secret shapes in the renderer.

- **[Medium] Security** - `.github/workflows/lighthouse.yml` uses `--headless` Chrome in CI
  - Explanation: the action invokes `treosh/lighthouse-ci-action@v11` with `assert: true` and `assertOptions: ["Categories:performance=warn"]`. The job does not pin a Chrome version or a specific Playwright build; it relies on the action's own image.
  - Why it matters: a transitive bump in the action could change the asserted score and block the PR for a non-regression. Not a security issue per se, but a stability one.
  - Recommended fix: pin `treosh/lighthouse-ci-action` to a SHA for high-confidence reproducibility, and add a small comment that explains the `assert: true` plus `assertOptions` choice (today the comment is good, but a SHA pin is missing).

- **[Medium] Code Quality** - `scripts/run-zap.ps1` mounts the report dir into the container with `:rw`
  - Explanation: line 102 uses `-v "${reportDir}:/zap/wrk/:rw"`. The script writes a file the runner user owns; outside the container the file is owned by the host user. That is correct for a single-run report, but the script does not clean up the report if a previous run aborted (ZAP writes a partial file). Subsequent runs then see a stale `zap-baseline-report.html` and might think the scan was already done.
  - Why it matters: a partial report from a crashed run can be mistaken for a fresh one.
  - Recommended fix: at the start of the run, delete any file matching `$htmlOut` so the report is guaranteed to come from the current invocation.

- **[Medium] Code Quality** - `frontend-test/src/reportCatalog.js` hardcodes the absolute Windows path
  - Explanation: line 22 sets `const ROOT = "D:/trigyn/trigyn project/AI-recruiter-screening-system-";` and uses it in the `cwd` of every command. This is fine for one developer on one machine, but anyone on a different drive, in WSL, or on macOS will get a `path not found` when they click Run.
  - Why it matters: the testing dashboard's "Run" button stops working the moment a teammate clones the repo to a different location.
  - Recommended fix: derive the root from `import.meta.url` (the file lives in `frontend-test/src/`), or read `VITE_PROJECT_ROOT` from a `frontend-test/.env`. The `path` field is already relative, so the catalog could keep `path` as a relative path and compute `cwd` at click time.

- **[Medium] Code Quality** - `start-app.ps1` resumes the python venv with backticks and `$env:`
  - Explanation: lines 119-120 build the uvicorn command with `". '$venvActivate'; `$env:ANALYZE_MAX_INFLIGHT='4'; ..."`. This works in PowerShell, but a copy-paste from the chat into a real terminal will lose the escaping. The README quick-start should be self-sufficient without copy-pasting from the launcher.
  - Why it matters: on a new contributor's machine, the only way to launch the stack is `start-app.ps1`. That is by design and fine - but a debug comment noting "if you want to run uvicorn by hand, see README > Quick Start (macOS / Linux)" would tie the two together.
  - Recommended fix: add a one-line cross-reference at the bottom of the launcher so a reader who steps through the script knows where the manual equivalent lives.

- **[Medium] Documentation** - `requirements.txt` now pins `lighthouse==12.2.1` and `@lhci/cli==0.14.0` but the README does not tell users these are run from `npx`
  - Explanation: the README's Lighthouse section gives the `lighthouse` invocation, but `@lhci/cli` is mentioned only in the CI block. A new user reading the docs will not know that `lighthouse` and `lhci` are launched via `npx --yes` locally (the `requirements.txt` entries are misleading - they look like Python packages).
  - Why it matters: a new user who runs `pip install -r requirements.txt` and then tries `python -m lighthouse` will get a `No module named lighthouse` error.
  - Recommended fix: add a short note at the top of `requirements.txt`: "the `lighthouse` and `@lhci/cli` lines are documentation; the actual Lighthouse CLI is `npx --yes lighthouse ...`". This keeps the file readable as a single source of truth.

- **[Medium] Configuration** - `frontend/public/reports.json` and the new `frontend-test/src/reportCatalog.js` describe overlapping but not identical report inventories
  - Explanation: the recruiter-side `reports.json` lists seven reports (ZAP x2, Lighthouse, perf-benchmarks, scenario-matrix, code-review, security-review). The testing-side `reportCatalog.js` lists four (HTML Report, ZAP, Lighthouse, Code Review). Both are useful, but the new user cannot tell which one drives which UI.
  - Why it matters: docs and code drift; one side will fall behind the other.
  - Recommended fix: pick one catalog as the source of truth and have the other consume it. The simplest path: keep `frontend/public/reports.json` as the recruiter-side view, and have `frontend-test/src/reportCatalog.js` only declare `command` / `cwd` for the four reports the testing dashboard knows how to run, while sharing the same metadata shape.

## Low Priority Suggestions

- **[Low] Maintainability** - `backend/seeders/seedManager.js` now mutates the cached JSON record via `JsonCollection` directly
  - Explanation: the file drops down to `new JsonCollection(usersFile)._flush()` to update the manager password, bypassing the `User` facade. This is correct (the facade has no update method) but the seeder and the `User` store now have a foot-gun relationship: if `User` later adds an `update()` method, the seeder must be migrated. The earlier review already raised this drift risk.
  - Why it matters: future maintainers will not know where the canonical update path is.
  - Recommended fix: add a one-line comment in `User` ("update is intentionally not exposed; use `JsonCollection` directly when needed") so the seeder's pattern is the documented escape hatch.

- **[Low] Maintainability** - `frontend/src/pages/dashboard/reportsPanel.css` uses `text-transform: uppercase` and a 0.06em letter-spacing on every label
  - Explanation: small but consistent - uppercase tracking is repeated across `.reports-category h3`, `.report-row h4`, and `.report-status`. That is a deliberate design choice, not a bug.
  - Why it matters: maintenance; if a future designer drops the tracking on one of the three, the visual rhythm will feel off.
  - Recommended fix: extract a CSS custom property, e.g. `--label-tracking: 0.06em;`, and apply it in the three rules.

- **[Low] Test Coverage** - no Playwright test covers the new `ReportsPanel`
  - Explanation: the `ReportsPanel` is a static panel that reads `frontend/public/reports.json`. A one-line test that asserts the panel renders the "Reports & test runs" heading and lists at least one row would catch a JSON typo and a missing `public/reports.json` deploy.
  - Why it matters: tiny, but the panel is what the user sees first; it is worth a smoke test.
  - Recommended fix: add `tests/ui/test_reports_panel.py` that boots the React app and asserts the heading and one card.

- **[Low] Documentation** - `README.md` mentions "Reports & test runs" implicitly via the dashboard but does not link to the panel in the User Guide
  - Explanation: the dashboard now embeds a reports panel that lists every command a recruiter or QA might want to run. The README's Testing section has the deep details; the Recruiter section does not mention the panel.
  - Why it matters: a recruiter who only reads the Recruiter section will not know the panel exists.
  - Recommended fix: add one sentence to the "Live Demo" or "Key Features" table: "Reports & test runs panel inside the dashboard lists every command, prereq, and artifact for ZAP, Lighthouse, pytest-benchmark, the scenario matrix, and the AI reviews."

## Best Practice Recommendations

- The `seedManager.js` rotation is the right shape: check bcrypt against the env value first, only hash and write if it does not match, log the rotation so an operator can see what happened. That is the same pattern used by production seeders and is the reason this push can be approved.
- The Lighthouse + perf CI jobs are well-scoped: they pull their own Ollama model, boot only the slice they need, and fail with a comment that names the missing prerequisite. The "wait for health endpoints" loop is a nice touch - it removes the `sleep 20` race that bites most first-time CI runs.
- `start-app.ps1` is now genuinely usable as a one-click stack. The README's "Quick Start (Windows)" section makes the steps obvious without forcing the user to read the script.

## Items Needing Manual Verification

- `reports/junit.json` in the diff is a single passing test (`test_invalid_extension`). Confirm that the scenario-matrix CI is still producing a multi-test JUnit; if so, the single-test file in the diff is only there for the catalog, and the actual CI output lives elsewhere.
- `reports/lighthouse-report.html` in the diff is a static copy. Confirm that the `.github/workflows/lighthouse.yml` job still uploads `.lighthouseci/lhr-*.html` to the GH artifacts; the working-tree copy is for local reference.
- `frontend/public/reports.json` references `pwsh scripts/run-zap.ps1` with `-ReportName zap-baseline-report` but the script's default is the same name. The new user should still be able to copy-paste the command; verify on a clean clone.
- `scripts/run-zap.ps1` checks the auth API at `http://127.0.0.1:4000/api/health`. Confirm that endpoint still returns 200 with the new manager seeder running (the auth API has not changed shape, so it should).
- The `lighthouse` and `@lhci/cli` lines in `requirements.txt` are documentation. Verify the README "Quick Start" does not tell new users to `pip install` Lighthouse and then run `python -m lighthouse` - the README's Lighthouse section uses the right `npx` invocation, but a future edit could regress.

## Code Quality Summary

Good

## Verdict

Approve with Suggestions

VERDICT: Approve with Suggestions
