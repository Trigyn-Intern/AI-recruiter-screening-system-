"""Render a single Code Review Checklist HTML report from the two templates."""
from __future__ import annotations
import argparse, datetime, html, json, re, sys
from pathlib import Path

TAG_PATTERN = re.compile(r"\{(\^|#|/)([A-Za-z_][A-Za-z0-9_]*)\}")

def render_template(text, data):
    out = []
    pos = 0
    while pos < len(text):
        m = TAG_PATTERN.search(text, pos)
        if not m:
            out.append(_substitute_placeholders(text[pos:], data))
            break
        out.append(_substitute_placeholders(text[pos:m.start()], data))
        sigil, name = m.group(1), m.group(2)
        close = re.search(r"\{/" + re.escape(name) + r"\}", text[m.end():])
        if not close:
            raise ValueError("Unclosed tag {#" + name + "}")
        inner_start = m.end()
        inner_end = m.end() + close.start()
        body = text[inner_start:inner_end]
        if sigil == "#":
            items = data.get(name) or []
            for item in items:
                out.append(render_template(body, item))
        else:
            items = data.get(name) or []
            if not items: out.append(render_template(body, data))
        pos = inner_end + close.end() - close.start()
    return "".join(out)

_PLACEHOLDER = re.compile(r"\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}")

def _substitute_placeholders(text, scope):
    def repl(m):
        key = m.group(1)
        if key in scope and scope[key] is not None:
            return html.escape(str(scope[key]))
        return m.group(0)
    return _PLACEHOLDER.sub(repl, text)

CSS = """\
  :root { --bg:#fff; --fg:#1a1a1a; --muted:#6b7280; --border:#e5e7eb; --code-bg:#f3f4f6; --pass:#16a34a; --fail:#dc2626; --warn:#d97706; --info:#2563eb; --accent:#0e7490; }\
  * { box-sizing: border-box; }\
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; margin: 0; padding: 32px; color: var(--fg); background: var(--bg); line-height: 1.5; }\
  h1, h2, h3 { margin: 0 0 8px 0; } h1 { font-size: 24px; } h2 { font-size: 18px; margin-top: 32px; padding-bottom: 6px; border-bottom: 1px solid var(--border); } h3 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.04em; color: var(--muted); margin-top: 16px; }\
  p, li { font-size: 14px; } .meta { color: var(--muted); font-size: 13px; margin-bottom: 24px; }\
  .grid { display: grid; grid-template-columns: 200px 1fr; gap: 8px 16px; } .grid dt { color: var(--muted); } .grid dd { margin: 0; }\
  table { border-collapse: collapse; width: 100%; margin-top: 8px; } th, td { border: 1px solid var(--border); padding: 6px 10px; text-align: left; font-size: 13px; vertical-align: top; } th { background: #f9fafb; color: var(--muted); font-weight: 600; }\
  .pill { display: inline-block; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; } .pill.pass { background: #dcfce7; color: var(--pass); } .pill.fail { background: #fee2e2; color: var(--fail); } .pill.warn { background: #fef3c7; color: var(--warn); } .pill.na { background: #f3f4f6; color: var(--muted); }\
  ul, ol { padding-left: 24px; margin: 4px 0 0 0; } li { margin: 2px 0; }\
  pre { background: var(--code-bg); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px; overflow-x: auto; font-size: 12px; }\
  .note { background: #fff7ed; border: 1px solid #fed7aa; border-radius: 6px; padding: 10px 12px; color: #9a3412; font-size: 13px; }\
  .checklist-section { margin-top: 24px; } .checklist-section h2 { margin-top: 24px; }\
  .checkbox { font-family: monospace; color: var(--muted); margin-right: 8px; }
  .checklist-item { list-style: none; margin-left: -24px; }
  .checkbox-row { display: flex; align-items: flex-start; gap: 8px; cursor: pointer; padding: 2px 0; }
  .checkbox-row input { margin-top: 5px; flex-shrink: 0; cursor: pointer; }
  .checkbox-row:hover { background: #f9fafb; }
  .llm-tick { display: inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; background: #dcfce7; color: var(--pass); }
  .llm-tick { display: inline-block; margin-left: 8px; padding: 1px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; background: #dcfce7; color: var(--pass); }
\
  .red-flag { background: #fef2f2; border-left: 3px solid var(--fail); padding: 6px 10px; margin: 6px 0; font-size: 13px; }\
  .heuristic { background: #ecfeff; border-left: 3px solid var(--accent); padding: 6px 10px; margin: 6px 0; font-size: 13px; }\
  footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: 12px; }\
"""

