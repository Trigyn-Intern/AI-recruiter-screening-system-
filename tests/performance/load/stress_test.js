// Stress test: ramp to 500 VUs to find the breaking point.
//   cd tests/performance/load
//   k6 run stress_test.js

import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';

const explicitPaths = [
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_strong_python.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_data_engineer.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_frontend.pdf',
  'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_junior.pdf',
];

const resumes = new SharedArray('resumes', function () {
  return explicitPaths.map((p) => ({
    name: p.split(/[\\/]/).pop(),
    bytes: open(p, 'b'),
  }));
});

const jd = open(`${__ENV.K6_SCRIPT_DIR || '.'}/jd.txt`);

export const options = {
  scenarios: {
    stress: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '1m',  target: 1},
        { duration: '2m',  target: 50},
        { duration: '2m',  target: 100 },
        { duration: '1m',  target: 0   },
      ],
      gracefulRampDown: '30s',
    },
  },
  thresholds: {
    // No hard pass/fail here - this test is for finding the ceiling.
    // Read the summary to identify where p95 / error rate starts to spike.
    http_req_failed:   ['rate<0.50'],
  },
};

const BASE = __ENV.BASE_URL || 'http://127.0.0.1:8000';

export default function () {
  const r = resumes[Math.floor(Math.random() * resumes.length)];
  const buf = new Uint8Array(r.bytes).buffer;
  const form = {
    job_description: jd,
    provider: 'Gemini',
    resumes: http.file(buf, r.name, 'application/pdf'),
  };
  const res = http.post(`${BASE}/analyze`, form, { timeout: '120s' });
  check(res, { 'status is 200': (x) => x.status === 200 });
  sleep(1);
}