
## Tools Used

This project uses a layered security and quality toolchain covering static analysis, dynamic scanning, AI-assisted review, performance auditing, and automated testing.

---

### 1. DevSecOps Pipeline (`.github/workflows/devsecops.yml`)

The DevSecOps workflow is the backbone of the CI/CD security posture. It chains eleven jobs in order, each consuming the output of the previous, ensuring that a failing security gate stops the pipeline before the next stage runs.

| Tool | Role |
|---|---|
| **Ruff** | Python linter and formatter — catches style and logic errors before any test runs |
| **Pytest + pytest-cov** | Runs the full unit and integration test suite and generates JUnit XML and HTML coverage reports |
| **Semgrep** | Static Application Security Testing (SAST) — pattern-based source code scanner that detects injection flaws, insecure API usage, and logic bugs using community and custom rule sets |
| **Bandit** | Python-specific SAST — flags dangerous function calls (`eval`, `exec`, `shell=True`), hardcoded passwords, weak cryptography, and insecure temporary file usage across the Python codebase |
| **Gitleaks** | Secret scanning — crawls the entire git history and working tree for API keys, tokens, connection strings, and credentials before they reach the remote |
| **pip-audit** | Software Composition Analysis (SCA) — audits every Python dependency in `requirements.txt` against the OSV and PyPI advisory databases and reports CVEs with severity ratings |
| **Trivy** | Container and filesystem vulnerability scanner — scans the project filesystem for OS package CVEs and misconfigurations and uploads results as SARIF to GitHub Security |
| **Lighthouse CI** | Frontend performance and accessibility auditing — runs Google Lighthouse headlessly against the built Vite app and enforces score thresholds for Performance, Accessibility, Best Practices, and SEO |
| **OWASP ZAP** | Dynamic Application Security Testing (DAST) — runs a baseline spider scan against the running app server and reports OWASP Top 10 findings without active exploitation |
| **API Security Tests** | Project-specific Pytest suite (`tests/unit/test_api.py`) — verifies authentication enforcement, input validation, error codes, and rate-limit headers on the FastAPI endpoints |
| **AI Security Tests** | Project-specific Pytest suite (`tests/unit/test_ollama.py`) — validates that LLM prompt injection guards, output sanitization, and model-boundary controls work correctly |

---

### 2. Security Review (`tests/`, `.ai/skills/security.skill.md`, `.ai/checklists/security.md`)

The project follows a structured, standard-based security review process backed by three recognized frameworks:

**OWASP Application Security Verification Standard (ASVS)**
The ASVS is the primary checklist for verifying that the application meets a defined security baseline. It covers authentication and session management, access control, input validation, cryptography, error handling, logging, data protection, communication security, and API security. Every sprint review scores each applicable ASVS control as `pass`, `risk`, or `n/a`.

**Cryptography Controls**
All cryptographic decisions are reviewed against modern standards. The checklist enforces: no custom or home-grown token formats; use of authenticated encryption (AES-GCM) where data confidentiality is required; no deprecated algorithms (MD5, SHA-1, DES, RC4); minimum RSA 2048 / ECDSA P-256 for asymmetric keys; and PBKDF2 / bcrypt / argon2 for password hashing. JWT signing uses RS256; symmetric secrets use environment-variable injection, not hardcoded literals.

**OWASP Top 10**
The OWASP Top 10 provides the threat model framing for the review. Each category is explicitly addressed:
- **A01 Broken Access Control** — every FastAPI route enforces JWT validation; manager-only routes check the `role` claim.
- **A02 Cryptographic Failures** — covered by the cryptography checklist above and Bandit's crypto checks.
- **A03 Injection** — Semgrep SAST + parameterized queries; LLM outputs are never executed.
- **A04 Insecure Design** — local-first privacy model; resumes stay on-machine unless a cloud provider is explicitly configured.
- **A05 Security Misconfiguration** — ZAP baseline checks security headers; Trivy scans for misconfigured OS packages.
- **A06 Vulnerable Components** — pip-audit and Trivy SCA flag known CVEs in dependencies.
- **A07 Authentication Failures** — JWT expiry, refresh rotation, and bcrypt password hashing are enforced.
- **A08 Software Integrity Failures** — Gitleaks secret scan and Dependabot keep the supply chain clean.
- **A09 Logging Failures** — PII is redacted at the logger boundary; security events are emitted to structured logs.
- **A10 SSRF** — outbound HTTP calls are allowlisted; user-supplied URLs are not followed.

