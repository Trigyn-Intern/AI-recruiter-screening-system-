"""Fetch the latest CI pipeline run from GitHub and lay it out for inspection.

What this script does
---------------------
1. Detects the current GitHub repository and branch (so it works for every
   developer, not just one machine).
2. Queries the GitHub API for the latest completed run of ``ci.yml`` on
   that branch.
3. Downloads the full workflow logs and writes them, in order, to
   ``reports/ci-logs.txt``.
4. Downloads every build artifact (the four expected ones are
   ``backend-python-reports``, ``backend-node-reports``,
   ``dist-frontend``, and ``dist-frontend-test``) and extracts each one
   under ``reports/ci/<artifact-name>/`` with path-traversal protection.
5. Generates a polished ``reports/ci/ci-summary.html`` landing page and a
   machine-readable ``reports/ci/ci-summary.json`` so the testing
   dashboard can pick up the data via the existing ``/api/reports``
   endpoint.

Design goals
------------
- **Local-first.** Never sends resume or test data anywhere. Uses only
  the public GitHub REST API with the developer-supplied ``GITHUB_TOKEN``.
- **Hardened downloads.** Strips the ``Authorization`` header on
  cross-origin redirects (S3 returns 401 otherwise), enforces a sane
  payload cap, validates artifact ZIP members, and refuses to write
  outside the working tree.
- **Readable output.** The summary HTML gives every artifact its own
  card with file counts, sizes, and the path a developer clicks to open
  it. The JSON mirrors the dashboard's report catalog shape so the
  testing dashboard can render it without changes.
- **Deterministic.** Exit codes are stable: 0 = success, 2 = no token /
  rate limited, 3 = nothing fetched, 1 = unexpected error. Network and
  HTTP failures are caught per-artifact so one bad download does not
  sink the rest.

Usage
-----
    python scripts/fetch_ci.py            # uses $GITHUB_TOKEN from env
    python scripts/fetch_ci.py --dry-run  # show what would happen, no HTTP

The token must have ``actions:read`` and ``contents:read`` scopes. A
classic PAT or a fine-grained token with access to the repository works.
"""

from __future__ import annotations

import argparse
import html as html_lib
import io
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"
GITHUB_VERSION = "2022-11-28"
WORKFLOW_FILE = "ci.yml"
LOGS_OUT = Path("reports/ci-logs.txt")
CI_ROOT = Path("reports/ci")
SUMMARY_HTML = CI_ROOT / "ci-summary.html"
SUMMARY_JSON = CI_ROOT / "ci-summary.json"

# 50 MB per artifact; 25 MB aggregated logs. Plenty for a CI run, stops
# runaway downloads cold.
ARTIFACT_BYTE_LIMIT = 50 * 1024 * 1024
LOGS_BYTE_LIMIT = 25 * 1024 * 1024

# The four artifacts the .github/workflows/ci.yml pipeline produces on a
# full run. Anything else is still extracted but is described generically.
KNOWN_ARTIFACTS = (
    "backend-python-reports",
    "backend-node-reports",
    "dist-frontend",
    "dist-frontend-test",
)


# ---------------------------------------------------------------------------
# Networking helpers
# ---------------------------------------------------------------------------


class NoAuthRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Drop ``Authorization`` on cross-origin redirects.

    GitHub returns artifact downloads as 302 redirects to S3. S3 rejects
    signed requests that include an unexpected ``Authorization`` header
    with a 401. Stripping the header on the redirect gives the S3 URL a
    chance to succeed.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req is not None and new_req.has_header("Authorization"):
            new_req.remove_header("Authorization")
        return new_req


def install_redirect_handler() -> None:
    opener = urllib.request.build_opener(NoAuthRedirectHandler())
    urllib.request.install_opener(opener)


