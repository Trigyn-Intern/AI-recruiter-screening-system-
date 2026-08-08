# AI Recruiter Screening System

AI-powered resume screening that ranks candidates against a Job Description in minutes, not days.

A recruiter-friendly web app that reads multiple resumes, understands a JD, scores each candidate, surfaces the skill gaps, and tells you who to interview first.

License: MIT  Python  FastAPI  React  Vite  Sentence Transformers  FAISS  Ollama  Llama 3.2  Google Gemini  Playwright

Built by Team Trigyn  ·  Internal prototype  ·  FastAPI + React + local LLMs

---

## Table of Contents

- Overview
- The Problem
- Key Features
- Tools Used
- GitHub Actions – DevSecOps Pipeline
- Live Demo
- Architecture
- How It Works
- Data and Schema
- Tech Stack
- Getting Started
- Quick Start (Windows)
- Quick Start (macOS / Linux)
- Testing
- Project Structure
- Configuration
- Deployment
- Limitations and Roadmap
- Authors
- License
- Acknowledgements

---

## Overview

Hiring teams still spend hours on the first pass: opening 40 PDFs, skimming each one, comparing them line by line to a Job Description, and trying to be consistent across reviewers. It is slow, subjective, and the part that decides who gets an interview rarely changes.

The AI Recruiter Screening System removes that first pass. Drop in a JD, upload a folder of resumes, and the app returns a ranked shortlist with match scores, skill gaps, and a per-candidate explainer that you can act on. The interface is a modern React app with secure recruiter login; the heavy lifting runs in FastAPI on top of Sentence Transformers, FAISS, and a local LLM (Ollama Llama 3.2 by default, or Google Gemini when you want a hosted model).

The system is built to be **local-first**: your resumes never leave your machine unless you choose a cloud model, and every prompt template is editable from the UI.

---

## The Problem

- Recruiters lose 1 to 3 hours per role on the first resume screen.
- Reviewer bias and fatigue make shortlists inconsistent.
- Resumes mix formats (PDF, DOCX), styles, and lengths, so a fair comparison is hard by hand.
- Generic ATS filters reject strong candidates on missing exact keywords.
- Hiring managers want a shortlist with reasons, not a black-box score.

This project is a focused answer to all five.

---

## Key Features

- Secure recruiter login and signup, with a JWT-backed auth API and a glassmorphism React sign-in screen.
- Bulk resume upload (PDF and DOCX) with per-file validation and error reporting.
- AI Job Description analysis that extracts experience, primary skills, secondary skills, and education as structured JSON.
- Resume-to-JD semantic matching using Sentence Transformers and a persistent FAISS vector store.
- Skill gap analysis that lists matching and missing skills for every candidate.
- Candidate ranking with explicit fit buckets:
  - **Good Fit**
  - **Moderate Fit**
  - **Bad Fit**
- Per-candidate explainer with justification, evidence, and grading rationale.
- Editable prompt templates for the JD analyzer, skill gap analyzer, candidate explainer, and resume skill extractor, all live from the UI.
- Pluggable AI provider: local Ollama (Llama 3.2) or Google Gemini, configurable from the dashboard.
- A separate React testing dashboard (port 5174) that lets QA run scenarios, watch live logs, and inspect generated reports.
- A scenario-matrix Playwright suite that runs the full flow against a real model and captures screenshots.
- Lighthouse + axe-core accessibility scoring wired into CI.
- A one-click `start-app.ps1` launcher that brings up the full stack (Ollama, FastAPI, auth API, recruiter app, testing dashboard) in separate windows.

---

## Tools Used

This project uses a layered security and quality toolchain covering static analysis, dynamic scanning, AI-assisted review, performance auditing, and automated testing.

---

### How the Toolchain Helps This Project

Each layer in the toolchain solves a specific problem that arises when building an AI-powered application that handles candidate data:

| Challenge | Tool(s) That Address It |
|---|---|
| Resume text and JD could contain prompt injection | Semgrep SAST + `test_ollama.py` AI security suite |
| Uploaded files could be malformed or malicious | `test_extraction.py`, file-type and size validation in FastAPI |
| Auth tokens could be stolen or replayed | Bandit crypto checks, `test_api.py` auth suite, bcrypt + JWT |
| Python dependencies could carry CVEs | pip-audit + Trivy SCA in every CI run |
| Secrets (API keys, manager passwords) could leak into git | Gitleaks pre-CI scan across full git history |
| UI could regress on accessibility or performance | Lighthouse CI + axe-playwright on every push |
| LLM output could be unparseable or unsafe | `jsonschema` validation + deterministic fallback grader |
| Code quality could drift without a reviewer | Pre-push AI review hook (`.githooks/pre-push`) |

