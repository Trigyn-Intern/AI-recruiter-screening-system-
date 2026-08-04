"""Parsers for the standard CI outputs.

This module is intentionally additive: ``scripts/fetch_ci.py`` imports it
and uses the helpers to populate ``ArtifactSummary.parsed`` with structured
data so the HTML summary and the JSON sidecar can show real numbers
instead of just file counts and sizes.

Every parser returns a dict. The ``present`` key is the canonical
"did we find anything" flag — ``False`` when the source file is
missing, ``True`` otherwise. When parsing fails, ``present`` is still
``True`` and an ``error`` key carries the exception message.
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path


def safe_xml(path: Path):
    return ET.parse(path).getroot()


def parse_junit(xml_path: Path) -> dict:
    """Pytest JUnit XML -> pass/fail counts, per-suite rows, failing tests."""
    if not xml_path.exists():
        return {"present": False}
    try:
        root = safe_xml(xml_path)
    except (ET.ParseError, ValueError, OSError) as exc:
        return {"present": True, "error": f"Failed to parse: {exc}"}

    suites = root.findall(".//testsuite") or [root]
    tests = failures = errors = skipped = duration = 0
    suite_rows: list = []
    failed_cases: list = []
    slow_cases: list = []

    for suite in suites:
        try:
            tests += int(suite.get("tests", "0"))
            failures += int(suite.get("failures", "0"))
            errors += int(suite.get("errors", "0"))
            skipped += int(suite.get("skipped", "0"))
            duration += float(suite.get("time", "0") or 0)
        except ValueError:
            pass
        suite_rows.append({
            "name": suite.get("name", ""),
            "tests": int(suite.get("tests", "0") or 0),
            "failures": int(suite.get("failures", "0") or 0),
            "errors": int(suite.get("errors", "0") or 0),
            "skipped": int(suite.get("skipped", "0") or 0),
            "duration": float(suite.get("time", "0") or 0),
            "timestamp": suite.get("timestamp", ""),
        })
        for case in suite.findall("testcase"):
            case_time = float(case.get("time", "0") or 0)
            fail_node = case.find("failure") or case.find("error")
            if fail_node is not None:
                failed_cases.append({
                    "name": case.get("name", ""),
                    "classname": case.get("classname", ""),
                    "duration": case_time,
                    "message": (fail_node.get("message") or "")[:240],
                })
            if case_time > 0.5:
                slow_cases.append({
                    "name": case.get("name", ""),
                    "classname": case.get("classname", ""),
                    "duration": case_time,
                })

    passed = max(tests - failures - errors - skipped, 0)
    slow_cases.sort(key=lambda c: -c["duration"])
    failed_cases.sort(key=lambda c: c["classname"])

    return {
        "present": True,
        "tests": tests,
        "passed": passed,
        "failures": failures,
        "errors": errors,
        "skipped": skipped,
        "duration_seconds": round(duration, 3),
        "pass_rate": round((passed / tests) * 100, 1) if tests else 0.0,
        "suites": suite_rows[:25],
        "failed_cases": failed_cases[:25],
        "slow_cases": slow_cases[:10],
        "path": str(xml_path).replace("\\", "/"),
    }


def parse_coverage(xml_path: Path) -> dict:
    """Coverage.py XML -> overall + per-file line/branch rates."""
    if not xml_path.exists():
        return {"present": False}
    try:
        root = safe_xml(xml_path)
    except (ET.ParseError, ValueError, OSError) as exc:
        return {"present": True, "error": f"Failed to parse: {exc}"}

    line_rate = float(root.get("line-rate", "0") or 0)
    branch_rate = float(root.get("branch-rate", "0") or 0)
    files: list = []
    for cls in root.iter("class"):
        filename = cls.get("filename", "")
        lines = cls.findall(".//line")
        files.append({
            "file": filename,
            "line_rate": float(cls.get("line-rate", "0") or 0),
            "branch_rate": float(cls.get("branch-rate", "0") or 0),
            "lines": len(lines),
            "missing": sum(1 for line in lines if line.get("hits") == "0"),
        })
    files.sort(key=lambda f: f["line_rate"])
    weakest = [{"file": f["file"], "line_rate": round(f["line_rate"] * 100, 1)} for f in files[:5]]
    return {
        "present": True,
        "line_rate": round(line_rate * 100, 2),
        "branch_rate": round(branch_rate * 100, 2),
        "files": files,
        "weakest": weakest,
        "path": str(xml_path).replace("\\", "/"),
    }


def parse_coverage_status_json(json_path: Path) -> dict:
    """coverage.py status.json -> per-file statements/covered/missing."""
    if not json_path.exists():
        return {"present": False}
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return {"present": True, "error": f"Failed to parse: {exc}"}

    rows: list = []
    for name, info in (payload.get("files") or {}).items():
        nums = info.get("nums", {}) if isinstance(info, dict) else {}
        statements = int(nums.get("n_statements", 0))
        missing = int(nums.get("n_missing", 0))
        excluded = int(nums.get("n_excluded", 0))
        covered = max(statements - missing, 0)
        rate = (covered / statements) if statements else 0
        rows.append({
            "file": nums.get("file", name),
            "statements": statements,
            "covered": covered,
            "missing": missing,
            "excluded": excluded,
            "line_rate": round(rate * 100, 1),
        })
    rows.sort(key=lambda r: r["line_rate"])
    weakest = [{"file": r["file"], "line_rate": r["line_rate"]} for r in rows[:5]]
    return {"present": True, "files": rows, "weakest": weakest}


def parse_zap_html(html_path: Path) -> dict:
    """OWASP ZAP baseline HTML -> severity counts."""
    if not html_path.exists():
        return {"present": False}
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"present": True, "error": str(exc)}

    counts = {"High": 0, "Medium": 0, "Low": 0, "Informational": 0}
    for severity in counts:
        match = re.search(
            rf"<td[^>]*>{severity}</td>\s*<td[^>]*>\s*(\d+)\s*</td>",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            counts[severity] = int(match.group(1))
    return {
        "present": True,
        "severity": counts,
        "high_above_threshold": counts["High"] > 0,
        "path": str(html_path).replace("\\", "/"),
    }


def parse_dependency_check_html(html_path: Path) -> dict:
    """OWASP dependency-check HTML -> vulnerability counts per severity."""
    if not html_path.exists():
        return {"present": False}
    try:
        text = html_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"present": True, "error": str(exc)}

    counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for severity in counts:
        match = re.search(
            rf"<td[^>]*>\s*{severity}\s*</td>\s*<td[^>]*>\s*(\d+)\s*</td>",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            counts[severity] = int(match.group(1))
    return {
        "present": True,
        "severity": counts,
        "fails_threshold": counts["Critical"] + counts["High"] > 0,
        "path": str(html_path).replace("\\", "/"),
    }


def parse_ai_dashboard(json_path: Path) -> dict:
    """ai-dashboard.json -> file / module counts, post-checks state."""
    if not json_path.exists():
        return {"present": False}
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return {"present": True, "error": f"Failed to parse: {exc}"}

    return {
        "present": True,
        "source_files": payload.get("source_files", 0),
        "test_modules": payload.get("test_modules", 0),
        "oversized_files": payload.get("oversized_files", 0),
        "dependency_manifests": payload.get("dependency_manifests", 0),
        "duration_seconds": payload.get("duration_seconds", 0),
        "codex_status": payload.get("codex_status", "unknown"),
        "post_checks_status": payload.get("post_checks_status", "skipped"),
        "reports": payload.get("reports", []),
        "path": str(json_path).replace("\\", "/"),
    }


def parse_k6(jsonl_path: Path) -> dict:
    """k6 NDJSON -> aggregated counters for http_reqs / duration / failed."""
    if not jsonl_path.exists():
        return {"present": False}
    try:
        lines = jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return {"present": True, "error": str(exc)}

    samples: dict = {}
    for raw in lines:
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if row.get("type") != "Point":
            continue
        data = row.get("data") or {}
        name = data.get("name")
        if not name:
            continue
        samples.setdefault(name, []).append(data.get("value"))

    def _summary(values):
        values = [v for v in values if isinstance(v, (int, float))]
        if not values:
            return {"count": 0}
        values.sort()
        count = len(values)
        return {
            "count": count,
            "min": values[0],
            "max": values[-1],
            "avg": round(sum(values) / count, 3),
            "p50": values[count // 2],
            "p95": values[int(count * 0.95)] if count > 1 else values[-1],
        }

    keys = ["http_reqs", "http_req_duration", "http_req_failed", "vus", "iterations", "checks"]
    return {
        "present": True,
        "metrics": {k: _summary(samples.get(k, [])) for k in keys if k in samples},
        "path": str(jsonl_path).replace("\\", "/"),
    }


def parse_reports_catalog(json_path: Path) -> dict:
    """frontend/public/reports.json bundled in dist-frontend."""
    if not json_path.exists():
        return {"present": False}
    try:
        payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        return {"present": True, "error": f"Failed to parse: {exc}"}

    reports = payload.get("reports") or []
    return {
        "present": True,
        "updated": payload.get("updated", ""),
        "report_count": len(reports),
        "categories": sorted({r.get("category") for r in reports if r.get("category")}),
        "ids": [r.get("id") for r in reports if r.get("id")],
        "path": str(json_path).replace("\\", "/"),
    }


def generate_junit_html(junit_data: dict, out_path: Path, label: str = "Tests"):
    """Generate a premium dark-themed HTML JUnit report."""
    if not junit_data.get("present") or junit_data.get("error"):
        return

    passed = junit_data.get('passed', 0)
    failed = junit_data.get('failures', 0) + junit_data.get('errors', 0)
    skipped = junit_data.get('skipped', 0)
    total = junit_data.get('tests', 0)
    rate = junit_data.get('pass_rate', 0)
    duration = junit_data.get('duration_seconds', 0)
    verdict_color = "#4caf73" if failed == 0 else "#d96b6b"
    verdict_label = "ALL PASSING" if failed == 0 else f"{failed} FAILURE(S)"

    # Build test case rows for ALL tests sorted by suite
    rows_html = []
    for suite in junit_data.get('suites', []):
        suite_name = suite.get('name', '')
        rows_html.append(
            f'<tr class="suite-header"><td colspan="4">{suite_name}</td></tr>'
        )

    # Re-parse testcases from suite data — we need them per-suite
    # Fall back: list failed cases prominently, then all from suites
    failed_cases = junit_data.get('failed_cases', [])
    slow_cases = junit_data.get('slow_cases', [])

    failed_rows = ""
    for c in failed_cases:
        msg = str(c.get('message', '')).replace('<', '&lt;').replace('>', '&gt;')
        failed_rows += (
            f'<tr class="fail-row">'
            f'<td><code>{c.get("classname", "")}</code></td>'
            f'<td>{c.get("name", "")}</td>'
            f'<td><span class="badge fail">FAIL</span></td>'
            f'<td class="msg">{msg}</td>'
            f'</tr>'
        )

    slow_rows = ""
    for c in slow_cases:
        slow_rows += (
            f'<tr>'
            f'<td><code>{c.get("classname", "")}</code></td>'
            f'<td>{c.get("name", "")}</td>'
            f'<td class="dur">{c.get("duration", 0):.3f}s</td>'
            f'</tr>'
        )

    suite_rows = ""
    for s in junit_data.get('suites', []):
        s_pass = max(0, s.get('tests', 0) - s.get('failures', 0) - s.get('errors', 0) - s.get('skipped', 0))
        row_cls = "fail-row" if (s.get('failures', 0) + s.get('errors', 0)) > 0 else ""
        suite_rows += (
            f'<tr class="{row_cls}">'
            f'<td>{s.get("name")}</td>'
            f'<td>{s.get("tests", 0)}</td>'
            f'<td style="color:#4caf73">{s_pass}</td>'
            f'<td style="color:{"#d96b6b" if s.get("failures", 0) else "#9bb1a8"}">{s.get("failures", 0)}</td>'
            f'<td>{s.get("skipped", 0)}</td>'
            f'<td>{s.get("duration", 0):.3f}s</td>'
            f'</tr>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JUnit Report &mdash; {label}</title>
<style>
  :root {{
    --bg: #0f1d18; --panel: #15241f; --border: rgba(255,255,255,0.08);
    --text: #e6efe9; --muted: #9bb1a8; --pass: #4caf73; --fail: #d96b6b;
    --warn: #d9a26b; --code-bg: #0b1310;
  }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.6; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 80px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 28px; }}
  .verdict {{ display: inline-block; padding: 4px 14px; border-radius: 999px;
              font-size: 13px; font-weight: 700; letter-spacing: .06em;
              background: rgba(76,175,115,.15); color: {verdict_color};
              border: 1px solid {verdict_color}44; margin-bottom: 24px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px,1fr));
            gap: 14px; margin-bottom: 32px; }}
  .stat {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
           padding: 16px; text-align: center; }}
  .stat .val {{ font-size: 28px; font-weight: 700; line-height: 1.1; }}
  .stat .lbl {{ color: var(--muted); font-size: 11px; text-transform: uppercase;
                letter-spacing: .08em; margin-top: 4px; }}
  .stat.pass .val {{ color: var(--pass); }}
  .stat.fail .val {{ color: var(--fail); }}
  .stat.skip .val {{ color: var(--warn); }}
  h2 {{ font-size: 15px; margin: 28px 0 10px; color: var(--muted);
        text-transform: uppercase; letter-spacing: .06em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ padding: 8px 12px; text-align: left; color: var(--muted);
              border-bottom: 1px solid var(--border); font-weight: 600; }}
  tbody td {{ padding: 9px 12px; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  .fail-row td {{ background: rgba(217,107,107,.06); }}
  code {{ background: var(--code-bg); padding: 1px 5px; border-radius: 4px;
          font-size: 12px; color: var(--accent, #82b4a7); }}
  .badge {{ display: inline-block; padding: 2px 8px; border-radius: 999px;
            font-size: 11px; font-weight: 700; }}
  .badge.fail {{ background: rgba(217,107,107,.2); color: var(--fail); }}
  .badge.pass {{ background: rgba(76,175,115,.2); color: var(--pass); }}
  .msg {{ color: var(--fail); font-family: monospace; font-size: 12px;
          max-width: 420px; word-break: break-word; }}
  .dur {{ color: var(--warn); }}
  .empty {{ color: var(--muted); font-size: 13px; padding: 20px 0; }}
</style>
</head>
<body>
<main>
  <h1>JUnit Test Report &mdash; {label}</h1>
  <div class="subtitle">Generated by fetch_ci.py &bull; {total} tests &bull; {duration:.2f}s total</div>
  <div class="verdict">{verdict_label}</div>

  <div class="stats">
    <div class="stat"><div class="val">{total}</div><div class="lbl">Total Tests</div></div>
    <div class="stat pass"><div class="val">{passed}</div><div class="lbl">Passed</div></div>
    <div class="stat{'fail' if failed else ''}"><div class="val" style="color:{'var(--fail)' if failed else 'var(--pass)'}">{failed}</div><div class="lbl">Failed</div></div>
    <div class="stat skip"><div class="val">{skipped}</div><div class="lbl">Skipped</div></div>
    <div class="stat"><div class="val">{rate}%</div><div class="lbl">Pass Rate</div></div>
    <div class="stat"><div class="val">{duration:.2f}s</div><div class="lbl">Duration</div></div>
  </div>
"""

    if failed_cases:
        html += f"""
  <h2>&#x26A0; Failed Tests ({len(failed_cases)})</h2>
  <table>
    <thead><tr><th>Module</th><th>Test Name</th><th>Status</th><th>Message</th></tr></thead>
    <tbody>{failed_rows}</tbody>
  </table>
"""
    else:
        html += '<p class="empty" style="margin: 20px 0; color: var(--pass);">&#x2714; All tests passed. No failures.</p>\n'

    html += f"""
  <h2>Test Suites</h2>
  <table>
    <thead><tr><th>Suite</th><th>Tests</th><th>Passed</th><th>Failed</th><th>Skipped</th><th>Duration</th></tr></thead>
    <tbody>{suite_rows if suite_rows else '<tr><td colspan="6" class="empty">No suite data.</td></tr>'}</tbody>
  </table>
"""

    if slow_cases:
        html += f"""
  <h2>&#x1F40C; Slowest Tests (top {len(slow_cases)})</h2>
  <table>
    <thead><tr><th>Module</th><th>Test Name</th><th>Duration</th></tr></thead>
    <tbody>{slow_rows}</tbody>
  </table>
"""

    html += "</main></body></html>"
    out_path.write_text(html, encoding='utf-8', errors='replace')