def github_request(url, token, *, raw=False):
    """GET a GitHub URL and return parsed JSON or raw bytes.

    Network errors are translated to short, actionable messages instead
    of raw stack traces.
    """
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", GITHUB_VERSION)

    try:
        with urllib.request.urlopen(req) as response:
            payload = response.read()
            if raw:
                return payload
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        reason = {
            401: "Bad or missing GITHUB_TOKEN (HTTP 401).",
            403: "GitHub denied the request (HTTP 403). Usually rate limit or insufficient scope.",
            404: "Not found (HTTP 404). Check that the repo and workflow name are correct.",
        }.get(exc.code, f"HTTP {exc.code}: {exc.reason}")
        raise GitHubError(reason) from exc
    except urllib.error.URLError as exc:
        raise GitHubError(f"Network error talking to GitHub: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Data shapes
# ---------------------------------------------------------------------------


class GitHubError(RuntimeError):
    """Raised when the GitHub API rejects a request."""


@dataclass
class FileEntry:
    path: str
    size_bytes: int
    size_human: str
    kind: str  # html, json, xml, css, png, md, txt, log, other
    open_href: str  # workspace-relative path; clickable in the dashboard
    preview: str | None = None  # short first-line preview for non-binary files


@dataclass
class ArtifactSummary:
    name: str
    download_url: str
    size_bytes: int
    size_human: str
    file_count: int
    top_level: list
    files: list = field(default_factory=list)
    status: str = "ok"
    note: str | None = None
    output_dir: str | None = None
    # Parsed content derived from the extracted files. Keys are stable so the
    # HTML and JSON consumers can render without re-parsing the tree.
    parsed: dict = field(default_factory=dict)


@dataclass
class RunSummary:
    repo: str
    branch: str
    workflow: str
    run_id: int
    run_name: str
    status: str
    conclusion: str
    event: str
    head_sha: str
    created_at: str
    updated_at: str
    html_url: str
    actor: str | None = None
    logs_path: str = ""
    logs_bytes: int = 0
    artifacts: list = field(default_factory=list)
    fetched_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    def total_files(self) -> int:
        return sum(a.file_count for a in self.artifacts)

    def total_bytes(self) -> int:
        return sum(a.size_bytes for a in self.artifacts)


# ---------------------------------------------------------------------------
# Git + GitHub discovery
# ---------------------------------------------------------------------------


def get_git_info():
    """Read the GitHub repo path and current branch from ``git`` itself."""
    try:
        remote_url = subprocess.check_output(
            ["git", "config", "--get", "remote.origin.url"],
            text=True,
        ).strip()
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            text=True,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise GitHubError(
            "Could not determine git remote or branch. "
            "Run this script from inside the repository checkout."
        ) from exc

    if remote_url.startswith("git@github.com:"):
        repo_path = remote_url.split(":", 1)[1]
    elif "github.com" in remote_url:
        repo_path = remote_url.split("github.com/", 1)[-1]
    else:
        raise GitHubError(f"Remote origin is not on GitHub: {remote_url}")

    repo_path = repo_path.removesuffix(".git")
    return repo_path, branch


def latest_workflow_run(repo_path, branch, token):
    """Return the metadata for the most recent completed ``ci.yml`` run."""
    url = (
        f"{GITHUB_API}/repos/{repo_path}/actions/workflows/{WORKFLOW_FILE}"
        f"/runs?branch={branch}&status=completed&per_page=1"
    )
    data = github_request(url, token)
    runs = data.get("workflow_runs") or []
    if not runs:
        raise GitHubError(f"No completed {WORKFLOW_FILE} runs found for branch '{branch}'.")
    return runs[0]


def list_artifacts(repo_path, run_id, token):
    """Return every artifact attached to the run."""
    url = f"{GITHUB_API}/repos/{repo_path}/actions/runs/{run_id}/artifacts?per_page=100"
    data = github_request(url, token)
    return data.get("artifacts") or []


# ---------------------------------------------------------------------------
# Downloads
# ---------------------------------------------------------------------------


def download_bytes(url, token, byte_limit, label):
    """Download a URL into memory with a hard byte cap."""
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req) as response:
            chunks = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > byte_limit:
                    raise GitHubError(
                        f"{label} exceeded the {byte_limit // (1024 * 1024)} MB cap and was truncated."
                    )
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib.error.HTTPError as exc:
        raise GitHubError(f"{label} download failed: HTTP {exc.code} {exc.reason}") from exc


def download_logs(run, token, dest):
    """Fetch the run logs ZIP and write an aggregated, ordered text file."""
    logs_url = run.get("logs_url")
    if not logs_url:
        raise GitHubError("Run has no logs_url; logs are unavailable for this workflow.")

    raw = download_bytes(logs_url, token, LOGS_BYTE_LIMIT, "Logs archive")
    dest.parent.mkdir(parents=True, exist_ok=True)

    aggregated_path = dest
    extracted = 0
    skipped = 0
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        text_members = sorted(name for name in zf.namelist() if name.endswith(".txt"))
        with aggregated_path.open("w", encoding="utf-8") as out:
            for name in text_members:
                out.write(f"\n--- {name} ---\n")
                try:
                    out.write(zf.read(name).decode("utf-8", errors="replace"))
                    extracted += 1
                except (KeyError, zipfile.BadZipFile, RuntimeError) as exc:
                    skipped += 1
                    out.write(f"[fetch_ci] could not read {name}: {exc}\n")

    if extracted == 0:
        # Still write the file so the dashboard has something to display.
        aggregated_path.write_text(
            f"[fetch_ci] Run {run.get('id')} produced no log text files.\n",
            encoding="utf-8",
        )

    print(f"  -> {extracted} log file(s) aggregated, {skipped} skipped")
    return aggregated_path.stat().st_size