**LLM-Specific Security**
Because the system uses local and hosted LLMs, a dedicated checklist section covers prompt injection (untrusted resume text is marked as data, not instructions), model output sandboxing (LLM responses are parsed as structured JSON and validated before use), and tool-scope constraints (the LLM cannot invoke system commands or write to disk directly).

---

### 3. Git Hooks (`.githooks/`)

Two local hooks enforce quality gates before code leaves the developer's machine:

**`pre-commit`** — runs on every `git commit` and is designed to be fast (no LLM calls):
- Blocks direct commits to `main` (all work must go through a feature branch and pull request).
- Runs `npm run lint` and `npm run format:check` for both `backend/` and `frontend/` if those scripts are defined.
- Byte-compiles every staged `.py` file with `python -m py_compile` to catch syntax errors before CI does.
- The hook is a no-op for any step where the required tool is not installed, so it does not break fresh checkouts.

**`pre-push`** — runs on every `git push` and enforces the AI code-review policy:
- Computes a SHA-256 hash of the list of files changed since the last push to the upstream branch.
- Compares the hash against `.code-review/last-report.hash`. If the hash has changed, the previous report is archived (not deleted) and the push is blocked until a fresh review is produced.
- The developer pastes the auto-generated invocation prompt (`.code-review/invoke.txt`) into an AI chat, receives the review report, and saves it to `.code-review/last-report.md`.
- The hook reads the final `VERDICT:` line of the report: `Approve` allows the push silently, `Approve with Suggestions` allows it with a warning, and `Request Changes` blocks the push until High-severity findings are resolved.
- Emergency override: `AI_SKIP_PRE_PUSH=1 git push`.

---

### 4. Pytest

Pytest is the primary Python test runner for all unit, integration, and performance test suites under `tests/`.

| Suite | Location | What It Covers |
|---|---|---|
| API unit tests | `tests/unit/test_api.py` | FastAPI endpoint contracts, auth enforcement, error responses |
| Scoring tests | `tests/unit/test_scoring.py` | Match score calculation, fit bucket assignment |
| Validation tests | `tests/unit/test_validation.py` | JD and resume input validation, schema enforcement |
| JSON tests | `tests/unit/test_json.py` | LLM output parsing, malformed JSON fallback paths |
| Extraction tests | `tests/unit/test_extraction.py` | PDF and DOCX text extraction edge cases |
| Ollama / AI tests | `tests/unit/test_ollama.py` | LLM integration, mock provider, prompt injection guards |
| Report summary tests | `tests/unit/test_report_summary.py` | Report aggregation and summary API responses |
| Integration tests | `tests/integration/` | End-to-end flows across the FastAPI and auth services |
| Performance tests | `tests/performance/` | Response time benchmarks and k6 load test result validators |

Tests are run with coverage reporting:
```bash
pytest --junitxml=junit.xml --cov=. --cov-report=xml --cov-report=html
```
Coverage reports are uploaded as CI artifacts on every pipeline run.

---

### 5. Playwright

Playwright drives the end-to-end and scenario-matrix test suite for the React frontend.

- **Scenario Matrix** — `frontend-test/` is a dedicated React testing dashboard (port 5174) that streams live logs while Playwright exercises the full recruiter workflow: login → upload resumes → paste JD → run analysis → inspect results → verify ranking.
- **Screenshot capture** — every scenario step captures a screenshot, stored under `reports/` for visual regression review.
- **Cross-browser** — tests run against Chromium by default in CI; Firefox and WebKit are added for release gates.
- **Accessibility** — `axe-core` is integrated into the Playwright runner to assert WCAG 2.1 AA compliance on every page visited.
- **Manager-only routes** — the suite includes flows for the manager role: viewing all candidates, accessing the testing dashboard, and verifying that recruiter-only users are blocked from manager endpoints.

---

### 6. Lighthouse CI

Lighthouse CI (`@lhci/cli`) runs Google Lighthouse headlessly against the production-built Vite app as part of the DevSecOps pipeline.

