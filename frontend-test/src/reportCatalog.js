// Auto-discovered report catalog. Each entry renders one card in the
// Reports Generated section. Add "command" + "cwd" to make the card
// show a Run button that streams live output into the card.
//
// Fields:
//   id          - stable key (used for localStorage state)
//   title       - card title
//   kind        - "html" | "json" | "junit" | "perf" | "security" | "lighthouse" | "ci" | "code"
//   filename    - suggested download name
//   path        - workspace-relative path for discovery / opening
//   command     - (optional) shell command to regenerate this report
//   cwd         - (optional) working directory for the command. If omitted,
//                 the entry falls back to the dynamically detected repo root
//                 derived from this file's location.
//   description - short description shown on the card
//
// NOTE: do not put secrets in `command`; if a command needs a token, name
// the env var in `description` and reference `$VAR` in the command.

import { SAMPLE_FIXTURES } from "./fixtures";

export { SAMPLE_FIXTURES };

// Derive the project root from this file's location so the catalog works
// on every developer's machine, not just the original author. The file
// lives at <repo>/frontend-test/src/reportCatalog.js, so going up two
// levels lands at the repo root regardless of the absolute path.
const __filename =
  typeof window !== "undefined" && typeof document !== "undefined"
    ? null
    : null;
const fromUrl =
  typeof import.meta !== "undefined" && import.meta.url
    ? new URL("../..", import.meta.url).pathname
    : null;

function detectRepoRoot() {
  if (fromUrl) {
    // import.meta.url is file:///D:/... on Windows. Strip the file://
    // scheme and the leading slash so path.resolve-friendly formats.
    let p = decodeURIComponent(fromUrl);
    if (p.startsWith("/") && /^\/[A-Za-z]:/.test(p.slice(1))) {
      p = p.slice(1);
    }
    return p;
  }
  // Browser fallback: ask the parent app for the root via a global set
  // by vite.config.js, or fall back to "." which keeps the test
  // dashboard's "Run" button working relative to the app's own root.
  if (typeof window !== "undefined" && window.__PROJECT_ROOT__) {
    return window.__PROJECT_ROOT__;
  }
  return ".";
}

const ROOT = detectRepoRoot();

export const REPORT_CATALOG = [
 
  {
    id: "html",
    title: "Scenario Matrix (HTML Report)",
    kind: "html",
    filename: "report.html",
    path: "reports/report.html",
    command: "pwsh tests/run.ps1",
    cwd: ROOT,
    description:
      "Full integration scenario matrix - boots Ollama, FastAPI analyzer, Node auth API, recruiter UI, runs every scenario in tests/data/scenarios.yaml and writes the HTML report.",
  },
  {
    id: "zap-frontend",
    title: "OWASP ZAP Baseline - Recruiter UI",
    kind: "security",
    filename: "zap-baseline-report.html",
    path: "reports/zap/zap-baseline-report.html",
    command: "pwsh scripts/run-zap.ps1 -Target http://host.docker.internal:5173 -ReportName zap-baseline-report",
    cwd: ROOT,
    description:
      "OWASP ZAP baseline scan against the React recruiter UI on :5173. Requires Docker Desktop and the local stack to be up (start-app.ps1).",
  },
  {
    id: "lighthouse",
    title: "Lighthouse Performance (local)",
    kind: "perf",
    filename: "lighthouse-report.html",
    path: "reports/lighthouse-report.html",
    command:
      "npx --yes lighthouse http://localhost:5173 --output html --output-path \"reports/lighthouse-report.html\" --chrome-flags=\"--headless --no-sandbox\"",
    cwd: ROOT,
    description:
      "Local Lighthouse audit: performance, accessibility, best practices, SEO. Recruiter UI must be running on :5173 first (start-app.ps1).",
  },
 
  {
    id: "code-review",
    title: "Code Review Checklist (AI-driven)",
    kind: "code",
    filename: "checklist-report.html",
    path: ".code-review/checklist-report.html",
    command: "run code-review",
    cwd: ROOT,
    description:
      "Send .code-review/invoke.txt to Gemini using the Code Review Policy skill. The AI reviews the changed files and writes the checklist-report.html output.",
  },
  {
    id: "security-review",
    title: "AI Security Review (LLM-driven)",
    kind: "security",
    filename: "security-review-*.html",
    path: "skills/reports/",
    command: "run security-review",
    cwd: ROOT,
    description:
      "Send api.py to Gemini using the Security Review skill. The AI produces a structured HTML report under skills/reports/.",
  },
  {
    id: "fetch-ci",
    title: "Fetch Latest CI Pipeline Run",
    kind: "ci",
    filename: "ci-logs.txt",
    path: "reports/ci-logs.txt",
    command: "python scripts/fetch_ci.py",
    cwd: ROOT,
    description:
      "Downloads the latest ci.yml logs and build artifacts from GitHub. Requires GITHUB_TOKEN in .env for artifact downloads.",
  },
  {
    // Coverage report has relative CSS/JS/PNG assets — served via /reports-static/ so all assets load correctly.
    id: "ci-python-coverage",
    title: "CI: Python Coverage Report",
    kind: "code",
    filename: "index.html",
    path: "reports/ci/backend-python-reports/htmlcov-python/index.html",
    staticUrl: "/reports-static/reports/ci/backend-python-reports/htmlcov-python/index.html",
    cwd: ROOT,
    description:
      "Python test coverage report (48%) from the latest CI run. Run \"Fetch Latest CI Pipeline Run\" first to download it.",
  },
  {
    id: "ci-junit-xml",
    title: "CI: Python Test Results (JUnit XML)",
    kind: "junit",
    filename: "junit-python.xml",
    path: "reports/ci/backend-python-reports/junit-python.xml",
    cwd: ROOT,
    description:
      "JUnit XML test results from the latest CI run. Run \"Fetch Latest CI Pipeline Run\" first to download it.",
  },
  {
    id: "ci-depcheck",
    title: "CI: OWASP Dependency-Check",
    kind: "security",
    filename: "dependency-check-report.html",
    path: "reports/ci/dependency-check-report/dependency-check-report.html",
    cwd: ROOT,
    description:
      "Dependency-Check HTML report from the CI run. Only available if the OWASP dependency-check job completed in the latest ci.yml run.",
  },
  {
    // Fetched by scripts/fetch_ci.py. The polished HTML page opens in a single click via /reports-static/.
    id: "ci-summary",
    title: "CI: Pipeline Run Summary",
    kind: "ci",
    filename: "ci-summary.html",
    path: "reports/ci/ci-summary.html",
    staticUrl: "/reports-static/reports/ci/ci-summary.html",
    cwd: ROOT,
    description:
      "Polished overview of the latest ci.yml run: verdict, branch, commit, every artifact with file counts and sizes, and the aggregated log path. Run \"Fetch Latest CI Pipeline Run\" first to generate it.",
  },
];
