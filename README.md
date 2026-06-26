# AI Recruiter Screening System

## Overview

The AI Recruiter Screening System is an intelligent resume screening application that helps recruiters evaluate and rank multiple candidates against a given Job Description (JD). The system uses Artificial Intelligence, Natural Language Processing (NLP), and semantic similarity techniques to automate the initial screening process.

The application extracts information from resumes, analyzes job descriptions, calculates resume-job match scores, performs skill gap analysis, and generates candidate rankings to assist recruiters in making faster and more informed hiring decisions.

A modern React + FastAPI frontend replaces the legacy Streamlit UI and adds a recruiter authentication screen.

---

## Features

* Secure recruiter login and signup flow (default demo credentials shown on the login screen)
* Upload and analyze multiple resumes simultaneously
* Supports PDF and Word document resumes
* AI-powered Job Description analysis
* Resume-to-JD semantic matching
* Skill gap analysis
* Candidate ranking dashboard
* Categorization of candidates into:

  * Good Fit
  * Moderate Fit
  * Bad Fit
* Detailed resume-level analysis
* Configurable AI provider (Ollama or Gemini) and model
* Editable prompt templates for JD analysis, skill gap, candidate detail, and resume skill extraction
* Local AI processing using Ollama and Llama 3.2 (with Gemini as an alternative)
* Interactive web interface built with React, Vite, and FastAPI

---

## Technologies Used

### Frontend

* React 18
* Vite
* React Router
* lucide-react icons
* Plain CSS (Outfit font, glassmorphism auth screen)

### Backend

* Python 3.10+
* FastAPI
* Uvicorn

### Artificial Intelligence & NLP

* Ollama (Llama 3.2 by default)
* Google Gemini (optional)
* Sentence Transformers
* Cosine Similarity
* FAISS (vector store)

### Libraries

* pypdf
* python-docx
* Pandas
* Scikit-Learn
* Sentence Transformers
* Ollama Python Library
* google-genai
* jsonschema
* pytest, pytest-playwright, bandit (testing and security)

---

## System Architecture

Recruiter Login
â†“
React Frontend (Vite, React Router)
â†“
FastAPI Backend (`api.py`)
â†“
Resume Text Extraction (pypdf / python-docx)
â†“
Embedding Generation (Sentence Transformers + FAISS)
â†“
Semantic Similarity Calculation
â†“
Match Score Generation
â†“
Skill Gap Analysis using Llama 3.2 / Gemini
â†“
Candidate Ranking
â†“
Recruiter Dashboard

---

## Prerequisites

Before running the application, ensure the following software is installed:

### Node.js (for the React frontend)

Install Node.js 18 or above.

Verify installation:

```bash
node --version
npm --version
```

### Python

Install Python 3.10 or above.

Verify installation:

```bash
python --version
```

### Ollama

Download and install Ollama from:

https://ollama.com

Verify installation:

```bash
ollama --version
```

### Llama 3.2 Model

Pull the model locally:

```bash
ollama pull llama3.2
```

---

## Installation

### Clone the Repository

```bash
git clone <repository-url>
cd AI-recruiter-screening-system-
```

### Backend Setup

Create a virtual environment:

```bash
python -m venv venv
```

Activate the virtual environment:

Windows:

```bash
venv\Scripts\activate
```

Mac/Linux:

```bash
source venv/bin/activate
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

### Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the Application

There are two ways to start the stack: the one-click PowerShell script, or the manual multi-terminal flow.

### Option 1 — One-click: `start-app.ps1` (recommended)

From the project root, run:

```powershell
.\start-app.ps1
```

What the script does for you:

1. Starts the `recruiter-mongo` Docker container (creates it on first run, see Auth backend below).
2. Frees ports 4000, 8000, and 5173 if anything is still bound to them.
3. Opens a new terminal running `ollama serve` on `http://127.0.0.1:12000`.
4. Opens a new terminal running `ollama pull llama3.2` to make sure the model is present.
5. Creates the Python `venv` (first run only) and installs `requirements.txt`.
6. Opens a new terminal running the FastAPI analyzer: `uvicorn api:api --host 127.0.0.1 --port 8000`.
7. Opens a new terminal running the Node auth API: `npm run dev` inside `backend/`.
8. Opens a new terminal running the React frontend: `npm run dev` inside `frontend/`.