**What it audits:**
- **Performance** — First Contentful Paint, Largest Contentful Paint, Total Blocking Time, Cumulative Layout Shift, and Speed Index.
- **Accessibility** — color contrast ratios, ARIA roles, keyboard navigation, focus management, and semantic HTML structure.
- **Best Practices** — HTTPS enforcement, deprecated API usage, browser error logging, and correct use of `rel=noopener` on external links.
- **SEO** — meta descriptions, crawlable links, `robots.txt`, and structured data.

**How it runs in CI:**
```bash
npm run build
npx vite preview --port 5173 &
sleep 3
lhci autorun
```

The `lighthouserc.json` at the project root defines the URL targets, score thresholds (e.g., Accessibility ≥ 90), and the upload destination. Reports are saved to `.lighthouseci/` and uploaded as a CI artifact named `lighthouse-report`.

---

## GitHub Actions – DevSecOps Pipeline

The pipeline defined in `.github/workflows/devsecops.yml` runs on every push to `main` or `develop`, every pull request, and on manual dispatch. Jobs run sequentially (each `needs` the previous) so a failing gate stops the chain early and saves runner minutes.

```
push / pull_request / workflow_dispatch
          │
          ▼
┌─────────────────────┐
│  1. lint            │  Ruff (Python) + npm build check (Node)
└──────────┬──────────┘
           │ needs: lint
           ▼
┌─────────────────────┐
│  2. unit-tests      │  pytest + coverage → junit.xml, coverage.xml, htmlcov/
└──────────┬──────────┘
           │ needs: unit-tests
           ▼
┌─────────────────────┐
│  3. semgrep         │  SAST pattern scan via semgrep/semgrep-action@v1
└──────────┬──────────┘
           │ needs: semgrep
           ▼
┌─────────────────────┐
│  4. bandit          │  Python SAST → bandit-report.html artifact
└──────────┬──────────┘
           │ needs: bandit
           ▼
┌─────────────────────┐
│  5. gitleaks        │  Secret scan across full git tree (v8.18.4)
└──────────┬──────────┘
           │ needs: gitleaks
           ▼
┌─────────────────────┐
│  6. pip-audit       │  SCA on requirements.txt → pip-audit.json artifact
└──────────┬──────────┘
           │ needs: pip-audit
           ▼
┌─────────────────────┐
│  7. trivy           │  Filesystem CVE scan → trivy.sarif → GitHub Security tab
└──────────┬──────────┘
           │ needs: trivy
           ▼
┌─────────────────────┐
│  8. build           │  npm install + npm run build (production bundle)
└──────────┬──────────┘
           │ needs: build
           ▼
┌─────────────────────┐
│  9. lighthouse      │  Vite preview server → lhci autorun → .lighthouseci/ artifact
└──────────┬──────────┘
           │ needs: lighthouse
           ▼
┌─────────────────────┐
│ 10. zap             │  OWASP ZAP baseline spider scan → zap-scan artifact
└──────────┬──────────┘
           │ needs: zap
           ▼
┌─────────────────────┐
│ 11. api-security    │  pytest tests/unit/test_api.py (FastAPI auth + input checks)
└──────────┬──────────┘
           │ needs: api-security
           ▼
┌─────────────────────┐
│ 12. ai-security     │  pytest tests/unit/test_ollama.py (LLM injection + output guards)
└──────────┬──────────┘
           │ needs: ai-security
           ▼
┌─────────────────────┐
│ 13. upload-reports  │  Bundles all artifacts into one devsecops-reports archive
└─────────────────────┘
```

**Concurrency control** — a `concurrency` group keyed to `github.ref` with `cancel-in-progress: true` ensures that a new push to the same branch cancels any still-running pipeline for that branch, preventing queued runs from stacking up.

**Permissions** — the workflow requests only `contents: read`, `security-events: write` (for SARIF upload), and `actions: read`. No write access to the repository itself.

**Artifacts produced per run:**

| Artifact Name | Contents |
|---|---|
| `junit-report` | Pytest JUnit XML (`junit.xml`) |
| `coverage-report` | `coverage.xml` + `htmlcov/` HTML coverage report |
| `bandit-report` | `bandit-report.html` — all Python SAST findings |
| `pip-audit` | `pip-audit.json` — CVEs in Python dependencies |
| `lighthouse-report` | `.lighthouseci/` — Lighthouse scores and traces |
| `zap-scan` | ZAP baseline scan HTML report |
| `devsecops-reports` | Combined archive of all the above + `reports/` + `.code-review/` |

---
