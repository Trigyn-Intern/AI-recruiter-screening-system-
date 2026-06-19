
## How a scenario row maps to a test case

`tests/data/scenarios.yaml` is a list of scenarios. Each scenario becomes
one parameterized pytest case.

```yaml
scenarios:
  - id: "python_ml_llama32"            # becomes the pytest test id
    model: "llama3.2"                  # selected in the Configurations tab
    jd_file: "tests/data/jds/jd_python_ml.txt"
    resume_files:
      - "tests/data/resumes/resume_strong_python.pdf"
      - "tests/data/resumes/resume_data_engineer.pdf"
    expected_min_score: 50             # optional soft assertion
    expected_resume: "resume_strong_python.pdf"  # optional top-1 check
    # or, when several resumes may legitimately tie for #1:
    expected_resumes_any:
      - "resume_strong_python.pdf"
      - "resume_data_engineer.pdf"
    notes: "..."
```

Adding a new combination is just adding a row. The runner and the test do
not need to change.

## How to run it locally

```powershell
# (venv active)
python tests\ui\run_scenario_matrix.py
```

Optional flags:

```powershell
# Run only scenarios whose id contains "python"
python tests\ui\run_scenario_matrix.py --filter python

# Use a custom config file
python tests\ui\run_scenario_matrix.py --config my_scenarios.yaml

# Keep Streamlit running after pytest finishes (handy for poking at the UI)
python tests\ui\run_scenario_matrix.py --keep-streamlit

# Dry run: print what would be executed without doing anything
python tests\ui\run_scenario_matrix.py --dry-run
```

The runner:

1. Checks that every requested Ollama model is installed (`ollama list`);
   if not, it pulls the missing ones.
2. Starts `streamlit run app.py` on a free port if one is not already up.
3. Runs `pytest tests/ui/test_scenario_matrix.py -v`, which executes the
   parameterized test once per scenario row.
4. Stops the Streamlit process it started (use `--keep-streamlit` to keep
   it running for manual inspection).

### PowerShell note on `--pytest-args`

PowerShell rewrites `--pytest-args=...` when the value contains `=`. The
reliable pattern is to drop into `cmd /c` or split the flag:

```powershell
cmd /c "venv\Scripts\python.exe tests\ui\run_scenario_matrix.py --pytest-args --junitxml=test-results\x.xml"
```

Or just call pytest directly for the JUnit XML:

```powershell
venv\Scripts\python.exe -m pytest tests\ui\test_scenario_matrix.py --junitxml=test-results\scenario-matrix.xml
```

## What the test asserts

For each scenario the test:

1. Opens `http://localhost:8501`.
2. Switches to the **Configurations** tab and selects the requested Ollama
   model via the hidden BaseWeb combobox inside `[data-testid=stSelectbox]`.
3. Switches back to the **Resume Analyzer** tab.
4. Uploads every resume listed in the scenario via
   `[data-testid=stFileUploader] input[type=file]`.
5. Pastes the JD text into the Streamlit text area and commits it with
   `Ctrl+Enter` (Streamlit only re-runs the script on that keystroke).
6. Waits for the **Candidate Ranking Dashboard** subheader and for the
   Glide data grid to render with the expected number of rows.
7. Reads the top row from the grid (`[data-testid=glide-cell-0-0]` is the
   rank, `-1-0` is the resume name, `-2-0` is the match score).
8. If `expected_min_score` is set, asserts the top score meets it.
9. If `expected_resume` is set, asserts that exact resume is ranked #1.
   Otherwise, if `expected_resumes_any` is set, asserts the top resume is
   in the list.
10. Saves a full-page screenshot to `tests/ui/screenshots/<id>.png`.

## End-to-end run on this machine

```text
tests/ui/test_scenario_matrix.py::test_recruiter_scenario[python_ml_llama32-chromium]      PASSED  [ 33%]
tests/ui/test_scenario_matrix.py::test_recruiter_scenario[data_engineer_llama32-chromium]  PASSED  [ 66%]
tests/ui/test_scenario_matrix.py::test_recruiter_scenario[frontend_react_llama32-chromium] PASSED  [100%]
=================== 3 passed in 65.91s (0:01:05) ===================
```

Screenshots land in `tests/ui/screenshots/`; the JUnit XML in
`test-results/scenario-matrix.xml`.

## CI integration (GitHub Actions)

`.github/workflows/ci.yml` has two jobs driven by the runner:

- **`scenario-matrix`** — runs every scenario on `ubuntu-latest` with the
  Ollama Docker service, uploads the screenshots and the JUnit XML report
  as artifacts.
- **`playwright-smoke`** — a quick filter run that only exercises
  `python_ml_llama32`, useful as a fast feedback loop on PRs.

Both jobs call:

```bash
python tests/ui/run_scenario_matrix.py --config tests/data/scenarios.yaml
```

Add new scenarios to `tests/data/scenarios.yaml` and CI picks them up on
the next push.