def generate_coverage_html(coverage_data: dict, out_path: Path, label: str = "Coverage"):
    """Generate a premium dark-themed HTML Coverage report."""
    if not coverage_data.get("present") or coverage_data.get("error"):
        return

    line_rate = coverage_data.get('line_rate', 0) or 0
    branch_rate = coverage_data.get('branch_rate', 0) or 0
    lines_valid = coverage_data.get('lines_valid', 0) or 0
    lines_covered = coverage_data.get('lines_covered', 0) or 0
    weakest = coverage_data.get('weakest', []) or []
    strongest = coverage_data.get('strongest', []) or []

    bar_color = "#4caf73" if line_rate >= 80 else ("#d9a26b" if line_rate >= 50 else "#d96b6b")
    rating = "EXCELLENT" if line_rate >= 90 else ("GOOD" if line_rate >= 70 else ("FAIR" if line_rate >= 50 else "LOW"))

    def file_rows(files, limit=20):
        rows = ""
        for f in files[:limit]:
            r = f.get('line_rate', 0) or 0
            c = "#4caf73" if r >= 80 else ("#d9a26b" if r >= 50 else "#d96b6b")
            rows += (
                f'<tr>'
                f'<td><code>{f.get("file", "")}</code></td>'
                f'<td style="color:{c};font-weight:600">{r}%</td>'
                f'<td>{f.get("lines_valid", "—")}</td>'
                f'<td>{f.get("lines_covered", "—")}</td>'
                f'<td>{f.get("lines_missing", "—")}</td>'
                f'</tr>'
            )
        return rows or '<tr><td colspan="5" style="color:var(--muted)">No file data.</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Coverage Report &mdash; {label}</title>
