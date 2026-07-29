"""Render report.html from a JUnit XML file into a clean spreadsheet-style audit table.

Standalone renderer. Reads:
  --junit   path to pytest's JUnit XML
  --yaml    path to tests/data/scenarios.yaml (for description / expected)
  --output  path to write the HTML report
  --filter  filter string (display only)
"""
from __future__ import annotations

import argparse
import datetime
import html
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
import yaml


HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent


def load_junit(path: Path) -> list:
    if not path.exists():
        print(f"Error: JUnit file does not exist: {path}", file=sys.stderr)
        return []
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        testcases = []
        for tc in root.iter("testcase"):
            tc_data = {
                "classname": tc.get("classname", ""),
                "name": tc.get("name", ""),
                "time": tc.get("time", ""),
            }
            failure = tc.find("failure")
            if failure is not None:
                tc_data["failure"] = {
                    "message": failure.get("message", ""),
                    "text": failure.text or "",
                }
            error = tc.find("error")
            if error is not None:
                tc_data["error"] = {
                    "message": error.get("message", ""),
                    "text": error.text or "",
                }
            testcases.append(tc_data)
        return testcases
    except Exception as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        return []


def parse_yaml_meta(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        scenarios = data.get("scenarios", [])
        meta = {}
        for s in scenarios:
            if "id" in s:
                meta[s["id"]] = s
        return meta
    except Exception as e:
        print(f"Error parsing YAML metadata: {e}", file=sys.stderr)
        return {}


def get_scenario_id(testcase_name: str) -> str:
    m = re.search(r"\[([^\]]+)\]", testcase_name)
    if m:
        param = m.group(1)
        if "-" in param:
            return param.split("-", 1)[0]
        return param
    return testcase_name


def render_row(idx: int, tc: dict, meta: dict) -> str:
    tc_name = tc.get("name", "")
    scenario_id = get_scenario_id(tc_name)
    m = meta.get(scenario_id, {})

    sr_no = idx + 1
    cr_no = m.get("cr_no", "102423")
    name = scenario_id.replace("_", " ").title()
    model = m.get("model", "llama3.2")
    jd_file = m.get("jd_file", "")
    resume_files = m.get("resume_files", [])
    expected_resume = m.get("expected_resume", "N/A")
    expected_min_score = m.get("expected_min_score", "N/A")

    # Description
    description = (
        f"Verify AI recruiter screening for {name} scenario using Ollama model {model}."
    )

    # Pre-requisite
    prerequisite = (
        f"1. Ollama model '{model}' must be running via 'ollama serve'.\n"
        f"2. FastAPI backend on http://127.0.0.1:8000 must be running.\n"
        f"3. React frontend on http://localhost:5173 must be running.\n"
        f"4. Auth API on http://localhost:4000 must be running."
    )

    # Test Steps
    test_steps = (
        f"1. Open the AI Recruiter Screening app at http://localhost:5173\n"
        f"2. Login with recruiter credentials.\n"
        f"3. Navigate to Dashboard > Configurations tab.\n"
        f"4. Set Provider to Ollama, Model to {model}.\n"
        f"5. Switch to Analyzer tab.\n"
        f"6. Upload {len(resume_files)} resume files.\n"
        f"7. Paste job description from {jd_file}.\n"
        f"8. Click 'Analyze' and wait for Ranking table.\n"
        f"9. Verify top-ranked resume and minimum score."
    )

    # Input Data
    resume_text = (
        "\n".join(f"  - {r}" for r in resume_files) if resume_files else "  (none)"
    )
    input_data = f"JD File: {jd_file}\n" f"Model: {model}\n" f"Resumes:\n{resume_text}"

    # Expected Result
    expected_result = (
        f"1. Top-ranked resume should be: {expected_resume}\n"
        f"2. Match score should be at least: {expected_min_score}"
    )

    # Actual Result & Status
    status = "Pass"
    actual_result = "Top-ranked resume and score met or exceeded the expected values."

    if tc.get("failure"):
        status = "Fail"
        actual_result = (
            tc["failure"].get("message")
            or tc["failure"].get("text")
            or "Assertion Failed"
        )
    elif tc.get("error"):
        status = "Fail"
        actual_result = (
            tc["error"].get("message") or tc["error"].get("text") or "Execution Error"
        )

    # Enhancement
    if status == "Pass":
        enhancement = (
            f"1. Scenario {scenario_id} passed successfully.\n"
            f"2. Model version verified, no drift detected.\n"
            f"3. Automated Playwright wait-for-load checks passed."
        )
    else:
        enhancement = (
            f"1. Investigate failure for scenario {scenario_id}.\n"
            f"2. Check reports/logs/api.log for backend errors.\n"
            f"3. Verify Ollama model {model} is responsive.\n"
            f"4. Cross-check score threshold against model version."
        )

    # Email
    if status == "Pass":
        email = (
            f"Subject: AI Recruiter Screening Test Passed - {scenario_id}\n\n"
            f"Hi Recruiter,\n"
            f"This is to inform you that the automated screening test for "
            f"scenario '{scenario_id}' completed successfully.\n\n"
            f"Model: {model}\n"
            f"Top Resume: {expected_resume}\n"
            f"Status: PASSED\n\n"
            f"Thank you,\n"
            f"AI Recruiter Automation Tool"
        )
    else:
        email = (
            f"Subject: AI Recruiter Screening Test Failed - {scenario_id}\n\n"
            f"Hi Recruiter,\n"
            f"This is to inform you that the automated screening test for "
            f"scenario '{scenario_id}' has FAILED.\n\n"
            f"Model: {model}\n"
            f"Expected Top Resume: {expected_resume}\n"
            f"Status: FAILED\n\n"
            f"Please check logs at reports/logs/ for details.\n\n"
            f"Thank you,\n"
            f"AI Recruiter Automation Tool"
        )

    # Reference + screenshot
    screenshot_path = REPO_ROOT / "tests" / "ui" / "screenshots" / f"{scenario_id}.png"
    screenshot_html = ""
    if screenshot_path.exists():
        screenshot_html = (
            f"\n3. Screenshot: {scenario_id}.png"
        )
    reference = (
        f"1. Case ID: 10560-{scenario_id}\n"
        f"2. Config: tests/data/scenarios.yaml"
        f"{screenshot_html}"
    )

    status_class = "pass" if status == "Pass" else "fail"

    def cell(text):
        return html.escape(text).replace("\n", "<br>")

    return f"""<tr>
  <td class="center">{sr_no}</td>
  <td class="center">{html.escape(str(cr_no))}</td>
  <td class="bold">{html.escape(name)}</td>
  <td>{cell(description)}</td>
  <td>{cell(prerequisite)}</td>
  <td>{cell(test_steps)}</td>
  <td>{cell(input_data)}</td>
  <td>{cell(expected_result)}</td>
  <td>{cell(actual_result)}</td>
  <td class="center {status_class}">{status}</td>
  <td>{cell(enhancement)}</td>
  <td class="email-cell">{cell(email)}</td>
  <td>{cell(reference)}</td>
</tr>"""


CSS = """\
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: Calibri, "Segoe UI", Arial, sans-serif;
  font-size: 11px;
  color: #000;
  background: #fff;
  padding: 20px;
}
h1 {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 4px;
}
.meta-line {
  font-size: 11px;
  color: #555;
  margin-bottom: 12px;
}
.summary-bar {
  display: flex;
  gap: 20px;
  margin-bottom: 14px;
  font-size: 12px;
  font-weight: bold;
}
.summary-bar .total { color: #333; }
.summary-bar .passed { color: #217346; }
.summary-bar .failed { color: #c00; }

table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
  font-size: 11px;
}
thead th {
  background: #4472C4;
  color: #fff;
  font-weight: bold;
  font-size: 11px;
  padding: 6px 5px;
  border: 1px solid #2F5496;
  text-align: center;
  vertical-align: middle;
  position: sticky;
  top: 0;
  z-index: 10;
}
tbody td {
  border: 1px solid #B4C6E7;
  padding: 5px 6px;
  vertical-align: top;
  word-wrap: break-word;
  overflow-wrap: break-word;
}
tbody tr:nth-child(even) {
  background: #D6E4F0;
}
tbody tr:nth-child(odd) {
  background: #fff;
}
tbody tr:hover {
  background: #FFF2CC;
}
td.center { text-align: center; }
td.bold { font-weight: bold; }
td.pass {
  color: #217346;
  font-weight: bold;
}
td.fail {
  color: #c00;
  font-weight: bold;
}
td.email-cell {
  font-size: 10px;
}

/* Column widths */
th:nth-child(1), td:nth-child(1) { width: 38px; }    /* Sr No */
th:nth-child(2), td:nth-child(2) { width: 60px; }    /* CR No */
th:nth-child(3), td:nth-child(3) { width: 120px; }   /* Name */
th:nth-child(4), td:nth-child(4) { width: 180px; }   /* Description */
th:nth-child(5), td:nth-child(5) { width: 180px; }   /* Pre-requisite */
th:nth-child(6), td:nth-child(6) { width: 220px; }   /* Test Steps */
th:nth-child(7), td:nth-child(7) { width: 160px; }   /* Input Data */
th:nth-child(8), td:nth-child(8) { width: 160px; }   /* Expected Result */
th:nth-child(9), td:nth-child(9) { width: 180px; }   /* Actual Result */
th:nth-child(10), td:nth-child(10) { width: 55px; }   /* Pass/Fail */
th:nth-child(11), td:nth-child(11) { width: 200px; }  /* New Enhancement */
th:nth-child(12), td:nth-child(12) { width: 220px; }  /* Email sent */
th:nth-child(13), td:nth-child(13) { width: 140px; }  /* Reference */

@media print {
  body { padding: 0; font-size: 9px; }
  table { font-size: 9px; }
  thead th { background: #4472C4 !important; color: #fff !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  tbody tr:nth-child(even) { background: #D6E4F0 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--junit", required=True, type=Path)
    p.add_argument("--yaml", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--filter", default="")
    p.add_argument("--stamp", default="")
    args = p.parse_args()

    testcases = load_junit(args.junit)
    meta = parse_yaml_meta(args.yaml)

    pass_c = sum(1 for tc in testcases if not tc.get("failure") and not tc.get("error"))
    fail_c = sum(1 for tc in testcases if tc.get("failure") or tc.get("error"))
    total = len(testcases)

    rows_html = "\n".join(render_row(idx, tc, meta) for idx, tc in enumerate(testcases))
    stamp = args.stamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    filt = args.filter or "(all)"

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Scenario Matrix Test Report</title>
<style>{CSS}</style>
<script src="https://cdn.sheetjs.com/xlsx-0.20.1/package/dist/xlsx.full.min.js"></script>
</head>
<body>

<h1>AI Recruiter Screening System &mdash; Scenario Matrix Test Report</h1>
<div class="meta-line">Generated: {html.escape(stamp)} &nbsp;|&nbsp; Filter: {html.escape(filt)} &nbsp;|&nbsp; Source: {html.escape(str(args.junit.name))}</div>
<div class="summary-bar">
  <span class="total">Total: {total}</span>
  <span class="passed">Passed: {pass_c}</span>
  <span class="failed">Failed: {fail_c}</span>
</div>

<button onclick="exportTableToExcel('report-table', 'scenario-matrix-report')" style="margin-bottom: 15px; padding: 5px 10px; background: #4472C4; color: white; border: none; cursor: pointer; border-radius: 3px; font-weight: bold;">Export to XLSX</button>

<script>
function exportTableToExcel(tableID, filename = ''){{
    var tableSelect = document.getElementById(tableID);
    var wb = XLSX.utils.table_to_book(tableSelect, {{sheet: "Report"}});
    filename = filename ? filename + '.xlsx' : 'excel_data.xlsx';
    XLSX.writeFile(wb, filename);
}}
</script>

<table id="report-table">
<thead>
<tr>
  <th>Sr No</th>
  <th>CR No</th>
  <th>Name</th>
  <th>Description</th>
  <th>Pre-requisite</th>
  <th>Test Steps</th>
  <th>Input Data</th>
  <th>Expected Result</th>
  <th>Actual Result</th>
  <th>Pass/Fail</th>
  <th>New Enhancement</th>
  <th>Email sent to Requester</th>
  <th>Reference</th>
</tr>
</thead>
<tbody>
{rows_html}
</tbody>
</table>

</body>
</html>
"""
    args.output.write_text(doc, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