def pill_for(status):
    s = (status or "").strip().lower()
    if s in ("pass","ok","yes","done","approved","approve"): return "pass"
    if s in ("fail","no","rejected","block","request changes"): return "fail"
    if s in ("warn","warning","needs changes","approve with suggestions","partial"): return "warn"
    return "na"

def render_structured(data):
    out = []
    out.append("<h2>Reviewer Information</h2>")
    out.append("<dl class=\"grid\">")
    for key, label in [("projectName","Project Name"),("repositoryBranch","Repository / Branch"),("reviewerName","Reviewer"),("reviewDate","Date of Review")]:
        out.append("<dt>" + html.escape(label) + "</dt><dd>" + html.escape(str(data.get(key, "") or "-")) + "</dd>")
    out.append("</dl>")
    items = data.get("generalChecklist") or []
    if items:
        out.append("<h2>General Checklist</h2><ul>")
        for it in items:
            item = html.escape(str(it.get("item", ""))); comment = html.escape(str(it.get("comment", "")))
            if comment: out.append("<li><strong>" + item + "</strong> - " + comment + "</li>")
            else: out.append("<li><strong>" + item + "</strong></li>")
        out.append("</ul>")
    rows = data.get("codeQuality") or []
    if rows:
        out.append("<h2>Code Quality</h2>")
        out.append("<table><thead><tr><th>Check</th><th>Status</th><th>Notes</th></tr></thead><tbody>")
        for r in rows:
            pill = pill_for(r.get("status", ""))
            out.append("<tr><td>" + html.escape(str(r.get("checkItem", ""))) + "</td><td><span class=\"pill " + pill + "\">" + html.escape(str(r.get("status", ""))) + "</span></td><td>" + html.escape(str(r.get("notes", ""))) + "</td></tr>")
        out.append("</tbody></table>")
    has_sec = bool(data.get("hasSecuritySection"))
    sec_rows = data.get("securityChecks") or []
    out.append("<h2>Security Review</h2>")
    if has_sec and sec_rows:
        out.append("<table><thead><tr><th>Vulnerability Check</th><th>Status</th><th>Comments</th></tr></thead><tbody>")
        for r in sec_rows:
            pill = pill_for(r.get("status", ""))
            out.append("<tr><td>" + html.escape(str(r.get("checkItem", ""))) + "</td><td><span class=\"pill " + pill + "\">" + html.escape(str(r.get("status", ""))) + "</span></td><td>" + html.escape(str(r.get("comments", ""))) + "</td></tr>")
        out.append("</tbody></table>")
    else: out.append("<p class=\"note\">No security-specific checks were included in this review.</p>")
    perf = data.get("performanceChecks") or []
    if perf:
        out.append("<h2>Performance Checks</h2><ul>")
        for p in perf: out.append("<li><strong>" + html.escape(str(p.get("title", ""))) + "</strong>: " + html.escape(str(p.get("details", ""))) + "</li>")
        out.append("</ul>")
    style = data.get("stylePractices") or []
    if style:
        out.append("<h2>Style and Best Practices</h2><ul>")
        for s in style: out.append("<li><strong>" + html.escape(str(s.get("practice", ""))) + "</strong>: " + html.escape(str(s.get("issuesFound", ""))) + "</li>")
        out.append("</ul>")
    out.append("<h2>Test Coverage</h2><dl class=\"grid\">")
    out.append("<dt>Are tests present?</dt><dd>" + html.escape(str(data.get("hasTests", "-"))) + "</dd>")
    out.append("<dt>Test Coverage % (approx)</dt><dd>" + html.escape(str(data.get("coveragePercent", "-"))) + "</dd>")
    out.append("<dt>Manual Tests Needed</dt><dd>" + html.escape(str(data.get("manualTestNotes", "-"))) + "</dd></dl>")
    fb = data.get("reviewerFeedbacks") or []
    if fb:
        out.append("<h2>Additional Reviewers Feedback</h2><ul>")
        for f in fb: out.append("<li><strong>" + html.escape(str(f.get("reviewerName", ""))) + "</strong>: " + html.escape(str(f.get("comment", ""))) + "</li>")
        out.append("</ul>")
    if data.get("finalNotes"): out.append("<h2>Final Notes</h2><p>" + html.escape(str(data["finalNotes"])) + "</p>")
    out.append("<h2>Approval</h2><dl class=\"grid\">")
    out.append("<dt>Approved by</dt><dd>" + html.escape(str(data.get("approvedBy", "-"))) + "</dd>")
    out.append("<dt>Date of Approval</dt><dd>" + html.escape(str(data.get("approvalDate", "-"))) + "</dd>")
    merge = data.get("mergeStatus", "-") or "-"; pill = pill_for(merge)
    out.append("<dt>Merge Status</dt><dd><span class=\"pill " + pill + "\">" + html.escape(str(merge)) + "</span></dd></dl>")
    return "\n".join(out)

