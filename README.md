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
