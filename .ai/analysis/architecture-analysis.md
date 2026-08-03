# Architecture Analysis

## Goal
Validate boundaries and integration health across the React frontend, Express auth API,
FastAPI analyzer, LLM providers, and FAISS vector store.

## Inspect
- Frontend to API contract consistency.
- Authentication and authorization boundaries.
- Ownership of business logic and data validation.
- Error handling, retries, timeouts, and fallbacks.
- Persistence schema compatibility for vector_store data.
- Coupling between UI, API routes, AI prompts, and storage.

## Output
Document the current architecture, violated boundaries, risks, and a prioritized
improvement plan. Use Mermaid for diagrams when helpful.