<style>
  :root {{
    --bg: #0f1d18; --panel: #15241f; --border: rgba(255,255,255,0.08);
    --text: #e6efe9; --muted: #9bb1a8; --pass: #4caf73; --fail: #d96b6b;
    --warn: #d9a26b; --code-bg: #0b1310;
  }}
  * {{ box-sizing: border-box; margin: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.6; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 36px 24px 80px; }}
  h1 {{ font-size: 22px; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 28px; }}
  .big-rate {{ font-size: 72px; font-weight: 800; color: {bar_color};
               line-height: 1; margin: 24px 0 8px; }}
  .rating {{ display: inline-block; padding: 4px 14px; border-radius: 999px;
             font-size: 13px; font-weight: 700; letter-spacing: .06em;
             background: {bar_color}22; color: {bar_color};
             border: 1px solid {bar_color}44; margin-bottom: 28px; }}
  .bar-wrap {{ background: var(--panel); border-radius: 999px; height: 12px;
               margin-bottom: 32px; overflow: hidden; border: 1px solid var(--border); }}
  .bar-fill {{ height: 100%; border-radius: 999px;
               background: linear-gradient(90deg, {bar_color}cc, {bar_color}); width: {line_rate}%; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px,1fr));
            gap: 14px; margin-bottom: 32px; }}
  .stat {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
           padding: 16px; text-align: center; }}
  .stat .val {{ font-size: 24px; font-weight: 700; line-height: 1.1; }}
  .stat .lbl {{ color: var(--muted); font-size: 11px; text-transform: uppercase;
                letter-spacing: .08em; margin-top: 4px; }}
  h2 {{ font-size: 14px; margin: 28px 0 10px; color: var(--muted);
        text-transform: uppercase; letter-spacing: .06em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{ padding: 8px 12px; text-align: left; color: var(--muted);
              border-bottom: 1px solid var(--border); font-weight: 600; }}
  tbody td {{ padding: 9px 12px; border-bottom: 1px solid var(--border); }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  code {{ background: var(--code-bg); padding: 1px 5px; border-radius: 4px;
          font-size: 12px; color: #82b4a7; }}
</style>
</head>
<body>
<main>
  <h1>Coverage Report &mdash; {label}</h1>
  <div class="subtitle">Generated by fetch_ci.py &bull; {lines_covered} / {lines_valid} lines covered</div>
  <div class="big-rate">{line_rate}%</div>
  <div class="rating">{rating} COVERAGE</div>
  <div class="bar-wrap"><div class="bar-fill"></div></div>

  <div class="stats">
    <div class="stat"><div class="val">{line_rate}%</div><div class="lbl">Line Coverage</div></div>
    <div class="stat"><div class="val">{branch_rate}%</div><div class="lbl">Branch Coverage</div></div>
    <div class="stat"><div class="val">{lines_valid}</div><div class="lbl">Total Lines</div></div>
    <div class="stat"><div class="val">{lines_covered}</div><div class="lbl">Covered</div></div>
    <div class="stat"><div class="val">{lines_valid - lines_covered}</div><div class="lbl">Missing</div></div>
  </div>
"""

    if weakest:
        html += f"""
  <h2>&#x1F7E5; Files Needing Attention (lowest coverage)</h2>
  <table>
    <thead><tr><th>File</th><th>Coverage</th><th>Total Lines</th><th>Covered</th><th>Missing</th></tr></thead>
    <tbody>{file_rows(weakest)}</tbody>
  </table>
"""

    if strongest:
        html += f"""
  <h2>&#x2728; Well-Covered Files (highest coverage)</h2>
  <table>
    <thead><tr><th>File</th><th>Coverage</th><th>Total Lines</th><th>Covered</th><th>Missing</th></tr></thead>
    <tbody>{file_rows(strongest)}</tbody>
  </table>
"""

    html += "</main></body></html>"
    out_path.write_text(html, encoding='utf-8', errors='replace')


def parse_log_signals(text: str) -> dict:
    """Aggregate the .txt logs for the numbers a manager wants in the header strip."""

    def _first(pattern: str, group: int = 1, cast=float):
        match = re.search(pattern, text)
        if not match:
            return None
        try:
            return cast(match.group(group))
        except (TypeError, ValueError):
            return None

    return {
        "python_unit_tests": {
            "passed": _first(r"(\d+) passed(?:, 3 warnings)?", 1, int),
            "duration_seconds": _first(r"(\d+\.\d+)s.*passed", 1, float),
        },
        "python_integration_tests": {
            "passed": _first(r"(\d+) passed, \d+ deselected", 1, int),
            "deselected": _first(r"\d+ passed, (\d+) deselected", 1, int),
            "duration_seconds": _first(r"deselected.*in (\d+\.\d+)s", 1, float),
        },
        "coverage": {
            "rate": _first(r"Total coverage: (\d+(?:\.\d+)?)%", 1, float),
            "required": _first(r"Required test coverage of (\d+)% reached", 1, int),
        },
        "ruff_or_lint_ok": "All checks passed!" in text,
        "frontend_jobs": re.findall(r"Complete job name: ([^\n]+)", text),
    }


def enrich_artifact(artifact, root: Path) -> None:
    """Fill ``artifact.parsed`` with everything we can extract from ``root``."""
    parsed: dict = {}

    if artifact.name == "backend-python-reports":
        parsed["junit"] = parse_junit(root / "junit-python.xml")
        generate_junit_html(parsed["junit"], root / "junit-python.html", label="Python (pytest)")
        parsed["coverage"] = parse_coverage(root / "coverage-python.xml")
        generate_coverage_html(parsed["coverage"], root / "coverage-python.html", label="Python")
        parsed["status"] = parse_coverage_status_json(root / "htmlcov-python" / "status.json")
        parsed["ai_dashboard"] = parse_ai_dashboard(root / "ai-dashboard.json")

    if artifact.name == "backend-node-reports":
        parsed["junit"] = parse_junit(root / "junit-node.xml")
        if parsed["junit"].get("present"):
            generate_junit_html(parsed["junit"], root / "junit-node.html", label="Node (Jest)")
        # Try to parse coverage summary from jest's coverage-summary.json
        cov_summary = root / "coverage-node" / "coverage-summary.json"
        if cov_summary.exists():
            try:
                cov_data = json.loads(cov_summary.read_text(encoding="utf-8"))
                total = cov_data.get("total", {})
                parsed["coverage"] = {
                    "present": True,
                    "line_rate": round(total.get("lines", {}).get("pct", 0), 1),
                    "branch_rate": round(total.get("branches", {}).get("pct", 0), 1),
                    "lines_valid": total.get("lines", {}).get("total", 0),
                    "lines_covered": total.get("lines", {}).get("covered", 0),
                    "weakest": [],
                    "strongest": [],
                }
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                parsed["coverage"] = {"present": False}
        # Also read audit log for any security issues
        audit_log = root / "audit-node.log"
        if audit_log.exists():
            audit_text = audit_log.read_text(encoding="utf-8", errors="replace")
            vulns = re.findall(r"(\d+) (critical|high|moderate|low) severity", audit_text, re.IGNORECASE)
            parsed["node_audit"] = {"present": True, "findings": vulns}

    if artifact.name in ("frontend-reports", "frontend-test-reports"):
        app_name = "frontend-test" if "test" in artifact.name else "frontend"
        junit_path = root / f"junit-{app_name}.xml"
        parsed["junit"] = parse_junit(junit_path)
        if parsed["junit"].get("present"):
            generate_junit_html(parsed["junit"], root / f"junit-{app_name}.html",
                                label=f"{app_name.replace('-', ' ').title()} (Jest)")
        cov_summary = root / f"coverage-{app_name}" / "coverage-summary.json"
        if cov_summary.exists():
            try:
                cov_data = json.loads(cov_summary.read_text(encoding="utf-8"))
                total = cov_data.get("total", {})
                parsed["coverage"] = {
                    "present": True,
                    "line_rate": round(total.get("lines", {}).get("pct", 0), 1),
                    "branch_rate": round(total.get("branches", {}).get("pct", 0), 1),
                    "lines_valid": total.get("lines", {}).get("total", 0),
                    "lines_covered": total.get("lines", {}).get("covered", 0),
                    "weakest": [],
                    "strongest": [],
                }
                if parsed["coverage"].get("present"):
                    generate_coverage_html(parsed["coverage"], root / f"coverage-{app_name}.html",
                                           label=app_name.replace('-', ' ').title())
            except (json.JSONDecodeError, KeyError, ValueError, OSError):
                parsed["coverage"] = {"present": False}

    if artifact.name == "dist-frontend":
        parsed["catalog"] = parse_reports_catalog(root / "reports.json")

    if artifact.name == "dist-frontend-test":
        index_html = root / "index.html"
        parsed["index_size_bytes"] = index_html.stat().st_size if index_html.exists() else 0

    if artifact.name == "dependency-check-report":
        parsed["vulnerabilities"] = parse_dependency_check_html(root / "dependency-check-report.html")

    k6_path = Path("reports/k6-results.json")
    if k6_path.exists():
        parsed["k6"] = parse_k6(k6_path)

    for target in ("zap-baseline-report.html", "zap-baseline-report-auth.html"):
        zap_path = Path("reports/zap") / target
        if zap_path.exists():
            parsed.setdefault("zap", {})[target] = parse_zap_html(zap_path)

    artifact.parsed = parsed
