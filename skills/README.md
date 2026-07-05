# Skills

LLM-driven skills for the AI Recruiter Screening System. Each skill is a markdown manifest the model reads at runtime. There is no CLI, no runner, no registry, no Docker image. The "execution" is the model doing the reasoning (or, in the case of scenario-runner, emitting a runnable block the user pastes into a terminal).

## security-review

`skills/security-review/SKILL.md` covers five security areas:

- `auth-review` - Express authentication and authorization
- `llm-prompt-safety` - prompt injection and unsafe LLM usage
- `secrets-hygiene` - committed secrets and weak secret config (safe mode)
- `frontend-input` - React/Vite input handling and dependency pinning
- `test-data-pii` - PII in test fixtures (safe mode)

### Invoking

- `run security-review` - runs all five reviews
- `run security-review mode=auth-review` - runs only the auth review
- `run security-review mode=secrets-hygiene` - runs only the secrets review in safe mode

### Output

Two artifacts per run:

1. **Chat findings** - inline in the conversation.
2. **Structured HTML report** - written to `skills/reports/security-review-<mode>-<date>.html`, with `skills/reports/index.html` regenerated each run.

Safe-mode runs (secrets-hygiene, test-data-pii) use redacted input data in the HTML.

## scenario-runner

`skills/scenario-runner/SKILL.md` boots the full local stack (Ollama, FastAPI, Express auth, React frontend) and runs the Playwright scenario matrix from `tests/data/scenarios.yaml`.

### Canonical entry point

```powershell
pwsh tests/run.ps1
pwsh tests/run.ps1 -Filter python_ml_llama32
pwsh tests/run.ps1 -Filter "python_ml_llama32,frontend_react_llama32" -OpenReport
```

`tests/run.ps1` is a thin wrapper around `tests/ui/run_scenario_matrix.py`. The Python runner now has four new flags on top of the original CLI:

- `--report-dir DIR` - write the structured HTML report to this folder.
- `--junit PATH` - write the raw JUnit JSON to a specific path (overrides the default location under `--report-dir`).
- `--open-report` - open the rendered HTML in the default browser when done.
- `--skills-dir DIR` - path to the `skills/` folder (defaults to `<repo>/skills`).

### Output

Three things land in `skills/reports/scenario-report/` per run:

- `junit-<timestamp>.json` - raw pytest JUnit JSON.
- `scenario-report-<timestamp>.html` - the structured HTML report.
- `logs/` - per-service logs (`api.log`, `web.log`, `auth.log`) and captured pytest output.

`skills/reports/scenario-report/index.html` is regenerated each run and lists all runs newest-first.

### Invoking from chat

- `run scenario-runner` - emits a `pwsh tests/run.ps1` block (or the verbose form, on request).
- `run scenario-runner mode=python_ml_llama32` - same with `-Filter python_ml_llama32`.
- `run scenario-runner --filter frontend_react_llama32` - alias for mode.

The skill is portable; `tests/run.ps1` is a real, standalone PowerShell entry point that does not depend on the LLM at all. The chat invocation is a convenience.

## Verify before acting

Findings from these skills are hints to investigate, not verified vulnerabilities or pass/fail verdicts. Always read the cited code or test output, confirm the issue exists, and test the suggested fix before merging.

## Opening reports

PowerShell:
```powershell
Start-Process .\skills\reports\index.html
```

bash / Git Bash:
```bash
open skills/reports/index.html
xdg-open skills/reports/index.html
```
