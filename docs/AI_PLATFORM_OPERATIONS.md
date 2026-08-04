# AI Platform Operations Guide

## Daily Developer Flow

1. Route the task before changing code:

   ```powershell
   venv\Scripts\python.exe scripts\ai_platform.py route "Describe the task"
   ```

2. Read the selected `.ai/workflows/`, `.ai/skills/`, and `.ai/checklists/` files.
3. Implement the change and update tests.
4. Run the local gates:

   ```powershell
   venv\Scripts\python.exe -m pytest tests\unit -q
   venv\Scripts\python.exe -m bandit -r backend api.py -s B101 --severity-level high --confidence-level high
   npm --prefix frontend run build
   npm --prefix frontend-test run build
   venv\Scripts\python.exe scripts\ai_platform.py report
   ```

5. Commit and push. `.githooks/pre-commit` runs fast local checks; `.githooks/pre-push`
   requires a fresh AI review report for the pushed diff.

## Manager Dashboard Flow

1. Start the dashboard:

   ```powershell
   npm --prefix frontend-test run dev -- --host 127.0.0.1
   ```

2. Open `http://127.0.0.1:5174`.
3. Open the Executive Engineering Report, Quality and Security Reports, Technical Debt
   Report, Scenario Matrix Report, and Lighthouse Report cards.
4. Use this decision rule:
   - Green tests/builds and no blocking security finding: approve for PR review.
   - Failed quality/security gate: return to the developer with the linked report.
   - Production release: require the Release Readiness Report and recorded approval.

## CI and Pull Request Flow

GitHub Actions runs unit tests, frontend builds, report generation, Bandit, Safety, OWASP
dependency checks, CodeQL, Lighthouse, and performance workflows according to their workflow
triggers. The `engineering-reports` workflow artifact holds generated `reports/ai-*` files.

Enable repository branch protection for `main` and require successful CI checks before merge.

## External Integration Boundary

GitHub, Jira, Confluence, Slack, or other MCP integrations require an authenticated account,
approved scopes, and an installed connector. Do not put credentials in this repository. Once
an organization approves a connector, configure it in the hosting platform and use
`.ai/automation/mcp-integration.md` as the policy contract.
