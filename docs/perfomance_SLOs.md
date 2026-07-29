# Performance Service Level Objectives (SLOs)

This document defines the acceptable performance limits for the AI Recruiter Screening System. These limits are enforced via GitHub Actions using k6.

## Endpoints

### 1. `POST /api/upload`
Handles multi-part form uploads for resumes and triggers initial parsing.
* **Throughput:** Must handle 20 concurrent users.
* **Latency (p95):** < 2000 ms
* **Error Rate:** < 1%

### 2. `POST /api/score`
Triggers the LLM inference for skill extraction and ranking.
* **Throughput:** Must handle 10 concurrent requests.
* **Latency (p95):** < 5000 ms (Due to LLM processing times)
* **Error Rate:** < 2%

### 3. `GET /api/candidates`
Fetches the ranked list of candidates from the database.
* **Throughput:** Must handle 50 concurrent users.
* **Latency (p95):** < 500 ms
* **Error Rate:** < 0.1%

| Metric                          | Target        | How we measure                       |
| ------------------------------- | ------------- | ------------------------------------ |
| `extract_text` per resume       | p95 < 50ms    | `pytest-benchmark` per-file row      |
| End-to-end scoring              | p95 < 5s      | `tests/performance/load/score.js` k6 |
| Concurrent users on `/score`    | 50 @ p95 < 8s | k6 stages ramp                       |

| Endpoint | p50 | p95 | p99 | Max error rate |
|----------|-----|-----|-----|----------------|
| `POST /analyze` (1 resume) | 4s | 8s | 15s | 5% |
| `GET /health` | 5ms | 20ms | 50ms | 1% |
| `GET /resume-db` | 50ms | 200ms | 500ms | 1% |


# Service Level Objectives

## Current state (measured 2026-07-06)
- Single-process FastAPI: 1 worker, p95 = 60s, success = 23% at 100 VUs.
- 4-worker stack: p95 = 8-15s, success = 85-95% at 25 VUs (target).

## Target SLOs

| Endpoint            | p50  | p95  | p99  | Max error rate |
|---------------------|------|------|------|----------------|
| POST /analyze (1 resume)  | 4s   | 8s   | 15s  | 5%             |
| POST /analyze (5 resumes) | 8s   | 15s  | 30s  | 5%             |
| GET  /health        | 5ms  | 20ms | 50ms | 1%             |
| GET  /resume-db     | 50ms | 200ms| 500ms| 1%             |
| GET  /configuration | 20ms | 100ms| 300ms| 1%             |

## How we measure
- pytest-benchmark: `tests/performance/benchmarks/` (CI: 25% regression gate)
- k6 load test: `tests/performance/load/score_endpoint.js` (manual, weekly)
- cProfile: `tests/performance/profiles/run_profiler.py` (on demand)

## Alerting
- Any SLO breach in PR = block merge.
- Production weekly k6 run = create issue if p95 > SLO.