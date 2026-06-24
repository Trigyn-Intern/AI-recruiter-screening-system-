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
↓
React Frontend (Vite, React Router)
↓
FastAPI Backend (`api.py`)
↓
Resume Text Extraction (pypdf / python-docx)
↓
Embedding Generation (Sentence Transformers + FAISS)
↓
Semantic Similarity Calculation
↓
Match Score Generation
↓
Skill Gap Analysis using Llama 3.2 / Gemini
↓
Candidate Ranking
↓
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

Start Ollama in one terminal:

```bash
ollama serve
```

Start the FastAPI backend in another terminal (with the virtual environment activated):

```bash
uvicorn api:app --reload --port 8000
```

Start the React frontend in a third terminal:

```bash
cd frontend
npm run dev
```

The web app will open automatically in your browser.

Default URL:

```text
http://localhost:5173/
```

The FastAPI backend listens on:

```text
http://127.0.0.1:8000
```

---

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
│
├── api.py
├── backend.py
├── app.py                    # Legacy Streamlit entry point kept for reference
├── requirements.txt
├── README.md
├── tests/
│   ├── test_extraction.py
│   ├── test_json.py
│   ├── test_ollama.py
│   ├── test_scoring.py
│   ├── test_validation.py
│   └── ui/                  # Playwright end-to-end tests
│
└── frontend/
    ├── index.html
    ├── package.json
    └── src/
        ├── main.jsx          # React Router entry (login, signup, dashboard)
        ├── App.jsx           # Analyzer + Configurations dashboard
        ├── defaultModels.js
        ├── defaultPrompts.js
        ├── styles.css
        ├── assets/
        │   └── monstera_bg.png
        └── pages/
            ├── RequireAuth.jsx
            ├── auth/
            │   ├── Login.jsx
            │   ├── Signup.jsx
            │   └── auth.css
            └── dashboard/
                ├── Dashboard.jsx
                └── dashboard.css
```

---

## Authors

Developed as an AI-powered Resume Screening and Candidate Ranking System using React, FastAPI, Sentence Transformers, Ollama, Llama 3.2, and Google Gemini.