"""Render a 13-column Security Review HTML report from JSON input."""
from __future__ import annotations

import argparse
import datetime
import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=False)


def _status_class(pass_fail: str) -> str:
    val = (pass_fail or "").strip().lower()
    if val in ("pass", "passed", "ok", "yes"):
        return "pass"
    if val in ("warning", "warn"):
        return "warning"
    return "fail"


def _row_from_finding(idx: int, item: Dict[str, Any]) -> str:
    pf = item.get("pass_fail") or item.get("status") or item.get("passFail") or "Fail"
    cls = _status_class(str(pf))
    steps = _esc(item.get("test_steps", "")).replace("\n", "<br>")
    return (
        "<tr>"
        f'<td class="center">{idx}</td>'
        f'<td class="center">{_esc(item.get("cr_no", f"SR-{idx:03d}"))}</td>'
        f'<td class="bold">{_esc(item.get("name", item.get("checkItem", "")))}</td>'
        f"<td>{_esc(item.get('description', ''))}</td>"
        f"<td>{_esc(item.get('prerequisite', item.get('pre_requisite', '')))}</td>"
        f"<td>{steps}</td>"
        f"<td><pre>{_esc(item.get('input_data', ''))}</pre></td>"
        f"<td>{_esc(item.get('expected_result', ''))}</td>"
        f"<td>{_esc(item.get('actual_result', ''))}</td>"
        f'<td class="center {cls}">{_esc(pf)}</td>'
        f"<td>{_esc(item.get('enhancement', item.get('new_enhancement', '')))}</td>"
        f'<td class="email-cell">{_esc(item.get("codex_prompt", ""))}</td>'
        f"<td>{_esc(item.get('reference', ''))}</td>"
        "</tr>"
    )


def _findings_from_data(data: dict) -> List[dict]:
    findings = data.get("findings")
    if isinstance(findings, list) and findings:
        return findings

    rows: List[dict] = []
    for idx, check in enumerate(data.get("securityChecks") or [], start=1):
        status = check.get("status", "Fail")
        rows.append({
            "cr_no": f"SR-{idx:03d}",
            "name": check.get("checkItem", "Security check"),
            "description": check.get("checkItem", ""),
            "prerequisite": "Changed files in git diff against main",
            "test_steps": "Reviewed diff with security-review SKILL.md",
            "input_data": "",
            "expected_result": "No vulnerability",
            "actual_result": check.get("comments", check.get("notes", "")),
            "pass_fail": status,
            "enhancement": check.get("comments", ""),
            "codex_prompt": "",
            "reference": "",
        })
    if not rows and data.get("finalNotes"):
        rows.append({
            "cr_no": "SR-001",
            "name": "security-review / summary",
            "description": "LLM security review summary",
            "prerequisite": "Git diff main..HEAD",
            "test_steps": "Automated background security review",
            "input_data": "",
            "expected_result": "Structured findings",
            "actual_result": str(data.get("finalNotes", ""))[:500],
            "pass_fail": "Warning",
            "enhancement": "See full notes in job output",
            "codex_prompt": "",
            "reference": "",
        })
    return rows


def build_findings_html(data: dict) -> tuple[str, int, int, int]:
    findings = _findings_from_data(data)
    pass_count = fail_count = warn_count = 0
    rows: List[str] = []
    for idx, item in enumerate(findings, start=1):
        cls = _status_class(str(item.get("pass_fail") or item.get("status") or ""))
        if cls == "pass":
            pass_count += 1
        elif cls == "warning":
            warn_count += 1
        else:
            fail_count += 1
        rows.append(_row_from_finding(idx, item))
    if not rows:
        rows.append(
            '<tr><td class="center">1</td><td class="center">SR-000</td>'
            '<td class="bold">No findings</td><td colspan="10">No security findings in JSON.</td>'
            "<td>—</td></tr>"
        )
    return "\n".join(rows), pass_count, fail_count, warn_count


def _module_summary_html(modules: dict) -> str:
    if not modules:
        return ""
    rows = "".join(
        "<tr><td>" + _esc(str(name)) + "</td>"
        + "<td>" + str(p.get("Pass", 0)) + "</td>"
        + "<td>" + str(p.get("Fail", 0)) + "</td>"
        + "<td>" + str(p.get("Warning", 0)) + "</td>"
        + "<td>" + str(p.get("Total", 0)) + "</td></tr>"
        for name, p in modules.items()
    )
    return (
        "<h3>Module Summary</h3>"
        '<table border="1" cellpadding="6" style="border-collapse:collapse;width:100%;">'
        "<thead><tr><th>Module</th><th>Pass</th><th>Fail</th><th>Warning</th><th>Total</th></tr></thead>"
        "<tbody>" + rows + "</tbody></table>"
    )


def _modules_bullet_html(modules: dict) -> str:
    if not modules:
        return "<p>(no modules)</p>"
    items = "".join(
        "<li><b>" + _esc(str(name)) + "</b>: "
        + str(p.get("Total", 0)) + " checks ("
        + str(p.get("Pass", 0)) + " pass, "
        + str(p.get("Fail", 0)) + " fail, "
        + str(p.get("Warning", 0)) + " warn)</li>"
        for name, p in modules.items()
    )
    return "<ul>" + items + "</ul>"


