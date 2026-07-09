/**
 * k6 Load Test — Resume Upload Flow
 *
 * Simulates concurrent recruiters uploading resumes and triggering AI scoring.
 *
 * Run locally (requires the API running):
 *   uvicorn api:app --host 0.0.0.0 --port 8000
 *   k6 run tests/performance/load/upload_flow.js
 *
 * Override base URL:
 *   k6 run -e BASE_URL=http://staging:8000 tests/performance/load/upload_flow.js
 */
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate, Counter } from 'k6/metrics';

// Custom metrics
const uploadLatency = new Trend('upload_latency_ms');
const errorRate     = new Rate('error_rate');
const totalUploads  = new Counter('total_uploads');

export const options = {
  stages: [
    { duration: '30s', target: 10 }, // Ramp up to 10 virtual users
    { duration: '1m',  target: 20 }, // Hold at 20 concurrent users for 1 minute
    { duration: '30s', target: 0  }, // Ramp down
  ],
  thresholds: {
    // 95th percentile latency must stay under 2 seconds
    http_req_duration: ['p(95)<2000'],
    // Error rate must stay below 1%
    error_rate:        ['rate<0.01'],
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';

export default function () {
  // ---- 1. Health check ----
  const health = http.get(`${BASE_URL}/health`);
  check(health, { 'health OK': (r) => r.status === 200 });

  // ---- 2. Resume analysis (main load target) ----
  const payload = JSON.stringify({
    resume_text: (
      'Jane Smith — Senior Python Engineer.\n' +
      'Skills: Python, FastAPI, PostgreSQL, Docker, REST APIs.\n' +
      'Experience: 6 years. Built high-throughput data pipelines.\n' +
      'Education: B.S. Computer Science, State University.'
    ),
    job_description: (
      'We are hiring a Backend Engineer with Python and FastAPI experience.\n' +
      'Requirements: 3+ years Python, REST APIs, SQL databases, Docker.'
    ),
  });

  const params = {
    headers: { 'Content-Type': 'application/json' },
    timeout: '15s',
  };

  const start = Date.now();
  const res   = http.post(`${BASE_URL}/analyze`, payload, params);
  uploadLatency.add(Date.now() - start);
  totalUploads.add(1);

  const ok = check(res, {
    'status 200':        (r) => r.status === 200,
    'response has body': (r) => r.body && r.body.length > 0,
  });

  errorRate.add(ok ? 0 : 1);

  // Simulate recruiter think-time between uploads (1 second)
  sleep(1);
}
