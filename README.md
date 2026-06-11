# AI Recruiter Screening System

## Overview

The AI Recruiter Screening System is an intelligent resume screening application that helps recruiters evaluate and rank multiple candidates against a given Job Description (JD). The system uses Artificial Intelligence, Natural Language Processing (NLP), and semantic similarity techniques to automate the initial screening process.

The application extracts information from resumes, analyzes job descriptions, calculates resume-job match scores, performs skill gap analysis, and generates candidate rankings to assist recruiters in making faster and more informed hiring decisions.

---

## Features

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
* Local AI processing using Ollama and Llama 3.2
* Interactive web interface built with Streamlit

---

## Technologies Used

### Frontend

* Streamlit

### Backend

* Python

### Artificial Intelligence & NLP

* Ollama
* Llama 3.2
* Sentence Transformers
* Cosine Similarity

### Libraries

* PyPDF2
* Pandas
* Scikit-Learn
* Sentence Transformers
* Ollama Python Library
* python-docx

---

## System Architecture

Resume Upload
↓
Text Extraction
↓
Embedding Generation
↓
Semantic Similarity Calculation
↓
Match Score Generation
↓
Skill Gap Analysis using Llama 3.2
↓
Candidate Ranking
↓
Recruiter Dashboard

---

## Prerequisites

Before running the application, ensure the following software is installed:

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
cd resume-analyzer
```

### Create Virtual Environment

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

### Install Dependencies

```bash
pip install -r requirements.txt
```

If requirements.txt is unavailable:

```bash
pip install streamlit
pip install PyPDF2
pip install pandas
pip install scikit-learn
pip install sentence-transformers
pip install ollama
pip install python-docx
```

---

## Running the Application

Start Ollama:

```bash
ollama serve
```

Open a new terminal and activate the virtual environment.

Run the Streamlit application:

```bash
streamlit run app.py
```

The application will open automatically in your browser.

Default URL:

```text
http://localhost:8501
```

---

## How to Use

1. Launch the application.
2. Upload one or more resumes.
3. Paste the Job Description.
4. Wait for the system to analyze the JD.
5. View:

   * Match Scores
   * Candidate Rankings
   * Skill Gap Analysis
   * Candidate Categorization
6. Expand individual candidates to view detailed analysis.

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

### 2. Llama 3.2

Model:

```text
llama3.2
```

Purpose:

* Job Description Analysis
* Skill Extraction
* Skill Gap Analysis
* Recruitment Intelligence

---

## Future Enhancements

* Vector Database Integration (FAISS / ChromaDB)
* BGE Large Embedding Models
* Cross Encoder Re-ranking
* Parallel Resume Processing
* Candidate Recommendation Engine
* Interview Question Generation
* Resume Summarization
* Cloud Deployment
* Recruiter Login and Authentication

---

## Performance Optimizations

Implemented:

* Cached embedding model loading using Streamlit cache
* On-demand AI analysis for resume details
* Single JD analysis for multiple resumes

Planned:

* Parallel processing using ThreadPoolExecutor
* Vector search-based retrieval
* Embedding storage for reusable candidate profiles

---

## Project Structure

```text
resume-analyzer/
│
├── app.py
├── requirements.txt
├── README.md
├── resumes/
│
└── venv/
```

---

## Authors

Developed as an AI-powered Resume Screening and Candidate Ranking System using Streamlit, Sentence Transformers, Ollama, and Llama 3.2.