Once all five windows are up, open the web app:

```text
http://localhost:5173/
```

The FastAPI analyzer listens on `http://127.0.0.1:8000`, the Node auth API on `http://127.0.0.1:4000`, and Ollama on `http://127.0.0.1:12000` (note: the script intentionally uses 12000 to avoid clashing with another Ollama instance on 11434).

To stop everything, close the spawned PowerShell windows or run:

```powershell
Get-Process powershell -ErrorAction SilentlyContinue | Where-Object {
    $_.MainWindowTitle -match 'ollama|uvicorn|npm run dev'
} | Stop-Process -Force
```

### Option 2 — Manual start (if you do not want to use the script)

Use five separate terminals. Activate the venv in the Python terminals.

Terminal 1 — MongoDB (skip if you already have it running):

```bash
docker start recruiter-mongo
# or, for a one-off container:
docker run -d --name recruiter-mongo -p 27017:27017 mongo
```

Terminal 2 — Ollama:

```bash
ollama serve
# Optional: pre-pull the default model
ollama pull llama3.2
```

If you do not need a parallel Ollama on port 12000, just let `ollama serve` use the default `127.0.0.1:11434`. The backend reads `OLLAMA_HOST` from the environment, so set it to match:

```powershell
$env:OLLAMA_HOST = "http://127.0.0.1:11434"
```

Terminal 3 — FastAPI analyzer (venv activated, project root):

```bash
uvicorn api:api --host 127.0.0.1 --port 8000 --reload
```

Terminal 4 — Node auth API (first run: `cd backend && npm install`):

```bash
cd backend
npm run dev
```

Terminal 5 — React frontend (first run: `cd frontend && npm install`):

```bash
cd frontend
npm install     # first run only
npm run dev
```

Once every terminal reports a ready state, the app is live at `http://localhost:5173/`. The default demo credentials are shown on the login screen.


## How to Use

1. Launch Ollama, the FastAPI backend, and the React frontend.
2. Open `http://localhost:5173/` and sign in with the demo credentials shown on the login screen.
3. Upload one or more resumes (PDF or DOCX).
4. Paste the Job Description.
5. Pick the AI provider and model (defaults are preconfigured).
6. Click **Analyze** and wait for the system to evaluate the JD.
7. View:

   * Match Scores
   * Candidate Rankings
   * Skill Gap Analysis
   * Candidate Categorization
8. Switch to the **Configurations** tab to edit prompts or reset them to the defaults.
9. Use the **Logout** button in the header to return to the login screen.

New users can click **Sign up** on the login screen to create an account; the form validates the username, email, and matching passwords before returning to the login page.

---

## AI Models Used

### 1. Sentence Transformer

Model:

```text
all-MiniLM-L6-v2
```

Purpose:

* Generate text embeddings
* Resume-JD semantic matching
* Match score calculation
* FAISS-backed vector retrieval

### 2. Llama 3.2 (Ollama) and Gemini

Models:

```text
llama3.2
gemini-2.5-flash
```

Purpose:

* Job Description Analysis
* Skill Extraction
* Skill Gap Analysis
* Recruitment Intelligence

---

## Future Enhancements

* Persistent recruiter accounts (currently a local demo login)
* Vector Database tuning (FAISS / ChromaDB)
* BGE Large Embedding Models
* Cross Encoder Re-ranking
* Parallel Resume Processing
* Candidate Recommendation Engine
* Interview Question Generation
* Resume Summarization
* Cloud Deployment
* Role-based access control for recruiters and hiring managers

---

## Performance Optimizations

Implemented:

* Cached embedding model loading
* FAISS vector store for resumable candidate profiles
* On-demand AI analysis for resume details
* Single JD analysis for multiple resumes

Planned:

* Parallel processing using ThreadPoolExecutor
* Embedding storage versioning for reusable candidate profiles
* Server-side recruiter session management

---

## Project Structure