def render_report(data: dict, mode: str, stamp: str, scope: str, template_path: Path) -> str:
    date_part = stamp.split(" ")[0] if " " in stamp else stamp[:10]
    findings_html, pass_count, fail_count, warn_count = build_findings_html(data)

    boxes = data.get("summaryBoxes") or {}
    if boxes:
        pass_count = boxes.get("pass", pass_count)
        fail_count = boxes.get("fail", fail_count)
        warn_count = boxes.get("warn", warn_count)
        module_count = boxes.get("modules", 0)
    else:
        module_count = len(data.get("modules") or data.get("findings") or [])

    exec_summary = data.get("executiveSummary") or data.get("overallPosture") or ""
    posture = data.get("overallPosture") or data.get("overallSecurityPosture") or ""
    verdict = data.get("overallVerdict") or data.get("finalSecurityVerdict") or ""
    next_action = data.get("nextAction") or data.get("finalRecommendation") or ""
    modules = data.get("modules") or {}

    coverage_rows = {
        "__AUTH_STATUS__": data.get("coverage", {}).get("Authentication", ""),
        "__AUTHZ_STATUS__": data.get("coverage", {}).get("Authorization", ""),
        "__INPUT_STATUS__": data.get("coverage", {}).get("Input Validation", ""),
        "__SECRET_STATUS__": data.get("coverage", {}).get("Secrets Management", ""),
        "__DEPENDENCY_STATUS__": data.get("coverage", {}).get("Dependency Security", ""),
        "__CONFIG_STATUS__": data.get("coverage", {}).get("Configuration Review", ""),
        "__LOGGING_STATUS__": data.get("coverage", {}).get("Logging", ""),
        "__ERROR_STATUS__": data.get("coverage", {}).get("Error Handling", ""),
        "__FRONTEND_STATUS__": data.get("coverage", {}).get("Frontend Security", ""),
        "__BACKEND_STATUS__": data.get("coverage", {}).get("Backend Security", ""),
        "__PYTHON_STATUS__": data.get("coverage", {}).get("Python / AI Security", ""),
        "__GITHUB_STATUS__": data.get("coverage", {}).get("GitHub Actions", ""),
        "__DOCKER_STATUS__": data.get("coverage", {}).get("Docker / Infrastructure", ""),
        "__TEST_STATUS__": data.get("coverage", {}).get("Tests & Test Data", ""),
    }

    risks = data.get("riskDistribution") or []
    if risks:
        risk_text = "\n".join(
            "- " + _esc(str(r.get("Severity", ""))) + ": " + _esc(str(r.get("Recommendation", "")))
            for r in risks
        )
    else:
        risk_text = str(data.get("finalRecommendation", ""))

    module_block = _module_summary_html(modules)
    modules_bullet = _modules_bullet_html(modules)

    template = template_path.read_text(encoding="utf-8")
    replacements = {
        "__MODE__": _esc(mode),
        "__DATE__": _esc(date_part),
        "__TIMESTAMP__": _esc(stamp),
        "__SCOPE__": _esc(scope),
        "__PASS_COUNT__": str(pass_count),
        "__FAIL_COUNT__": str(fail_count),
        "__WARNING_COUNT__": str(warn_count),
        "__MODULE_COUNT__": str(module_count),
        "__FINDINGS__": findings_html,
        "__EXECUTIVE_SUMMARY__": str(exec_summary),
        "__SECURITY_POSTURE__": str(posture),
        "__VERDICT__": str(verdict),
        "__NEXT_ACTION__": str(next_action),
        "__RECOMMENDATIONS__": risk_text,
        "__OWASP_A01__": str(data.get("owaspA01", "")),
        "__OWASP_A02__": str(data.get("owaspA02", "")),
        "__OWASP_A03__": str(data.get("owaspA03", "")),
        "__OWASP_A04__": str(data.get("owaspA04", "")),
        "__OWASP_A05__": str(data.get("owaspA05", "")),
        "__OWASP_A06__": str(data.get("owaspA06", "")),
        "__OWASP_A07__": str(data.get("owaspA07", "")),
        "__OWASP_A08__": str(data.get("owaspA08", "")),
        "__OWASP_A09__": str(data.get("owaspA09", "")),
        "__OWASP_A10__": str(data.get("owaspA10", "")),
        "__MODULES__": modules_bullet,
    }
    replacements.update(coverage_rows)

    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, str(value))

    if module_block:
        rendered = rendered.replace(
            "<h2>Modules Reviewed</h2>",
            "<h2>Modules Reviewed</h2>" + module_block,
            1,
        )
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", default="all")
    parser.add_argument("--stamp", default=None)
    parser.add_argument("--scope", default="changed files (git diff main..HEAD)")
    args = parser.parse_args()

    data = json.loads(args.data.read_text(encoding="utf-8"))
    stamp = args.stamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    template_path = Path(__file__).resolve().parent / "reports" / "_template.html"
    if not template_path.exists():
        raise SystemExit(f"Template not found: {template_path}")

    doc = render_report(data, args.mode, stamp, args.scope, template_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc, encoding="utf-8")
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
