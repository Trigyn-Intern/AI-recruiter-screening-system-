import http from 'k6/http';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';

const resumes = new SharedArray('resumes', function () {
  return [
    'D:/trigyn/trigyn project/AI-recruiter-screening-system-/tests/data/resumes/resume_strong_python.pdf',
  ].map(p => ({ name: p.split('/').pop(), bytes: open(p, 'b') }));
});

const jd = open(`${__ENV.K6_SCRIPT_DIR || '.'}/jd.txt`);

export const options = {
  scenarios: {
    soak: {
      executor: 'constant-vus',
      vus: 5,
      duration: '30m',
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<20000'],
    http_req_failed: ['rate<0.10'],
  },
};

export default function () {
  const r = resumes[0];
  const buf = new Uint8Array(r.bytes).buffer;
  const form = {
    job_description: jd,
    provider: 'Gemini',
    resumes: http.file(buf, r.name, 'application/pdf'),
  };
  const res = http.post('http://127.0.0.1:8000/analyze', form, { timeout: '60s' });
  check(res, { 'status 200': r => r.status === 200 });
  sleep(2);
}