---

### 1. DevSecOps Pipeline (`.github/workflows/devsecops.yml`)

**How it helps:** The DevSecOps workflow is the backbone of the CI/CD security posture. It chains eleven jobs in order, each consuming the output of the previous, ensuring that a failing security gate stops the pipeline before the next stage runs. In a recruiting tool that processes real candidate data, a single leaked credential or insecure endpoint can expose PII; this pipeline makes that class of failure visible before any code reaches production.

**How to use it in your own project:**

1. Copy `.github/workflows/devsecops.yml` into your repo's `.github/workflows/` directory.
2. The workflow is parameterised with `env:` variables at the top. Update `PYTHON_VERSION`, `NODE_VERSION`, and the Semgrep rule set to match your stack.
3. Add the following GitHub Actions secrets to your repository (`Settings → Secrets and variables → Actions`):
   - `SEMGREP_APP_TOKEN` — from [semgrep.dev](https://semgrep.dev) (free tier available).
   - `GITLEAKS_LICENSE` — only required for the Enterprise edition; the community version needs no token.
4. The pipeline will run automatically on every push to `main` or `develop`, every pull request, and on manual dispatch (`workflow_dispatch`).
5. View results under **Actions → devsecops → latest run**. Security findings also appear under **Security → Code scanning** (SARIF results from Trivy and Semgrep).

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

**How it helps:** A toolchain alone is not sufficient when an application calls an LLM with user-supplied content. The structured review process forces a human to walk through OWASP ASVS, the OWASP Top 10, and an LLM-specific checklist on every sprint. This ensures that prompt injection guards and output validation rules are deliberately designed, not accidentally correct.

**How to use it in your own project:**

1. Copy `.ai/checklists/security.md` and `.ai/skills/security.skill.md` into your own `.ai/` directory.
2. Before any release, open `security.md` and score each ASVS control as `pass`, `risk`, or `n/a` for your application.
3. The LLM-specific section of the checklist is relevant to any project that calls an external model. Keep it even if you swap the provider.

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

**How it helps:** CI pipelines catch problems after a push; git hooks catch them before. The pre-commit hook stops obvious mistakes (direct commits to `main`, syntax errors, lint failures) in under two seconds. The pre-push hook enforces a mandatory AI code review for every meaningful change — ensuring that at least one structured review happens before code reaches teammates, without requiring a separate review ticketing system.

**How to deploy the hooks:**

```bash
# Point git to the project's hook directory (one-time setup per clone)
git config core.hooksPath .githooks

# Make the hooks executable (macOS / Linux)
chmod +x .githooks/pre-commit .githooks/pre-push
```

On Windows the `chmod` step is not needed; PowerShell respects the hooks automatically once the path is set.

**How to use them in your own project:**

1. Copy `.githooks/` into your repo root.
2. Edit the `PROTECTED_BRANCH` variable in `pre-commit` to match your main branch name.
3. Run `git config core.hooksPath .githooks` in every clone, or add it to your `npm postinstall` / `Makefile` setup target so contributors get it automatically.
4. The pre-push hook is self-contained: it reads `.code-review/last-report.md` for a `VERDICT:` line. Any AI tool that writes a Markdown review with that line at the end works — it is not tied to a specific model.

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

**How it helps:** Because the analyzer relies on a local LLM, deterministic unit tests are the only reliable way to verify the surrounding logic independently of model availability. Mocking the LLM provider lets the suite run in CI without Ollama or a Gemini key, yet still covers scoring logic, JSON validation, and auth enforcement. The coverage report pinpoints which branches of `backend.py` are exercised, making it easy to spot untested fallback paths.

**How to deploy and run:**

```bash
# Install test dependencies (already in requirements.txt)
pip install pytest pytest-cov pytest-asyncio

# Run the full suite with coverage
pytest --junitxml=junit.xml --cov=. --cov-report=xml --cov-report=html

# Run only the fast unit tests (no Playwright, no integration)
pytest tests/unit/

# Run a single file
pytest tests/unit/test_scoring.py -v

# Run with a filter on a specific scenario
pwsh tests/run.ps1 -Filter python_ml_llama32
```

**How to use in your own project:**

- `tests/unit/test_scoring.py` — the match score and fit bucket logic is fully decoupled from the LLM. Copy the scoring functions from `backend.py` and the corresponding test file to add semantic-similarity ranking to any Python service.
- `tests/unit/test_ollama.py` — the mock LLM provider pattern used here (replacing the real HTTP call with a fixture that returns canned JSON) can be adapted for any project that calls an external AI API.
- `tests/unit/test_api.py` — the FastAPI auth enforcement tests (checking for 401 on missing token, 403 on wrong role) are generic enough to serve as a baseline for any FastAPI project with JWT auth.

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

Coverage reports are uploaded as CI artifacts on every pipeline run.

---

### 5. Playwright

**How it helps:** The scenario matrix in `tests/data/scenarios.yaml` lets QA add a new test case in one YAML row — no code change needed. Playwright then drives the real browser through the full recruiter workflow, including login, file upload, JD paste, and ranking inspection. axe-core assertions piggyback on every page navigation, making accessibility a zero-cost side effect of the E2E suite rather than a separate audit.

**How to deploy and run:**

```bash
# Install Playwright browsers (one-time)
npx playwright install --with-deps chromium

# Run the full scenario matrix via the PowerShell runner (Windows)
pwsh tests/run.ps1

# Run a specific scenario
pwsh tests/run.ps1 -Filter python_ml_llama32

# Run Playwright tests directly (stack must already be running)
npx playwright test

# View the HTML report after a run
npx playwright show-report
```

**How to use in your own project:**

- `tests/data/scenarios.yaml` — the scenario-matrix pattern (one YAML row = one E2E test case with inputs and expected outputs) is portable to any project. The runner reads the file and parametrizes pytest automatically.
- `tests/ui/run_scenario_matrix.py` — the service-boot logic (start servers, wait for health check, run tests, tear down) can be adapted as a standalone test-runner harness for any microservice stack.
- `tests/render_report.py` — the JUnit-to-HTML report renderer is not tied to this project. Give it any `junit.xml` and a YAML scenario file and it produces a single-page pass/fail table.

Playwright drives the end-to-end and scenario-matrix test suite for the React frontend:

- **Scenario Matrix** — `frontend-test/` is a dedicated React testing dashboard (port 5174) that streams live logs while Playwright exercises the full recruiter workflow: login → upload resumes → paste JD → run analysis → inspect results → verify ranking.
- **Screenshot capture** — every scenario step captures a screenshot, stored under `reports/` for visual regression review.
- **Cross-browser** — tests run against Chromium by default in CI; Firefox and WebKit are added for release gates.
- **Accessibility** — `axe-core` is integrated into the Playwright runner to assert WCAG 2.1 AA compliance on every page visited.
- **Manager-only routes** — the suite includes flows for the manager role: viewing all candidates, accessing the testing dashboard, and verifying that recruiter-only users are blocked from manager endpoints.

---

### 6. Lighthouse CI

**How it helps:** Lighthouse CI (`@lhci/cli`) enforces a performance and accessibility budget on every push. Without this gate, React bundle size creep and unoptimized images silently degrade the recruiter's experience over time. The axe-core accessibility assertions ensure that the app remains usable by keyboard and screen-reader users as the UI evolves.

**How to deploy and run:**

```bash
# Install Lighthouse CI globally (or use npx)
npm install -g @lhci/cli

# Run Lighthouse locally against the running recruiter UI
npm run build                        # build the Vite production bundle
npx vite preview --port 5173 &      # serve it
lhci autorun                        # run against URLs in lighthouserc.json

# Or point at the dev server directly
lighthouse http://localhost:5173 \
  --output=html \
  --output-path=reports/lighthouse-report.html \
  --chrome-flags="--headless"
```

**How to use in your own project:**

1. Copy `lighthouserc.json` from the project root. Update the `url` list to match your app's routes and raise or lower the `minScore` thresholds to match your standards.
2. Add the `lighthouse` job from `.github/workflows/devsecops.yml` to your own workflow — it is self-contained and only requires a built static bundle to be served on a known port.
3. The accessibility threshold (`minScore: 0.9` for accessibility) is a good starting baseline for any customer-facing application.

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

### 7. Reusable Components and Modules

Several parts of this codebase are generic enough to be lifted directly into other projects.

#### Frontend (React)

| Component / File | Location | What It Does | How to Reuse |
|---|---|---|---|
| **Glassmorphism Auth Screen** | `frontend/src/pages/auth/Login.jsx`, `auth.css` | A polished JWT login + signup flow with glass-effect cards, animated gradients, and inline form validation | Copy `auth/` and `auth.css` into any React + Vite project; replace the `VITE_API_URL` endpoint |
| **`RequireAuth` Route Guard** | `frontend/src/pages/RequireAuth.jsx` | A React Router 6 wrapper that reads a JWT from `localStorage` and redirects unauthenticated users | Drop it into any React Router 6 app; update the `localStorage` key and the redirect path |
| **`api/client.js`** | `frontend/src/api/client.js` | A thin `fetch` wrapper that attaches the `Authorization` header, handles 401 → logout, and centralises the base URL | Copy and update `VITE_API_URL` + `VITE_FASTAPI_URL` to match your backend |
| **Skills Gap Panel** | `frontend/src/pages/dashboard/SkillsPage.jsx` | Renders matching and missing skills as visual pill groups with colour-coded fit buckets | Extract the component and pass it `matchingSkills` / `missingSkills` arrays from any skills API |
| **Reports Panel** | `frontend/src/pages/dashboard/ReportsPanel.jsx` | Displays paginated, filterable analysis session history with expandable candidate cards | Adapt by replacing the session-fetch call; the rendering logic is fully generic |
| **Design tokens** | `frontend/src/styles.css` | CSS custom properties for a cohesive dark-mode palette (HSL-based), Outfit font, glassmorphism utilities, and micro-animation helpers | Import the file as a global stylesheet; override `--color-*` variables to retheme |

#### Python Backend

| Module / Function | Location | What It Does | How to Reuse |
|---|---|---|---|
| **PDF + DOCX extractor** | `backend.py` → `extract_text_from_file()` | Extracts plain text from PDF (pypdf) and DOCX (python-docx) with a unified interface; returns `None` on unsupported types | Copy the function + its imports into any Python service that needs document ingestion |
| **FAISS vector store helpers** | `backend.py` → `save_vector_store()`, `load_vector_store()` | Persist and reload a FAISS index plus a parallel JSON metadata file to / from disk | Use as a drop-in local embedding cache in any Sentence Transformers project |
| **Deterministic fallback grader** | `backend.py` → `grade_candidate_local()` | Scores a candidate purely from skill overlap when the LLM is unavailable; requires no external API call | Pull into any ranking system that needs a rule-based fallback for when the AI provider is down |
| **LLM JSON output validator** | `backend.py` → `validate_llm_output()` | Wraps `jsonschema.validate` and logs schema violations; returns a safe default on failure | Use to harden any endpoint that parses LLM-generated JSON |
| **Pluggable provider router** | `backend.py` → `call_llm()` | Dispatches to Ollama or Gemini based on a runtime config flag; easy to extend with a third provider | Adopt the same `if provider == "ollama"` / `elif provider == "gemini"` pattern for any multi-provider LLM integration |
| **Prompt template manager** | `vector_store/prompt_config.json` + `backend.py` | Loads prompt templates from a JSON file at startup; falls back to `default_prompts.py` if the file is missing | Copy the load / fallback pattern to make any LLM prompt editable at runtime without a redeployment |

#### Auth API (Node.js)

| Module | Location | What It Does | How to Reuse |
|---|---|---|---|
| **JWT issue + verify middleware** | `backend/middleware/` | Issues `HS256` JWTs on login and validates them on protected routes with role checking | Copy `middleware/auth.js` into any Express app; update `JWT_SECRET` and `JWT_EXPIRES_IN` from `.env` |
| **Idempotent manager seeder** | `backend/seeders/seedManager.js` | Creates or rotates a seeded admin account on every server start using env variables; safe to run repeatedly | Use this pattern to guarantee a known admin account exists in any JSON-backed or MongoDB-backed Express auth service |
| **JSON user store** | `backend/data/users.json` + `backend/models/` | A zero-dependency file-based user store for prototypes; no database required | Swap the file read/write calls for a database client when you outgrow the JSON store — the controller and route layers are unchanged |

#### DevSecOps

| Asset | Location | What It Does | How to Reuse |
|---|---|---|---|
| **Full 13-job DevSecOps pipeline** | `.github/workflows/devsecops.yml` | Lint → Test → SAST → Secret scan → SCA → Container scan → Build → Lighthouse → ZAP → API security → AI security → Upload reports | Copy the file; update `PYTHON_VERSION`, `NODE_VERSION`, working-directory paths, and any tool-specific tokens |
| **Pre-push AI review hook** | `.githooks/pre-push` | Blocks pushes until a human completes an AI code review and the report records `VERDICT: Approve` | Copy `.githooks/` and run `git config core.hooksPath .githooks` in each clone |
| **Scenario-matrix runner** | `tests/run.ps1`, `tests/data/scenarios.yaml` | Data-driven E2E test runner: one YAML row = one full-stack scenario | Replace the YAML rows with your own scenario definitions; the runner script needs only the service URLs and the pytest path updated |

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

## Live Demo

| Channel                | Link                                                                              |
| ---------------------- | --------------------------------------------------------------------------------- |
| Recruiter web app      | http://localhost:5173 after running `./start-app.ps1`                             |
| Testing dashboard      | http://localhost:5174 (manager login only)                                        |
| Analyzer API           | http://127.0.0.1:8000                                                             |
| Auth API               | http://localhost:4000                                                             |
| Demo creds             | Shown on the login screen of the running app                                      |
| Manager creds          | Set via `SEED_MANAGER_EMAIL` / `SEED_MANAGER_PASSWORD` in `backend/.env`          |

The first request after a long idle may take a few seconds while the local model warms up.

---

## Architecture

A recruiter-facing React UI, a FastAPI analyzer, a Node auth API, a separate React testing dashboard, and a local LLM. Resumes and JD text are embedded once and cached in FAISS, so reruns are fast.

```
Recruiter Login (React :5173)
        |
        v
React Frontend (Vite + React Router)
        |
        +---> Auth API (Node + Express + JWT)  ---> users.json
        |
        v
FastAPI Analyzer (api.py :8000)
        |
        v
Resume Text Extraction (pypdf / python-docx)
        |
        v
Embedding Generation (Sentence Transformers, BAAI/bge-large-en-v1.5)
        |
        v
FAISS Vector Store (vector_store/resume_embeddings.faiss)
        |
        v
Semantic Similarity (cosine)  --->  Match Score
        |
        v
JD Analysis + Skill Gap + Candidate Explainer (Ollama Llama 3.2  or  Gemini)
        |
        v
Recruiter Dashboard (ranking, fit buckets, candidate details)

Testing Dashboard (React :5174, manager role only) ---> runs scenarios, streams logs
```

---

## How It Works

**Resume ingest.** Each uploaded file is read with `pypdf` or `python-docx`. The extracted text is hashed to a stable `resume_id`, embedded with the local Sentence Transformers model, and appended to a persistent FAISS index under `vector_store/`. Resumes are stored whole, not chunked, so a hit returns the complete record.

**JD analysis.** The pasted Job Description is run through a structured prompt that returns experience, primary skills, secondary skills, and education as validated JSON. The same JD embedding is then used to score every resume.

**Matching.** For each resume, cosine similarity against the JD embedding gives a 0 to 100 match score. The score feeds three outputs: a global ranking, a fit bucket (Good / Moderate / Bad), and a per-candidate detail bundle.

**Explainability.** The top N candidates are sent to the LLM with the JD, the resume text, and the structured skill profile. The model returns matching skills, missing skills, a written justification, and a grading verdict. When the LLM is unavailable, the system falls back to a deterministic local grader so the dashboard never goes blank.

**Auth and session.** The React app signs in against a separate Node + Express API that issues a JWT. The token is stored in `localStorage`, validated on every protected route, and cleared on a 401. The seeded manager account is auto-created on backend start (or rotated if `SEED_MANAGER_PASSWORD` is changed) and gates the testing dashboard at port 5174.

---

## Data and Schema

The vector store lives in `vector_store/` and contains three persistent files plus a per-session append log.

| File | Purpose |
| --- | --- |
| `resume_embeddings.faiss` | 1024-dim BGE-large index, one vector per resume. |
| `resume_metadata.json` | Resume name, id, raw text, and timestamps. |
| `resume_skills.json` | Cached structured skill profile per resume. |
| `prompt_config.json` | The current editable prompt templates. |
| `analysis_sessions.json` | Append-only log of past screening runs. |

A resume record is intentionally small: id, name, text, embedding, and skill profile. This keeps reruns fast, lets the UI show cached results for previously uploaded resumes, and makes the on-disk format easy to inspect.

---

## Tech Stack

### Frontend (recruiter)

- React 18
- Vite
- React Router 6
- lucide-react icons
- Plain CSS (Outfit font, glassmorphism auth screen)

### Testing dashboard

- React 18 + Vite (separate app on port 5174)
- Server-side middleware for live log streaming, command execution, and report serving

### Auth API

- Node.js 18+
- Express
- JSON Web Tokens (bcryptjs + jsonwebtoken)
- In-process JSON user store (no external database required)
- Idempotent manager seeder driven by `backend/.env`

### Analyzer Backend

- Python 3.10+
- FastAPI + Uvicorn (4 workers)
- Sentence Transformers (`BAAI/bge-large-en-v1.5`)
- FAISS (CPU)
- scikit-learn (cosine similarity)
- pypdf, python-docx
- pandas
- jsonschema (prompt output validation)

### AI Providers

- Ollama with Llama 3.2 (default, local)
- Google Gemini (`gemini-2.5-flash` and friends, optional)

### Testing and Security

- pytest, pytest-playwright, Playwright
- Bandit (SAST) and Safety (dependency audit)
- Lighthouse + `@lhci/cli` (performance, a11y, SEO budgets)
- axe-playwright (accessibility checks)
- Scalene (CPU/GPU profiler)
- OWASP Dependency-Check (GitHub Actions)

---

## Getting Started

This project runs entirely on your laptop. Pick the platform section that matches your OS and follow it top to bottom. The first run takes a few minutes (Ollama model pull + Python + Node installs); subsequent runs are fast.

### Prerequisites

- **Node.js 18 or above** (https://nodejs.org).
- **Python 3.10 or above** (https://www.python.org). On Windows make sure `py` is on PATH (it ships with the official installer).
- **Ollama** from https://ollama.com. After install, leave the desktop app running or run `ollama serve` once.
- **Llama 3.2 pulled locally**: `ollama pull llama3.2` (the launcher does this for you on first run).
- **PowerShell 5+** (built into Windows 10/11) for the one-click launcher.
- *(Optional)* Docker, only if you want to swap the JSON auth store for MongoDB.

> Disk budget: the Python venv with PyTorch and FAISS is ~2.5 GB; the Llama 3.2 model is ~2 GB. Plan for at least 6 GB free.

### Clone and install

```bash
git clone https://github.com/Trigyn-Intern/AI-recruiter-screening-system-.git
cd AI-recruiter-screening-system-
```

The repository ships with sensible defaults in `backend/.env`, `frontend/.env`, and `frontend-test/.env`. Override them only if you need to.

---

## Quick Start (Windows)

The fastest way for a brand-new user. Open PowerShell **as yourself** (admin not required) at the repo root and run:

```powershell
.\start-app.ps1
```

What it does, in order:

1. Creates `backend/data/users.json` if it is missing.
2. Frees ports `4000`, `5173`, `5174`, and `8000` if they are already in use.
3. Starts `ollama serve` on `http://127.0.0.1:11434` (or reuses a running instance) and pre-pulls `llama3.2`.
4. Creates the Python venv on first run and (re)installs `requirements.txt` only when the file changes.
5. Installs Node dependencies for the auth API, the recruiter app, and the testing dashboard (idempotent).
6. Launches the FastAPI analyzer on `http://127.0.0.1:8000` (4 workers, 90 s analyze timeout).
7. Launches the Node auth API on `http://localhost:4000` (auto-seeds the manager account from `backend/.env`).
8. Launches the React recruiter app on `http://localhost:5173`.
9. Launches the React testing dashboard on `http://localhost:5174`.

Wait ~10 seconds for each window to settle, then open:

- Recruiter UI: http://localhost:5173
- Testing UI: http://localhost:5174 (sign in with the manager credentials from `backend/.env`)
- Analyzer API: http://127.0.0.1:8000
- Auth API: http://localhost:4000

To shut the stack down, close the PowerShell windows it opened, or run:

```powershell
Get-Process node,python,ollama -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle -ne '' } | Stop-Process -Force
```

---

## Quick Start (macOS / Linux)

There is no `start-app.ps1` for POSIX yet, but the manual steps are short. Open four terminals at the repo root.

```bash
# 1. Ollama
ollama serve
ollama pull llama3.2

# 2. Python venv + analyzer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn api:api --host 127.0.0.1 --port 8000 --workers 4

# 3. Auth API
cd backend && npm install && npm run dev
# (in a new terminal)

# 4. Recruiter app
cd frontend && npm install && npm run dev
# (in a new terminal)

# 5. Testing dashboard (optional)
cd frontend-test && npm install && npm run dev
```

After ~10 s the four services should be reachable at the URLs listed in the Windows section above.

### If you prefer to run things by hand on Windows

```powershell
# Terminal 1 - Ollama
ollama serve

# Terminal 2 - FastAPI analyzer
.\venv\Scripts\activate
uvicorn api:api --host 127.0.0.1 --port 8000 --workers 4

# Terminal 3 - Node auth API
cd backend; npm run dev

# Terminal 4 - React frontend
cd frontend; npm run dev

# Terminal 5 - Testing dashboard (optional)
cd frontend-test; npm run dev
```

---

## Default credentials

| Account   | Email                    | Password      | Where it is set                                  |
| --------- | ------------------------ | ------------- | ------------------------------------------------ |
| Recruiter | any (sign up on screen)  | your choice   | n/a - sign up at http://localhost:5173/signup    |
| Manager   | `SEED_MANAGER_EMAIL`     | `SEED_MANAGER_PASSWORD` | `backend/.env`  |

The seeded manager account is created or rotated on every backend restart using `backend/seeders/seedManager.js`, so editing the env and restarting the auth API is the supported way to change the manager password.

---

## Testing

The repo ships a data-driven **scenario matrix** under `tests/data/scenarios.yaml` that drives the React UI end-to-end through Playwright, plus a fast pytest suite for the analyzer's pure logic.

### What the matrix covers

Each row in `tests/data/scenarios.yaml` pins together one Ollama model, one JD file, a set of resumes, and the expected top-ranked resume with a minimum acceptable match score. Adding a scenario is one YAML row; the runner, the tests, and CI all pick it up automatically.

```yaml
scenarios:
  - id: python_ml_llama32
    model: llama3.2
    jd_file: jds/jd_python_ml.txt
    resume_files: [resume_strong_python.pdf, resume_data_engineer.pdf, ...]
    expected_resume: resume_strong_python.pdf
    expected_min_score: 50
```

### One-click run with `tests/run.ps1`

`tests/run.ps1` is the supported entry point. It boots Ollama, the FastAPI analyzer, the Node auth API, the React dev server, runs the matrix with pytest, and renders the HTML report.

```powershell
# Run every scenario in tests/data/scenarios.yaml
pwsh tests/run.ps1

# Run a single scenario
pwsh tests/run.ps1 -Filter python_ml_llama32

# Run a comma-separated subset
pwsh tests/run.ps1 -Filter "python_ml_llama32,frontend_react_llama32"
```

What the script does for you:

1. Verifies the venv Python at `venv\Scripts\python.exe` (falls back to `python` on PATH).
2. Invokes `tests/ui/run_scenario_matrix.py`, which boots Ollama (and pulls any missing models), the FastAPI analyzer on :8000, the auth API on :4000, the React dev server on :5173, and the testing dashboard on :5174.
3. Runs pytest against `tests/ui/test_scenario_matrix.py` and writes JUnit XML to `reports/junit.json`.
4. Calls `tests/render_report.py` to produce a single-page, spreadsheet-style report at `reports/report.html`.
5. Tears the spawned services down on exit. Per-service logs land in `reports/logs/`.

### Generating the report from the command line

If you already have a `reports/junit.json` from a previous run (or from CI), you can re-render the HTML report at any time without re-running Playwright:

```powershell
# Activate the venv first
venv\Scripts\activate

python tests/render_report.py `
    --junit  reports/junit.json `
    --yaml   tests/data/scenarios.yaml `
    --output reports/report.html `
    --filter ""
```

On success the script prints `wrote reports/report.html` and exits 0. Open the file in any browser to inspect pass/fail per scenario, actual vs. expected top resume, and the matched scores.

### Lighthouse and accessibility

The CI workflow runs Lighthouse (performance, accessibility, best-practices, SEO) and axe-playwright against the recruiter app. The thresholds live in `lighthouserc.json`; tune them as the app grows.

```powershell
# Run Lighthouse locally against the running recruiter UI
lighthouse http://localhost:5173 --output=html --output-path=reports/lighthouse-report.html --chrome-flags="--headless"
```

---

## Project Structure

```
.
|-- api.py                    # FastAPI entrypoint for the analyzer
|-- backend.py                # Core analysis logic (LLM, FAISS, grading)
|-- default_prompts.py        # Default prompt templates (Python mirror of UI)
|-- requirements.txt          # Pinned Python dependencies
|-- start-app.ps1             # One-click stack launcher (Windows)
|-- backend/                  # Node + Express auth API
|   |-- server.js
|   |-- package.json
|   |-- seeders/seedManager.js
|   |-- controllers/
|   |-- middleware/
|   |-- models/
|   |-- routes/
|   `-- data/users.json
|-- frontend/                 # Recruiter app: React + Vite
|   `-- src/
|       |-- main.jsx          # React Router entry (login, signup, dashboard)
|       |-- App.jsx           # Analyzer + Configurations dashboard
|       |-- defaultModels.js
|       |-- defaultPrompts.js
|       |-- styles.css
|       |-- api/client.js
|       |-- assets/
|       `-- pages/
|           |-- RequireAuth.jsx
|           |-- auth/         # Login, Signup, auth.css
|           `-- dashboard/    # Dashboard, SkillsPage, dashboard.css
|-- frontend-test/            # Testing dashboard: React + Vite (port 5174)
|   `-- src/
|       |-- App.jsx
|       `-- pages/TestingDashboard.jsx
|-- vector_store/             # FAISS index, resume metadata, prompt config, session log
|-- tests/                    # pytest + Playwright scenario matrix
`-- skills/                   # Internal skill and security-review notes
```

---

## Configuration

### Auth API environment (`backend/.env`)

| Variable                 | Purpose                                                              | Default               |
| ------------------------ | -------------------------------------------------------------------- | --------------------- |
| `PORT`                   | Port the auth API listens on.                                        | `4000`                |
| `JWT_SECRET`             | Signing key for issued JWTs.                                         | random ephemeral      |
| `JWT_EXPIRES_IN`         | Token lifetime.                                                      | `7d`                  |
| `CLIENT_ORIGIN`          | CORS allow-list for the React apps.                                  | `http://localhost:5173` |
| `MONGO_URI`              | Reserved for a future MongoDB swap.                                 | unused with JSON store |
| `SEED_MANAGER_EMAIL`     | Email used by `seedManager.js` to create the manager account.        |  |
| `SEED_MANAGER_PASSWORD`  | Password for the seeded manager account. Edit + restart to rotate.   |          |
| `SEED_MANAGER_NAME`      | Display name for the seeded manager.                                | `Test Manager`        |

### Frontend environment (`frontend/.env`)

```
VITE_API_URL=http://localhost:4000
VITE_FASTAPI_URL=http://localhost:8000
```

### Testing dashboard environment (`frontend-test/.env`)

```
VITE_API_URL=http://localhost:4000
VITE_FASTAPI_URL=http://localhost:8000
```

### Analyzer environment (optional)

| Variable          | Purpose                                                |
| ----------------- | ------------------------------------------------------ |
| `OLLAMA_HOST`     | Ollama base URL. Defaults to `http://127.0.0.1:11434`. |
| `GEMINI_API_KEY`  | Enables the Gemini provider.                           |
| `ANALYZE_MAX_INFLIGHT` | Concurrency cap for in-flight analyzes.            |
| `ANALYZE_TIMEOUT_S`    | Hard timeout for a single analyze call (seconds).  |

The analyzer falls back to a deterministic local grader when no LLM is reachable, so the dashboard never goes blank mid-demo.

---

## Deployment

The repo is shaped to run locally today, but the components map cleanly to common hosts.

| Component        | Suggested host           | Notes                                                              |
| ---------------- | ------------------------ | ------------------------------------------------------------------ |
| Recruiter UI     | Vercel or Netlify        | Set the project root to `frontend/`. Forward `VITE_API_URL`.       |
| Testing UI       | Internal VM or staging   | Set the project root to `frontend-test/`.                          |
| Auth API         | Render, Fly, or a VM     | Stateless except for `backend/data/users.json`; mount a volume.    |
| Analyzer         | Render, Fly, or a VM     | Needs the FAISS volume and the embedding model cached.             |
| LLM              | Local Ollama or a host   | Swap to Gemini for a fully serverless deployment.                  |

For a quick serverless deploy, switch the AI provider to Gemini, build the recruiter UI with `npm run build` in `frontend/`, and serve the analyzer with `uvicorn api:api --host 0.0.0.0 --port $PORT`. The FAISS index can be rebuilt on first run from the resumes in `tests/data/resumes/`.

---

## Limitations and Roadmap

**Current limitations**

- One-time FAISS snapshot. There is no incremental refresh yet; re-uploading a resume with the same name rebuilds its vector.
- The JSON user store is fine for demos but not for multi-instance production. Swap to MongoDB or Postgres before scaling.
- LLM grading is best-effort: the JSON output is validated by `jsonschema` and falls back to a deterministic local grader on failure.
- Skill extraction depends on the LLM provider; switching providers changes recall.
- Lighthouse and axe checks run in CI but are not enforced as PR-blocking gates yet.

**Roadmap**

- Persistent recruiter accounts on MongoDB or Postgres.
- Cross-encoder re-ranking on top of the FAISS top-K.
- Larger embeddings (`BGE-M3` or `E5-large`) and embedding-store versioning.
- Parallel resume processing with `ThreadPoolExecutor`.
- Interview question generation per shortlisted candidate.
- Resume summarization cards on the dashboard.
- Cloud deployment recipes (Render + Vercel + a hosted LLM).
- Role-based access for recruiters and hiring managers.
- Lighthouse + axe budgets enforced in PR checks.

---

## Authors

The Trigyn team, with sustained collaboration from contributors during the prototype phase.

- Risha Batra
- Veda

---

## License

Released under the MIT License. See `LICENSE` for the full text.

---
## Acknowledgements

- Built with FastAPI, React, Vite, Sentence Transformers, FAISS, Ollama, Llama 3.2, and Google Gemini.
- Thanks to the open-source community behind `pypdf`, `python-docx`, `lucide-react`, `playwright`, and Lighthouse.