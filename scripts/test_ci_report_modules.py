"""Sanity-check the parsers against the real artifact files in this repo."""

import sys
from pathlib import Path

sys.path.insert(0, "scripts")

from ci_report_modules import (
    parse_ai_dashboard,
    parse_coverage,
    parse_coverage_status_json,
    parse_junit,
    parse_log_signals,
    parse_reports_catalog,
    parse_zap_html,
)

REPO = Path.cwd()
PY = REPO / "reports" / "ci" / "backend-python-reports"
assert PY.exists(), "real backend-python-reports must be present"

junit = parse_junit(PY / "junit-python.xml")
print("JUnit :", junit["tests"], "tests /", junit["passed"], "pass /", junit["failures"], "fail",
      "in", junit["duration_seconds"], "s")
assert junit["tests"] == 32 and junit["passed"] == 32 and junit["failures"] == 0, junit

cov = parse_coverage(PY / "coverage-python.xml")
print("Coverage line rate:", cov["line_rate"], "% across", len(cov["files"]), "files")
assert cov["line_rate"] == 48.19, cov["line_rate"]
weakest = [f["file"] for f in cov["weakest"]]
print("Weakest files :", weakest)

status = parse_coverage_status_json(PY / "htmlcov-python" / "status.json")
print("status.json rows:", len(status["files"]))
assert any(r["file"] in {"api_py", "api.py", "append_api_py", "backend_py"} for r in status["files"]), status["files"]

dash = parse_ai_dashboard(PY / "ai-dashboard.json")
print("AI dashboard :", dash["source_files"], "src /", dash["test_modules"], "tests")
assert dash["source_files"] == 15464

logs = parse_log_signals((REPO / "reports" / "ci-logs.txt").read_text(encoding="utf-8", errors="replace"))
print("Log signals :", logs["python_unit_tests"], logs["python_integration_tests"], logs["coverage"])

catalog = parse_reports_catalog(Path("frontend/public/reports.json"))
print("Reports catalog :", catalog["report_count"], "reports across", catalog["categories"])

zap = parse_zap_html(Path("zap-reports/zap-baseline-report.html"))
print("ZAP :", zap["severity"], "high above threshold:", zap["high_above_threshold"])

print("\nALL PARSER ASSERTIONS PASSED")
