# Architecture Report

## Current Components

```mermaid
flowchart LR
  UI[React recruiter UI] --> AUTH[Express auth API]
  UI --> API[FastAPI analyzer]
  API --> LLM[Ollama or Gemini]
  API --> STORE[FAISS vector store]
  QA[React testing dashboard] --> REPORTS[Local reports]
```

## Validation Focus

- Maintain a documented contract between the React UI, Express auth API, and FastAPI analyzer.
- Keep candidate data local unless a hosted provider is explicitly selected.
- Version vector-store metadata before modifying persisted structures.
- Use deterministic fallback behavior when an LLM provider is unavailable.
