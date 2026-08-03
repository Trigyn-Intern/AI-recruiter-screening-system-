# Technical Debt Report

Generated: 2026-07-19

## Summary

The local frontend and testing-dashboard production builds pass. The Bandit scan has no
high-severity findings. The normal unit-test gate is blocked before collection because
`pytest.ini` starts with `test]` instead of the required `[pytest]` section header. A retry
without that configuration collected 28 tests: 27 passed and 1 failed.

| Severity | Count | Status |
| --- | ---: | --- |
| High | 2 | Open |
| Medium | 3 | Open |
| Low | 1 | Open |

## Findings

### TD-001 - Invalid pytest configuration

- Severity: High
- Location: `pytest.ini:1`
- Evidence: `pytest tests/unit -q` stops with `unexpected line: 'test]'`.
- Impact: Local and CI unit tests cannot collect or run, so quality gates are ineffective.
- Remediation: Restore the header to `[pytest]`, retain the intended options, then run
  `venv\\Scripts\\python.exe -m pytest tests/unit -q`.
- Estimate: 5 minutes.

### TD-002 - CI lacks an executable end-to-end Playwright job

- Severity: Medium
- Location: `.github/workflows/ci.yml`
- Evidence: The workflow now runs unit tests and frontend builds, while the scenario matrix
  remains available through `tests/run.ps1` and is not invoked by the CI workflow.
- Impact: A frontend/API/LLM integration regression can merge without a scenario-matrix run.
- Remediation: Add a Linux-compatible CI job which starts required local services, runs the
  scenario matrix, and uploads JUnit, screenshots, and HTML reports.
- Estimate: 1-2 days.

### TD-003 - Cached FAISS embedding test fails

- Severity: High
- Location: `tests/unit/test_scoring.py:41`
- Evidence: A configuration-bypassing run produced `1 failed, 27 passed`; the cached FAISS
  embedding shape was a `MagicMock` instead of the expected `(1, 1024)`.
- Impact: The cache-path regression test does not currently verify its expected behavior.
- Remediation: Correct the test double or cache implementation so the reconstructed embedding
  has the expected NumPy shape, then rerun the unit suite with the normal pytest configuration.
- Estimate: 1-2 hours.

### TD-004 - Safety is missing from the local virtual environment

- Severity: Medium
- Location: `venv/`
- Evidence: `venv\\Scripts\\python.exe -m safety check --file requirements.txt --full-report`
  failed with `No module named safety`.
- Impact: Local dependency-vulnerability validation cannot run before commit or push.
- Remediation: Install the locked security tooling in the development environment and ensure
  the command is included in the documented local quality workflow.
- Estimate: 15 minutes.

### TD-005 - Security scan results are not retained as workflow artifacts

- Severity: Medium
- Location: `.github/workflows/ci.yml`
- Evidence: Bandit and Safety commands produce console output only.
- Impact: Trend analysis, audit evidence, and dashboard consumption are limited.
- Remediation: Emit JSON reports and upload them with `actions/upload-artifact`.
- Estimate: 2-4 hours.

### TD-006 - CodeQL workflow encoding prevents normal patch tooling

- Severity: Low
- Location: `.github/workflows/codeql.yml`
- Evidence: The file is not UTF-8, so standard patch tooling cannot safely modify it.
- Impact: Routine CI maintenance is more error-prone.
- Remediation: Normalize the file to UTF-8 without changing YAML semantics, then validate it.
- Estimate: 15 minutes.

## Verified Checks

| Check | Result |
| --- | --- |
| Bandit high-severity scan | Pass - 0 high-severity findings |
| Recruiter frontend build | Pass |
| Testing-dashboard build | Pass |
| Pytest unit suite | Blocked by TD-001; configuration-bypassing retry: 27 passed, 1 failed (TD-003) |
| Safety dependency scan | Blocked locally: Safety package is not installed (TD-004) |
| Lighthouse | Configured separately in `.github/workflows/lighthouse.yml`; not run locally because the recruiter stack was not started |

## Recommended Sequence

1. Repair the pytest header, then repair the cached FAISS test failure and rerun unit tests.
2. Install Safety locally and run the dependency scan.
3. Add and validate the end-to-end CI job.
4. Retain security and test artifacts for dashboard and audit use.
5. Normalize the CodeQL workflow encoding.