# ---------------------------------------------------------------------------
# Artifact handling
# ---------------------------------------------------------------------------


def safe_extract(zip_bytes, dest):
    """Extract a zip into ``dest`` while refusing path-traversal members."""
    extracted_files = []
    extracted_dirs = []
    dest = dest.resolve()
    dest.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        namelist = zf.namelist()
        top_items = sorted(list(set(m.split("/")[0] for m in namelist if m)))
        for member in namelist:
            member_path = (dest / member).resolve()
            try:
                member_path.relative_to(dest)
            except ValueError as exc:
                raise GitHubError(
                    f"Refusing to extract '{member}' (would escape {dest})."
                ) from exc

            if member.endswith("/"):
                member_path.mkdir(parents=True, exist_ok=True)
                extracted_dirs.append(member)
                continue

            member_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, member_path.open("wb") as out:
                shutil.copyfileobj(src, out)
            extracted_files.append(member)

    return len(extracted_files), top_items, sorted(extracted_files)


def human_bytes(num):
    """Render ``1234567`` as ``1.2 MB``."""
    units = ("B", "KB", "MB", "GB")
    value = float(num)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{num} B"


def download_artifact(repo_path, artifact, token):
    """Download one artifact ZIP, extract it, and return a summary."""
    name = artifact.get("name", "unnamed")
    download_url = (
        f"{GITHUB_API}/repos/{repo_path}/actions/artifacts/"
        f"{artifact['id']}/zip"
    )
    extract_root = CI_ROOT / name
    summary = ArtifactSummary(
        name=name,
        download_url=download_url,
        size_bytes=0,
        size_human="0 B",
        file_count=0,
        top_level=[],
        status="ok",
        output_dir=str(extract_root).replace("\\", "/"),
    )

    try:
        # Wipe any previous version so the dashboard does not display stale data.
        if extract_root.exists():
            shutil.rmtree(extract_root)
        raw = download_bytes(download_url, token, ARTIFACT_BYTE_LIMIT, f"Artifact '{name}'")
        summary.size_bytes = len(raw)
        summary.size_human = human_bytes(summary.size_bytes)

        file_count, top_dirs, files = safe_extract(raw, extract_root)
        summary.file_count = file_count
        summary.top_level = top_dirs
        summary.files = files
        summary.status = "ok"
        print(
            f"  -> extracted {file_count} file(s) into {summary.output_dir} "
            f"({summary.size_human})"
        )
    except GitHubError as exc:
        summary.status = "error"
        summary.note = str(exc)
        print(f"  ! {summary.note}")

    return summary


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def build_known_artifact_index():
    """Map every known artifact to a one-line description for the cards."""
    return {
        "backend-python-reports": (
            "Backend (FastAPI / pytest) coverage + AI engineering reports. "
            "Includes HTML coverage, JUnit XML, and the AI dashboard."
        ),
        "backend-node-reports": (
            "Backend Node (Express) lint, audit, and test output."
        ),
        "dist-frontend": (
            "Production build of the recruiter React/Vite frontend."
        ),
        "dist-frontend-test": (
            "Production build of the React/Vite testing dashboard (port 5174)."
        ),
    }


