// Auto-discovered report catalog. Each entry renders one card in the
// Reports Generated section. Add "command" + "cwd" to make the card
// show a Run button that streams live output into the card.
//
// Fields:
//   id          - stable key (used for localStorage state)
//   title       - card title
//   kind        - "html" | "json" | "junit" | "perf" | "security" | "lighthouse" | "ci"
//   filename    - suggested download name
//   path        - workspace-relative path for discovery / opening
//   command     - (optional) shell command to regenerate this report
//   cwd         - (optional) working directory for the command
//   description - short description shown on the card

import { SAMPLE_FIXTURES } from "./fixtures";

export { SAMPLE_FIXTURES };

const ROOT = "D:/trigyn/trigyn project/AI-recruiter-screening-system-";

export const REPORT_CATALOG = [
  {
    id: "html",
    title: "HTML Report",
    kind: "html",
    filename: "report.html",
    path: "reports/report.html",
    command: "pwsh tests/run.ps1",
    cwd: ROOT,
    description: "Full integration scenario matrix — boots Ollama, FastAPI, runs all scenarios",
  },
  {
    id: "security",
    title: "Security Review (ZAP)",
    kind: "security",
    filename: "zap-baseline-report.html",
    path: "zap-reports/zap-baseline-report.html",
    command:
      'docker run --rm -v "D:/trigyn/trigyn project/AI-recruiter-screening-system-/zap-reports:/zap/wrk" ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t http://host.docker.internal:8000 -r zap-baseline-report.html',
    cwd: ROOT,
    description: "OWASP ZAP baseline security scan against the running FastAPI backend",
  },
  {
    id: "performance",
    title: "Lighthouse Performance",
    kind: "perf",
    filename: "lighthouse-report.html",
    path: "reports/lighthouse-report.html",
    command:
      'npx --yes lighthouse http://localhost:5173 --output html --output-path "reports/lighthouse-report.html" --chrome-flags="--headless --no-sandbox"',
    cwd: ROOT,
    description:
      "Lighthouse audit: performance, accessibility, best practices, SEO. Frontend must be running on port 5173.",
  },
  {
    id: "code-review",
    title: "Code Review",
    kind: "code",
    filename: "checklist-report.html",
    path: ".code-review/checklist-report.html",
    command: "npm run lint",
    cwd: ROOT,
    description: "Static code analysis and review",
  },
];
   