SECTIONS = [
    ("Correctness",[
        "Does the code do what the PR description says it does?",
        "Are edge cases handled? (empty input, null values, boundary conditions)",
        "Does it handle errors gracefully - or does it silently fail?",
        "Are there any obvious off-by-one errors in loops or array indexing?",
        "Does concurrency introduce race conditions or deadlocks?",
        "Are database transactions used correctly? (no partial writes)",
        "Is business logic correct, not just technically working?",
    ]),
    ("Security",[
        "Is user input validated and sanitized before use?",
        "Are SQL queries parameterized? (no string concatenation with user data)",
        "Are secrets or credentials hardcoded anywhere? (API keys, passwords)",
        "Is authentication checked before accessing protected resources?",
        "Is authorization enforced - not just is the user logged in but can this user do this?",
        "Are file paths validated to prevent path traversal attacks?",
        "Is sensitive data (passwords, tokens, PII) logged anywhere?",
        "Are dependencies introduced by this PR known-good? (no obviously suspicious packages)",
    ]),
    ("Performance",[
        "Are there N+1 query patterns? (loop that triggers a database query each iteration)",
        "Are expensive operations cached where appropriate?",
        "Does the code handle large inputs without memory issues?",
        "Are there unnecessary re-renders or re-computations? (frontend)",
        "Is pagination used for list endpoints that could return large datasets?",
        "Are database indexes used for the queries this code will run?",
    ]),
    ("Testing",[
        "Are there tests for the new behavior?",
        "Do existing tests still pass? (check CI results)",
        "Are edge cases tested, not just the happy path?",
        "Are tests testing behavior, not implementation?",
        "Is test data realistic? (tests that only pass with id = 1 may fail in production)",
        "Is there a test for the bug that was fixed? (regression test)",
    ]),
    ("Readability and Maintainability",[
        "Is the code readable by someone unfamiliar with this part of the codebase?",
        "Are function and variable names descriptive?",
        "Are complex sections explained with comments - not what the code does, but why?",
        "Is the code DRY - or is repetition justified?",
        "Are magic numbers replaced with named constants?",
        "Is the function doing one thing? (single responsibility)",
        "Is the diff focused? (unrelated changes mixed in?)",
    ]),
    ("API and Interface Design",[
        "Does the public API surface make sense? (naming, parameter order, return types)",
        "Are breaking changes documented?",
        "Is the API consistent with similar patterns in the codebase?",
        "Are deprecated functions or parameters flagged?",
        "Is the feature flag or rollout strategy defined for risky changes?",
    ]),
]