def _render_artifact_extras(art):
    """Render per-artifact structured detail rows (JUnit, coverage, severity, etc)."""
    parsed = getattr(art, "parsed", None) or {}
    if not parsed:
        return ""

    def _escape(value):
        return html_lib.escape("" if value is None else str(value))

    def _fmt(seconds):
        if seconds is None or seconds == "":
            return "\u2014"
        try:
            s = float(seconds)
        except (TypeError, ValueError):
            return _escape(seconds)
        if s < 1:
            return f"{int(round(s * 1000))} ms"
        if s < 60:
            return f"{s:.2f} s"
        minutes, secs = divmod(s, 60)
        return f"{int(minutes)}m {secs:.0f}s"

    def _badge(text, cls="muted"):
        return f'<span class="status status-{cls}">{_escape(text)}</span>'

    parts = []

    junit = parsed.get("junit", {})
    if junit.get("present") and not junit.get("error"):
        badges = [
            _badge(f"{junit.get('passed', 0)}/{junit.get('tests', 0)} pass",
                   "pass" if junit.get("failures", 0) == 0 and junit.get("errors", 0) == 0 else "err"),
            _badge(f"{junit.get('pass_rate', 0)}% pass rate", "muted"),
            _badge(_fmt(junit.get("duration_seconds")), "muted"),
        ]
        if junit.get("failures"):
            badges.append(_badge(f"{junit['failures']} failures", "err"))
        if junit.get("errors"):
            badges.append(_badge(f"{junit['errors']} errors", "err"))
        if junit.get("skipped"):
            badges.append(_badge(f"{junit['skipped']} skipped", "muted"))
        summary = '<div class="art-extra">' + "".join(badges) + '</div>'
        failed = junit.get("failed_cases") or []
        if failed:
            rows = "".join(
                f'<li><code>{_escape(c["classname"])}::{_escape(c["name"])}</code> '
                f'<small>({_fmt(c["duration"])})</small> &mdash; {_escape(c["message"])}</li>'
                for c in failed[:10]
            )
            summary += f'<details><summary>{len(failed)} failing test(s)</summary><ul class="art-list">{rows}</ul></details>'
        parts.append(summary)

    coverage = parsed.get("coverage", {})
    if coverage.get("present") and not coverage.get("error"):
        line = coverage.get("line_rate")
        badge = _badge(f"{line}% line coverage", "pass" if (line or 0) >= 50 else "warn") if line is not None else None
        summary = '<div class="art-extra">' + "".join(b for b in [badge] if b) + '</div>'
        weakest = coverage.get("weakest") or []
        if weakest:
            rows = "".join(
                f'<li><code>{_escape(w["file"])}</code> &mdash; {w["line_rate"]}%</li>' for w in weakest
            )
            summary += f'<details><summary>Lowest-coverage files</summary><ul class="art-list">{rows}</ul></details>'
        parts.append(summary)

    status = parsed.get("status", {})
    if status.get("present") and not status.get("error"):
        rows = status.get("files") or []
        if rows:
            body = "".join(
                f'<tr><td><code>{_escape(r["file"])}</code></td>'
                f'<td>{r["statements"]}</td><td>{r["covered"]}</td>'
                f'<td>{r["missing"]}</td><td>{r["excluded"]}</td>'
                f'<td>{r["line_rate"]}%</td></tr>'
                for r in rows[:10]
            )
            summary = (
                '<details><summary>Per-file coverage (statements vs missing)</summary>'
                '<table class="art-table"><thead><tr>'
                '<th>File</th><th>Statements</th><th>Covered</th><th>Missing</th>'
                '<th>Excluded</th><th>Rate</th></tr></thead><tbody>'
                f'{body}</tbody></table></details>'
            )
            parts.append(summary)

    ai = parsed.get("ai_dashboard", {})
    if ai.get("present") and not ai.get("error"):
        summary = '<div class="art-extra">'
        summary += _badge(f"{ai.get('source_files', 0)} source files", "muted")
        summary += _badge(f"{ai.get('test_modules', 0)} test modules", "muted")
        summary += _badge(f"{ai.get('oversized_files', 0)} oversized", "warn" if ai.get("oversized_files", 0) else "muted")
        summary += _badge(f"{ai.get('dependency_manifests', 0)} manifests", "muted")
        summary += '</div>'
        reports = ai.get("reports") or []
        if reports:
            summary += f'<p class="muted">AI reports: {_escape(", ".join(reports))}</p>'
        parts.append(summary)

    vulns = parsed.get("vulnerabilities", {})
    if vulns.get("present") and not vulns.get("error"):
        sev = vulns.get("severity") or {}
        badges = []
        for level in ("Critical", "High", "Medium", "Low"):
            count = sev.get(level, 0)
            if count == 0:
                continue
            badges.append(_badge(f"{level}: {count}", "err" if level in {"Critical", "High"} else "warn"))
        summary = '<div class="art-extra">' + "".join(badges) + '</div>'
        if vulns.get("fails_threshold"):
            summary += '<p class="status status-err">Threshold breached &mdash; PR gate will fail.</p>'
        parts.append(summary)

    catalog = parsed.get("catalog", {})
    if catalog.get("present") and not catalog.get("error"):
        summary = '<div class="art-extra">'
        summary += _badge(f"{catalog.get('report_count', 0)} reports", "muted")
        summary += '</div>'
        cats = ", ".join(catalog.get("categories") or [])
        if cats:
            summary += f'<p class="muted">Categories: {_escape(cats)}</p>'
        summary += f'<p class="muted">Updated: {_escape(catalog.get("updated", ""))}</p>'
        parts.append(summary)

    k6 = parsed.get("k6", {})
    if k6.get("present") and not k6.get("error"):
        metrics = k6.get("metrics") or {}
        if metrics:
            rows = "".join(
                f'<tr><td><code>{_escape(name)}</code></td>'
                f'<td>{vals.get("count", 0)}</td>'
                f'<td>{_fmt(vals.get("min"))}</td>'
                f'<td>{_fmt(vals.get("p50"))}</td>'
                f'<td>{_fmt(vals.get("p95"))}</td>'
                f'<td>{_fmt(vals.get("max"))}</td></tr>'
                for name, vals in metrics.items()
            )
            summary = (
                '<details><summary>k6 load metrics</summary>'
                '<table class="art-table"><thead><tr>'
                '<th>Metric</th><th>Count</th><th>Min</th><th>p50</th>'
                '<th>p95</th><th>Max</th></tr></thead><tbody>'
                f'{rows}</tbody></table></details>'
            )
            parts.append(summary)

    logs = parsed.get("logs", {})
    if logs.get("ruff_or_lint_ok"):
        parts.append(_badge("Backend Node lint passed", "pass"))

    node_audit = parsed.get("node_audit", {})
    if node_audit.get("present"):
        findings = node_audit.get("findings", [])
        if findings:
            audit_badges = []
            for count, level in findings:
                color = "err" if level.lower() in ("critical", "high") else "warn"
                audit_badges.append(_badge(f"{count} {level}", color))
            parts.append('<div class="art-extra">&#x1F6E1; npm audit: ' + "".join(audit_badges) + '</div>')
        else:
            parts.append('<div class="art-extra">' + _badge("npm audit clean", "pass") + '</div>')

    if art.name == "dist-frontend-test":
        size = parsed.get("index_size_bytes", 0)
        if size:
            parts.append(_badge(f"index.html: {human_bytes(size)}", "muted"))

    if not parts:
        return ""
    return '<div class="art-section">' + "".join(parts) + '</div>'


