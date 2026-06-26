# Scenario-Driven Playwright Tests

This folder drives the AI Recruiter Screening System end-to-end from a single
YAML config. One Playwright test loops through every row of
`tests/data/scenarios.yaml`, and the runner script boots Ollama, the
FastAPI analyzer, the React dev server, and (optionally) the Node auth API
before invoking pytest.

The whole stack here is the **React + FastAPI** application. The legacy
Streamlit UI lives in `app.py` for reference only and is not exercised by
these tests.

## Layout

```
tests/data/
  scenarios.yaml             # the input matrix (model + JD + resumes)
  jds/                       # reusable JD text files
    jd_python_ml.txt
    jd_data_engineer.txt
    jd_frontend_react.txt
  resumes/                   # generated sample PDFs
    resume_strong_python.pdf
    resume_data_engineer.pdf
    resume_frontend.pdf
    resume_junior.pdf
  generate_resumes.py        # rebuilds the sample resume PDFs (reportlab)

tests/ui/
  conftest.py                # loads scenarios.yaml, parametrises the single test
  test_scenario_matrix.py    # THE Playwright test (one per scenario row)
  run_scenario_matrix.py     # automation runner (Ollama + uvicorn + vite + pytest)
  README.md                  # this file
  screenshots/               # full-page screenshots, one per scenario
```

## Scenario config

```yaml
scenarios:
  - id: python_ml_llama32
    model: llama3.2
    jd_file: jds/jd_python_ml.txt
    resume_files:
      - resumes/resume_strong_python.pdf
      - resumes/resume_data_engineer.pdf
      - resumes/resume_frontend.pdf
      - resumes/resume_junior.pdf
    expected_resume: resume_strong_python.pdf
    expected_min_score: 50
```

| Field              | Required | Meaning                                                            |
| ------------------ | -------- | ------------------------------------------------------------------ |
| `id`               | yes      | Stable identifier; used in `--scenario-filter` and the screenshot name. |
| `model`            | yes      | Ollama model tag (e.g. `llama3.2`). The runner `ollama pull`s it if missing. |
| `jd_file`          | yes      | Path to the JD, relative to the YAML file.                         |
| `resume_files`     | yes      | List of resume paths, relative to the YAML file.                   |
| `expected_resume`  | no       | Filename expected at rank #1.                                      |
| `expected_min_score` | no     | Minimum acceptable score for rank #1 (0-100).                       |

Add a row, rerun the runner - the test, screenshot, and CI job pick it up.

## Running locally

```bash
# from the repo root
python tests/ui/run_scenario_matrix.py            # run every scenario
python tests/ui/run_scenario_matrix.py --filter python_ml_llama32
python tests/ui/run_scenario_matrix.py --dry-run  # show what would run
python tests/ui/run_scenario_matrix.py --keep-streamlit  # leave servers up
```

The runner:

1. Validates Ollama and pulls any missing models.
2. Starts `uvicorn api:app` (FastAPI analyzer) on `127.0.0.1:8000`.
3. Starts `npm run dev` (Vite + React) on `localhost:5173`.
4. Starts the Node auth API on `localhost:4000` unless `--no-auth` is passed.
5. Waits for each health endpoint to respond.
6. Runs `pytest tests/ui/test_scenario_matrix.py` with the resolved
   `--scenario-config` and `--scenario-filter`.
7. Tears the spawned services down (unless `--keep-streamlit`).

To regenerate the sample resume PDFs:

```bash
python tests/data/generate_resumes.py
```

## What the test does

For every row in `scenarios.yaml` the test:

1. Logs in via the Node auth API and seeds the demo recruiter if needed.
2. Visits the React dashboard and switches to the **Configurations** tab.
3. Selects **Ollama** and the requested model.
4. Switches back to the **Analyzer** tab, re-confirms the model, uploads the
   resumes, pastes the JD, clicks **Analyze**.
5. Waits for the **Ranking** table to render.
6. Reads the top row and asserts on `expected_min_score` / `expected_resume`.
7. Saves a full-page screenshot to `tests/ui/screenshots/<id>.png`.

## Environment variables

| Variable          | Default                    | Used by                          |
| ----------------- | -------------------------- | -------------------------------- |
| `OLLAMA_HOST`     | `http://127.0.0.1:11434`   | runner                           |
| `API_PORT`        | `8000`                     | runner                           |
| `WEB_PORT`        | `5173`                     | runner                           |
| `AUTH_PORT`       | `4000`                     | runner                           |
| `API_BASE_URL`    | `http://127.0.0.1:8000`    | test                             |
| `WEB_BASE_URL`    | `http://localhost:5173`    | test                             |
| `AUTH_API_URL`    | `http://localhost:4000`    | test                             |
| `RECRUITER_EMAIL` | `qa-recruiter@example.com` | test (auto-seeds the account)    |
| `RECRUITER_PASSWORD` | `Recruiter!1`           | test                             |
| `SCENARIO_CONFIG` | `tests/data/scenarios.yaml`| conftest / pytest                |
| `SCENARIO_FILTER` | empty                      | conftest / pytest                |

## CI

`.github/workflows/ci.yml` defines two jobs that call this runner:

* `scenario-matrix` runs every scenario with the Ollama Docker service,
  uploads the screenshots + JUnit XML as artifacts.
* `playwright-smoke` runs a single filtered scenario (default
  `python_ml_llama32`) for fast PR feedback.
