// k6 load test for POST /analyze
// Usage (from the load/ folder):
//   cd tests/performance/load
//   k6 run score_endpoint.js
//   BASE_URL=http://localhost:8000 k6 run score_endpoint.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Counter, Rate, Trend } from 'k6/metrics';

// ---------- Init stage (runs once per VU group, NOT per iteration) ----------
const SCRIPT_DIR = __ENV.K6_SCRIPT_DIR || '.';
const JD_FILE = `${SCRIPT_DIR}/jd.txt`;

// Hard-coded absolute paths so k6 doesn't have to parse a text file
// or deal with spaces in the repo path. Update these if the repo moves.
const explicitPaths = [
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_strong_python.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_data_engineer.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_frontend.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_junior.pdf',
];

// Pre-load every resume into a SharedArray at init time.
// open() is only valid in the init stage, so this MUST be top-level.
const resumes = new SharedArray('resumes', function () {
  return explicitPaths.map((p) => ({
    name: p.split(/[\\/]/).pop(),
    bytes: open(p, 'b'),
  }));
});

const jobDescription = open(JD_FILE);

// ---------- Per-iteration metrics ----------
const analyzeErrors = new Counter('analyze_errors');
const analyzeDuration = new Trend('analyze_duration_ms', true);
const analyzeSuccess = new Rate('analyze_success');

export const options = {
  scenarios: {
    ramp: {
      executor: 'ramping-vus',
      startVUs: 0,
      
      stages: [
        { duration: '2m',  target: 10 }, // Ramp up to 10 users quickly
        { duration: '30m', target: 10 }, // Stay at 10 users for half an hour (The Soak)
        { duration: '2m',  target: 0  }, // Gentle ramp down
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<8000'],
    http_req_failed:   ['rate<0.05'],
    analyze_success:   ['rate>0.90'],
  },
};

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

// ---------- VU code ----------
export default function () {
  const r = resumes[Math.floor(Math.random() * resumes.length)];

  // k6's http.file wants a string or ArrayBuffer. The bytes we loaded
  // via open(p, 'b') arrive as Uint8Array; wrap in an ArrayBuffer so
  // the multipart encoder is happy.
  const buf = new Uint8Array(r.bytes).buffer;

  const form = {
    job_description: jobDescription,
    provider: 'Gemini',
    resumes: http.file(buf, r.name, 'application/pdf'),
  };

  const res = http.post(`${BASE}/analyze`, form);
  analyzeDuration.add(res.timings.duration);
  analyzeSuccess.add(res.status === 200);
  if (res.status !== 200) analyzeErrors.add(1);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'has results':   (r) => {
      try { return JSON.parse(r.body).results && JSON.parse(r.body).results.length > 0; }
      catch { return false; }
    },
  });

  sleep(1);
}