def render_summary_html(summary, descriptions):
    """Build the self-contained, polished HTML landing page."""
    artifact_cards = []

    # Pre-compute pieces that are referenced by both the header and the cards.
    log_signals = getattr(summary, 'log_signals', {}) or {}
    pytest_unit = log_signals.get('python_unit_tests') or {}
    pytest_int = log_signals.get('python_integration_tests') or {}
    cov_log = log_signals.get('coverage') or {}
    frontend_jobs = log_signals.get('frontend_jobs') or []

    for art in summary.artifacts:
        cls = "card" if art.status == "ok" else "card error"
        title = html_lib.escape(art.name)
        size = html_lib.escape(art.size_human)
        status_label = "downloaded" if art.status == "ok" else "error"
        desc = html_lib.escape(descriptions.get(art.name, "Custom artifact uploaded by the workflow."))
        file_count = art.file_count
        if art.status == "ok":
            extras = _render_artifact_extras(art)
            details = (
                "<dl>"
                f"<dt>Files</dt><dd>{file_count}</dd>"
                f"<dt>Size</dt><dd>{size}</dd>"
                f"<dt>Location</dt><dd><code>{html_lib.escape(art.output_dir or '')}</code></dd>"
                "</dl>" + extras
            )
            if art.top_level:
                # Known HTML reports get clickable links; known htmlcov folder links to its index
                _HTML_NAMES = {
                    "junit-python.html", "junit-node.html", "junit-frontend.html",
                    "junit-frontend-test.html", "coverage-python.html", "coverage-node.html",
                    "coverage-frontend.html", "coverage-frontend-test.html",
                    "dependency-check-report.html",
                }
                top_items = ""
                for t in art.top_level:
                    if t in ("htmlcov-python", "htmlcov-python/"):
                        top_items += (
                            f'<li><a href="./{html_lib.escape(art.name)}/htmlcov-python/index.html" target="_blank">'
                            f'<code>{html_lib.escape(t)} &#x2197; Interactive Coverage</code></a></li>'
                        )
                    elif t in _HTML_NAMES or t.endswith(".html"):
                        top_items += (
                            f'<li><a href="./{html_lib.escape(art.name)}/{html_lib.escape(t)}" target="_blank">'
                            f'<code>{html_lib.escape(t)}</code></a></li>'
                        )
                    else:
                        top_items += f'<li><code>{html_lib.escape(t)}</code></li>'
                details += f'<h4>Top-level entries</h4><ul>{top_items}</ul>'
        else:
            details = (
                f"<p class=\"error\">{html_lib.escape(art.note or 'Unknown error')}</p>"
            )

        artifact_cards.append(
            f"<section class=\"{cls}\">"
            f"<header><h3>{title}</h3>"
            f"<span class=\"status status-{art.status}\">{status_label}</span>"
            "</header>"
            f"<p class=\"desc\">{desc}</p>"
            f"{details}"
            "</section>"
        )

    if not artifact_cards:
        artifact_cards.append(
            "<section class=\"card empty\"><p>No artifacts were produced by this run.</p></section>"
        )

    artifact_html = "\n".join(artifact_cards)
    verdict_class = "pass" if summary.conclusion == "success" else (
        "fail" if summary.conclusion in {"failure", "cancelled", "timed_out"} else "warn"
    )
    verdict_label = (summary.conclusion or "unknown").replace("_", " ").upper()

    return f"""<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<title>CI Summary &mdash; {html_lib.escape(summary.run_name or summary.workflow)}</title>
<style>
  :root {{
    --bg: #0f1d18;
    --panel: #15241f;
    --border: rgba(255,255,255,0.08);
    --text: #e6efe9;
    --muted: #9bb1a8;
    --accent: #82b4a7;
    --pass: #4caf73;
    --fail: #d96b6b;
    --warn: #d9a26b;
    --code-bg: #0b1310;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.5; }}
  main {{ max-width: 1080px; margin: 0 auto; padding: 32px 24px 64px; }}
  header.page {{ border-bottom: 1px solid var(--border); padding-bottom: 18px; margin-bottom: 28px; }}
  header.page h1 {{ margin: 0; font-size: 24px; letter-spacing: 0.02em; }}
  header.page p {{ margin: 6px 0 0; color: var(--muted); font-size: 13px; }}
  .verdict {{ display: inline-block; padding: 2px 10px; border-radius: 999px; font-size: 12px;
              font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; }}
  .verdict.pass {{ background: rgba(76,175,115,0.18); color: var(--pass); }}
  .verdict.fail {{ background: rgba(217,107,107,0.18); color: var(--fail); }}
  .verdict.warn {{ background: rgba(217,162,107,0.18); color: var(--warn); }}
  .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
              gap: 14px; margin-bottom: 32px; }}
  .summary .item {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
                    padding: 14px 16px; }}
  .summary .item h4 {{ margin: 0; color: var(--muted); font-size: 11px;
                       text-transform: uppercase; letter-spacing: 0.06em; }}
  .summary .item p {{ margin: 6px 0 0; font-size: 18px; font-weight: 600; color: var(--text); }}
  .summary .item small {{ color: var(--muted); font-weight: 400; font-size: 12px; }}
  .cards {{ display: grid; gap: 16px; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 10px;
           padding: 16px; display: flex; flex-direction: column; gap: 8px; }}
  .card.error {{ border-color: rgba(217,107,107,0.4); }}
  .card header {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
  .card h3 {{ margin: 0; font-size: 14px; color: #fff; }}
  .card .desc {{ margin: 0; color: var(--muted); font-size: 12.5px; }}
  .card dl {{ margin: 6px 0 0; display: grid; grid-template-columns: 90px 1fr; gap: 2px 12px;
              font-size: 12.5px; }}
  .card dt {{ color: var(--muted); }}
  .card dd {{ margin: 0; word-break: break-all; }}
  .card h4 {{ margin: 8px 0 4px; color: var(--muted); font-size: 11px;
              text-transform: uppercase; letter-spacing: 0.06em; }}
  .card ul {{ margin: 0; padding-left: 18px; font-size: 12.5px; color: var(--muted); }}
  .card code {{ background: var(--code-bg); border: 1px solid var(--border); padding: 1px 6px;
                border-radius: 4px; font-size: 11.5px; color: var(--accent); }}
  .card p.error {{ margin: 0; color: var(--fail); font-size: 12.5px; }}
  .card.empty {{ text-align: center; color: var(--muted); }}
  .status {{ font-size: 10px; padding: 1px 8px; border-radius: 999px; font-weight: 700;
             text-transform: uppercase; letter-spacing: 0.05em; }}
  .status-ok {{ background: rgba(76,175,115,0.18); color: var(--pass); }}
  .status-error {{ background: rgba(217,107,107,0.18); color: var(--fail); }}
  footer {{ margin-top: 32px; color: var(--muted); font-size: 11.5px; text-align: center; }}
  a {{ color: var(--accent); }}
  .meta-grid {{ display: grid; gap: 4px 16px; grid-template-columns: 130px 1fr;
                font-size: 13px; margin-top: 12px; }}
  .meta-grid dt {{ color: var(--muted); }}
  .meta-grid dd {{ margin: 0; word-break: break-all; }}
</style>
</head>
<body>
<main>
  <header class=\"page\">
    <h1>CI Summary &mdash; {html_lib.escape(summary.workflow)}</h1>
    <p>
      Run <a href=\"{html_lib.escape(summary.html_url)}\">#{summary.run_id}</a>
      on <strong>{html_lib.escape(summary.branch)}</strong>
      <span class=\"verdict {verdict_class}\">{verdict_label}</span>
    </p>
    <dl class=\"meta-grid\">
      <dt>Repository</dt><dd>{html_lib.escape(summary.repo)}</dd>
      <dt>Workflow</dt><dd>{html_lib.escape(summary.workflow)}</dd>
      <dt>Trigger</dt><dd>{html_lib.escape(summary.event)}</dd>
      <dt>Commit</dt><dd><code>{html_lib.escape(summary.head_sha[:12])}</code></dd>
      <dt>Started</dt><dd>{html_lib.escape(summary.created_at)}</dd>
      <dt>Updated</dt><dd>{html_lib.escape(summary.updated_at)}</dd>
      <dt>Actor</dt><dd>{html_lib.escape(summary.actor or 'n/a')}</dd>
      <dt>Logs</dt><dd><code>{html_lib.escape(summary.logs_path)}</code> ({human_bytes(summary.logs_bytes)})</dd>
    </dl>
  </header>

  <section class=\"summary\" aria-label=\"Run totals\">
    <div class=\"item\"><h4>Artifacts</h4><p>{len(summary.artifacts)}</p></div>
    <div class=\"item\"><h4>Files</h4><p>{summary.total_files():,}</p></div>
    <div class=\"item\"><h4>Downloaded</h4><p>{human_bytes(summary.total_bytes())}</p></div>
    <div class=\"item\"><h4>Fetched at</h4><p>{html_lib.escape(summary.fetched_at)}</p></div>
  </section>

  <h2 style=\"margin-bottom:14px;font-size:16px;\">Artifacts</h2>
  <div class=\"cards\">
    {artifact_html}
  </div>

  <footer>
    Generated by <code>scripts/fetch_ci.py</code>. Open this file directly in any browser; no network required.
  </footer>
</main>
</body>
</html>
"""