```text
AI-recruiter-screening-system-/
â”‚
â”œâ”€â”€ api.py
â”œâ”€â”€ backend.py
â”œâ”€â”€ app.py                    # Legacy Streamlit entry point kept for reference
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ README.md
â”œâ”€â”€ tests/
â”‚   â”œâ”€â”€ test_extraction.py
â”‚   â”œâ”€â”€ test_json.py
â”‚   â”œâ”€â”€ test_ollama.py
â”‚   â”œâ”€â”€ test_scoring.py
â”‚   â”œâ”€â”€ test_validation.py
â”‚   â””â”€â”€ ui/                  # Playwright end-to-end tests
â”‚
â””â”€â”€ frontend/
    â”œâ”€â”€ index.html
    â”œâ”€â”€ package.json
    â””â”€â”€ src/
        â”œâ”€â”€ main.jsx          # React Router entry (login, signup, dashboard)
        â”œâ”€â”€ App.jsx           # Analyzer + Configurations dashboard
        â”œâ”€â”€ defaultModels.js
        â”œâ”€â”€ defaultPrompts.js
        â”œâ”€â”€ styles.css
        â”œâ”€â”€ assets/
        â”‚   â””â”€â”€ monstera_bg.png
        â””â”€â”€ pages/
            â”œâ”€â”€ RequireAuth.jsx
            â”œâ”€â”€ auth/
            â”‚   â”œâ”€â”€ Login.jsx
            â”‚   â”œâ”€â”€ Signup.jsx
            â”‚   â””â”€â”€ auth.css
            â””â”€â”€ dashboard/
                â”œâ”€â”€ Dashboard.jsx
                â””â”€â”€ dashboard.css
```

---

## Authors

Developed as an AI-powered Resume Screening and Candidate Ranking System using React, FastAPI, Sentence Transformers, Ollama, Llama 3.2, and Google Gemini.

---

## Auth Backend (Node.js + Express + MongoDB)

The React login/signup pages now call a separate Node.js API. The legacy FastAPI analyzer still runs on port 8000; the auth API listens on `http://localhost:4000` and persists users in MongoDB.

### Prerequisites

- Node.js 18+
- A running MongoDB instance (local install, Docker container, or Atlas cluster)

### Setup

```bash
cd backend
cp .env.example .env
npm install
npm run dev
```

### `backend/.env` variables

| Variable | What it is | Where to get it |
| --- | --- | --- |
| `PORT` | Port the auth API listens on. | Pick any free port; default `4000`. |
| `MONGO_URI` | MongoDB connection string used by Mongoose. | Local: `mongodb://127.0.0.1:27017/ai_recruiter` (start `mongod` or `docker run -p 27017:27017 mongo`). Atlas: copy the "Connect your application" URI from the Atlas dashboard and replace `<password>` with the database user password. |
| `JWT_SECRET` | Signing key for the JWT issued on login/signup. | Generate one with `node -e "console.log(require('crypto').randomBytes(48).toString('hex'))"` and paste it here. Never commit it. |
| `JWT_EXPIRES_IN` | Token lifetime accepted by `jsonwebtoken` (e.g. `7d`, `12h`). | Pick any value supported by [the `ms` library](https://github.com/vercel/ms#examples). |
| `CLIENT_ORIGIN` | Allowed CORS origin for the React app. | The URL Vite serves the frontend on; default `http://localhost:5173`. |

### Frontend env

`frontend/.env`:

```
VITE_API_URL=http://localhost:4000
```

Override `VITE_API_URL` if the auth API runs on a different host/port.

### API

- `POST /api/auth/signup` — `{ name, email, password, confirmPassword }` → `{ token, user }`.
- `POST /api/auth/login` — `{ email, password }` → `{ token, user }`.
- `GET /api/auth/me` — `Authorization: Bearer <token>` → `{ user }`.
- `GET /api/health` — liveness probe.

The React frontend stores the returned token under `localStorage.recruiter.token` and the user under `localStorage.recruiter.user`, then redirects to `/dashboard`. `RequireAuth` and `Dashboard` call `/api/auth/me` to refresh the session and clear storage on 401.