N1 = ("# Bad: N+1 queries\nfor user_id in user_ids:\n"
       "    user = db.query(User).filter(User.id == user_id).first()  # 1 query per iteration\n"
       "    send_email(user)\n\n"
       "# Good: single query\n"
       "users = db.query(User).filter(User.id.in_(user_ids)).all()\n"
       "for user in users:\n"
       "    send_email(user)")

def render_detailed(data=None):
    out = ['<h1 style="margin-top:32px">The Complete Code Review Checklist</h1>']
    out.append('<p class="meta">Tick each box. Leave a one-line note for anything unchecked. Link to a follow-up issue if the fix is out of scope for this PR.</p>')
    import re as _re
    raw_checked = (data or {}).get('checkedItems') or []
    def _norm(s):
        return _re.sub(r'\s+', ' ', s.lower().strip()).rstrip('.?!')
    norm_checked = {_norm(c) for c in raw_checked}
    prefix_checked = {c[:40].lower() for c in raw_checked}
    for name, items in SECTIONS:
        out.append('<div class="checklist-section"><h2>' + html.escape(name) + '</h2><ul>')
        for it in items:
            n = _norm(it)
            p_ = it[:40].lower()
            checked = (n in norm_checked) or (p_ in prefix_checked)
            box = '<input type="checkbox" checked />' if checked else '<input type="checkbox" s/>'
            note = ' <span class="llm-tick">verified by LLM</span>' if checked else ''
            out.append('<li class="checklist-item"><label class="checkbox-row">' + box + html.escape(it) + note + '</label></li>')
        out.append('</ul></div>')
    out.append("<h3>Red flag patterns to check</h3>")
    out.append('<div class="red-flag">catch(e) {} - swallowed exceptions</div>')
    out.append('<div class="red-flag">Unchecked array access without bounds validation</div>')
    out.append('<div class="red-flag">Missing <code>await</code> on async calls</div>')
    out.append("<h3>Performance: N+1 queries</h3>")
    out.append('<div class="heuristic">Performance issues in code review are often subtle. The most common culprit: a loop that queries the database on every iteration.</div>')
    out.append("<pre><code>" + html.escape(N1) + "</code></pre>")
    out.append("<h3>Testing heuristic</h3>")
    out.append('<div class="heuristic">If the PR description says "fix X bug," there should be a test that would have caught the bug before the fix.</div>')
    out.append("<h3>Tooling notes</h3><ul>")
    out.append("<li><strong>DevPlaybook AI Code Review</strong> - paste your diff and get automated security analysis before human review.</li>")
    out.append("<li><strong>DevPlaybook Code Diff</strong> - compare before/after versions of changed files when reviewing locally.</li>")
    out.append("</ul>")
    return "\n".join(out)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--structured", required=True, type=Path)
    p.add_argument("--detailed", required=True, type=Path)
    p.add_argument("--data", type=Path, default=None)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--stamp", default=None)
    args = p.parse_args()
    data = {}
    if args.data and args.data.exists(): data = json.loads(args.data.read_text(encoding="utf-8"))
    structured_html = render_structured(data)
    detailed_html = render_detailed(data)
    stamp = args.stamp or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    doc = "\n".join([
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head><meta charset=\"utf-8\"><title>Code Review Checklist - " + html.escape(stamp) + "</title><style>" + CSS + "</style></head>",
        "<body>",
        "<header><h1>Code Review Checklist</h1><p class=\"meta\">Generated " + html.escape(stamp) + " by the <code>code-review-policy</code> skill.</p></header>",
        structured_html,
        detailed_html,
        "<footer>Generated by the <code>code-review-policy</code> skill from <code>checklist-structured.md</code> and <code>checklist-detailed.md</code>.</footer>",
        "</body></html>",
    ])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(doc, encoding="utf-8")
    print("wrote", args.output)
    return 0

if __name__ == "__main__":
    sys.exit(main())