def _enrich_artifact_summaries(summary):
    """Run the artifact-specific parsers against each extracted folder."""
    try:
        from ci_report_modules import enrich_artifact
    except ImportError:
        return
    for art in summary.artifacts:
        if art.status != "ok" or not art.output_dir:
            continue
        try:
            enrich_artifact(art, Path(art.output_dir))
            # Inject any generated HTML files into top_level so they appear as clickable links
            _auto_html = [
                "junit-python.html", "coverage-python.html",
                "junit-node.html", "coverage-node.html",
                "junit-frontend.html", "coverage-frontend.html",
                "junit-frontend-test.html", "coverage-frontend-test.html",
            ]
            for fname in _auto_html:
                if fname not in art.top_level and (Path(art.output_dir) / fname).exists():
                    art.top_level.append(fname)
            art.top_level.sort()
        except Exception as exc:  # never let a parser break the run
            art.parsed = {"error": f"parse_failed: {exc}"}

    if summary.logs_path and Path(summary.logs_path).exists():
        try:
            from ci_report_modules import parse_log_signals
            text = Path(summary.logs_path).read_text(encoding="utf-8", errors="replace")
            summary.log_signals = parse_log_signals(text)
        except ImportError:
            pass


def write_outputs(summary):
    """Render both the HTML summary and the JSON sidecar."""
    descriptions = build_known_artifact_index()

    _enrich_artifact_summaries(summary)

    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(asdict(summary), indent=2),
        encoding="utf-8",
    )

    SUMMARY_HTML.write_text(
        render_summary_html(summary, descriptions),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run_fetch(dry_run=False):
    install_redirect_handler()
    token = os.environ.get("GITHUB_TOKEN")

    if not token and not dry_run:
        print("WARNING: GITHUB_TOKEN is not set. You may get a 403 Forbidden error when downloading logs.")

    try:
        repo, branch = get_git_info()
    except GitHubError as exc:
        print(f"[fetch_ci] {exc}")
        return 1
    print(f"[fetch_ci] Repository : {repo}")
    print(f"[fetch_ci] Branch     : {branch}")

    if dry_run:
        print("[fetch_ci] Dry-run: skipping GitHub calls. Will not write any files.")
        return 0

    try:
        run = latest_workflow_run(repo, branch, token)
    except GitHubError as exc:
        print(f"[fetch_ci] {exc}")
        return 2

    summary = RunSummary(
        repo=repo,
        branch=branch,
        workflow=WORKFLOW_FILE,
        run_id=run["id"],
        run_name=run.get("name") or WORKFLOW_FILE,
        status=run.get("status", "completed"),
        conclusion=run.get("conclusion") or "unknown",
        event=run.get("event", "unknown"),
        head_sha=run.get("head_sha", ""),
        created_at=run.get("created_at", ""),
        updated_at=run.get("updated_at", ""),
        html_url=run.get("html_url", ""),
        actor=(run.get("actor") or {}).get("login"),
        logs_path=str(LOGS_OUT).replace("\\", "/"),
        logs_bytes=0,
    )

    print(f"[fetch_ci] Run #{summary.run_id} ({summary.run_name}) - {summary.conclusion or summary.status}")

    # 1. Logs
    print("[fetch_ci] Downloading workflow logs...")
    try:
        summary.logs_bytes = download_logs(run, token, LOGS_OUT)
    except GitHubError as exc:
        print(f"[fetch_ci] Logs: {exc}")
        summary.logs_bytes = 0

    # 2. Artifacts
    print("[fetch_ci] Querying artifacts...")
    CI_ROOT.mkdir(parents=True, exist_ok=True)
    try:
        artifacts = list_artifacts(repo, summary.run_id, token)
    except GitHubError as exc:
        print(f"[fetch_ci] Artifacts: {exc}")
        artifacts = []

    if not artifacts:
        print("[fetch_ci] No artifacts found for this run.")
    else:
        print(f"[fetch_ci] Found {len(artifacts)} artifact(s):")
        for art in artifacts:
            name = art.get("name", "unnamed")
            size = human_bytes(art.get("size_in_bytes") or 0)
            expired = art.get("expired", False)
            label = f"{name} ({size})" + (" [EXPIRED]" if expired else "")
            print(f"  - {label}")
            if expired:
                summary.artifacts.append(
                    ArtifactSummary(
                        name=name,
                        download_url="",
                        size_bytes=0,
                        size_human=size,
                        file_count=0,
                        top_level=[],
                        status="error",
                        note="Artifact expired before download.",
                    )
                )
                continue
            summary.artifacts.append(download_artifact(repo, art, token))

    # 3. Outputs
    write_outputs(summary)

    # (Enrichment was already called inside write_outputs)

    failed = [a for a in summary.artifacts if a.status != "ok"]
    print()
    print(
        f"[fetch_ci] Done. Run #{summary.run_id} - {len(summary.artifacts)} artifact(s) "
        f"- {summary.total_files()} file(s) - {human_bytes(summary.total_bytes())}"
    )
    print(f"[fetch_ci] Logs  : {summary.logs_path} ({human_bytes(summary.logs_bytes)})")
    print(f"[fetch_ci] HTML  : {SUMMARY_HTML.as_posix()}")
    print(f"[fetch_ci] JSON  : {SUMMARY_JSON.as_posix()}")
    if failed:
        print(f"[fetch_ci] {len(failed)} artifact(s) failed to download; see the HTML for details.")
        return 3
    return 0


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Fetch the latest ci.yml run from GitHub and lay it out for inspection.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve the repo + branch but skip network and file writes.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main():
    args = parse_args()
    try:
        return run_fetch(dry_run=args.dry_run)
    except KeyboardInterrupt:
        print("[fetch_ci] Interrupted.")
        return 130


if __name__ == "__main__":
    sys.exit(main())

