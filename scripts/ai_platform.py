"""Local, privacy-safe operations for the repository AI framework.

This script deliberately does not send source code, resumes, or secrets to an external
service. It turns the policies in .ai into reproducible local reports and provides the
same workflow routing used by the multi-agent platform documentation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
LEARNING = ROOT / ".ai" / "learning"
SKIP_PARTS = {".git", "node_modules", "venv", "dist", "build", "__pycache__", "reports", "vector_store"}
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".md", ".yml", ".yaml"}


def source_files() -> list[Path]:
    return [
        path for path in ROOT.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
        and not any(part in SKIP_PARTS for part in path.relative_to(ROOT).parts)
    ]


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def count_lines(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="ignore").splitlines())
    except OSError:
        return 0


def markdown_report(title: str, body: str) -> str:
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return f"# {title}\n\nGenerated locally: {timestamp}\n\n{body.rstrip()}\n"


def write_report(name: str, title: str, body: str) -> Path:
    REPORTS.mkdir(exist_ok=True)
    destination = REPORTS / name
    destination.write_text(markdown_report(title, body), encoding="utf-8")
    return destination


def generate_reports() -> None:
    files = source_files()
    line_counts = {relative(path): count_lines(path) for path in files}
    long_files = sorted(((name, count) for name, count in line_counts.items() if count > 400), key=lambda row: row[1], reverse=True)
    marker_hits: list[str] = []
    duplicate_lines: Counter[str] = Counter()
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for number, line in enumerate(text.splitlines(), start=1):
            if re.search(r"\b(TODO|FIXME|HACK)\b", line, re.IGNORECASE):
                marker_hits.append(f"- `{relative(path)}:{number}` — {line.strip()[:180]}")
            normalized = line.strip()
            if len(normalized) >= 80 and not normalized.startswith(("#", "//", "*")):
                duplicate_lines[normalized] += 1

    dependency_files = [path for path in (ROOT / "requirements.txt", ROOT / "frontend" / "package.json", ROOT / "backend" / "package.json", ROOT / "frontend-test" / "package.json") if path.exists()]
    test_files = [path for path in files if "/tests/" in f"/{relative(path)}" and path.name.startswith("test_")]
    test_names = "\n".join(f"- `{relative(path)}`" for path in test_files) or "- No test files found."
    long_file_rows = "\n".join(f"- `{name}` — {count} lines" for name, count in long_files[:20]) or "- No files exceed the configured 400-line limit."
    marker_rows = "\n".join(marker_hits[:50]) or "- No TODO/FIXME/HACK markers found in scanned source files."
    duplicate_rows = "\n".join(f"- Appears {count} times: `{line[:150]}`" for line, count in duplicate_lines.most_common(15) if count > 1) or "- No repeated long source lines detected."

    write_report("ai-technical-debt-report.md", "Technical Debt Report", f"""## Repository Inventory

- Source and policy files scanned: **{len(files)}**
- Test modules discovered: **{len(test_files)}**
- Files above configured size limit: **{len(long_files)}**

## Oversized Files

{long_file_rows}

## Maintenance Markers

{marker_rows}

## Recommended Actions

1. Split oversized modules by responsibility before adding new features.
2. Convert each marker into an owned issue with a target release.
3. Keep the deleted scoring-cache test under review until its replacement is committed.
""")

    write_report("ai-architecture-report.md", "Architecture Report", """## Current Components

```mermaid
flowchart LR
  UI[React recruiter UI] --> AUTH[Express auth API]
  UI --> API[FastAPI analyzer]
  API --> LLM[Ollama or Gemini]
  API --> STORE[FAISS vector store]
  QA[React testing dashboard] --> REPORTS[Local reports]
```

## Validation Focus

- Maintain a documented contract between the React UI, Express auth API, and FastAPI analyzer.
- Keep candidate data local unless a hosted provider is explicitly selected.
- Version vector-store metadata before modifying persisted structures.
- Use deterministic fallback behavior when an LLM provider is unavailable.
""")

    write_report("ai-dependency-report.md", "Dependency Analysis Report", "## Dependency Manifests\n\n" + "\n".join(f"- `{relative(path)}`" for path in dependency_files) + "\n\n## Required Follow-up\n\nRun the Safety dependency scan in CI and locally. Keep Node lockfiles committed and use `npm ci` in CI.")

    write_report("ai-security-report.md", "Security Report", """## Required Controls

- Validate file type, size, and parser errors for every upload.
- Keep JWT signing material and AI-provider credentials only in environment variables.
- Treat resume text and job descriptions as untrusted prompt input.
- Prevent candidate PII from appearing in reports, logs, or external LLM requests without approval.
- Run Bandit and Safety before pull-request approval.

## Current Local Evidence

Bandit is configured as a high-severity quality gate. Safety must be installed in the local virtual environment before its local gate can run.
""")

    write_report("ai-quality-report.md", "Quality Report", f"""## Inventory

- Source/policy files scanned: **{len(files)}**
- Test modules discovered: **{len(test_files)}**
- Oversized files: **{len(long_files)}**

## Test Modules

{test_names}

## Duplicate-Line Heuristic

{duplicate_rows}

## Gate Status

Run `python scripts/ai_platform.py report` after changes, then run pytest, Bandit, Safety, frontend build, testing-dashboard build, and Lighthouse as applicable.
""")

    write_report("ai-executive-report.md", "Executive Engineering Report", f"""## Engineering Snapshot

| Measure | Value |
| --- | ---: |
| Scanned source and policy files | {len(files)} |
| Test modules | {len(test_files)} |
| Files above size guideline | {len(long_files)} |
| Dependency manifests | {len(dependency_files)} |

## Management Decision

Release readiness requires green automated tests, completed security scans, and an approved pull request. The dashboard provides local evidence; GitHub Actions remains the merge authority.
""")

    summary = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_files": len(files),
        "test_modules": len(test_files),
        "oversized_files": len(long_files),
        "reports": [path.name for path in sorted(REPORTS.glob("ai-*-report.md"))],
    }
    (REPORTS / "ai-dashboard.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def route_task(task: str) -> None:
    lower = task.lower()
    if any(word in lower for word in ("security", "auth", "jwt", "upload", "privacy", "llm")):
        workflow, skills = "bug-fix.workflow.md", ["security.skill.md", "unit-testing.skill.md"]
    elif any(word in lower for word in ("release", "deploy", "version")):
        workflow, skills = "release.workflow.md", ["code-review.skill.md", "documentation.skill.md"]
    elif any(word in lower for word in ("doc", "readme", "adr")):
        workflow, skills = "documentation.workflow.md", ["documentation.skill.md"]
    elif any(word in lower for word in ("bug", "fix", "error", "failure")):
        workflow, skills = "bug-fix.workflow.md", ["unit-testing.skill.md", "code-review.skill.md"]
    else:
        workflow, skills = "feature-development.workflow.md", ["coding-standards.skill.md", "unit-testing.skill.md", "code-review.skill.md"]
    print("Workflow:", f".ai/workflows/{workflow}")
    print("Skills:")
    for skill in skills:
        print("-", f".ai/skills/{skill}")
    print("Checks:")
    print("- .ai/checklists/coding.md")
    print("- .ai/checklists/testing.md")
    if "security.skill.md" in skills:
        print("- .ai/checklists/security.md")


def record_learning(note: str) -> None:
    if re.search(r"(api[_ -]?key|password|token|@|resume|candidate)", note, re.IGNORECASE):
        raise SystemExit("Refusing to store potentially sensitive information in the learning log.")
    destination = LEARNING / "lessons-learned.md"
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(f"\n- {timestamp}: {note.strip()}\n")
    print(f"Recorded learning note in {relative(destination)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Operate the local AI engineering platform.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("report", help="Generate repository-wide reports.")
    route = subparsers.add_parser("route", help="Route a task to workflow and skills.")
    route.add_argument("task")
    learn = subparsers.add_parser("learn", help="Record a non-sensitive lesson.")
    learn.add_argument("note")
    args = parser.parse_args()
    if args.command == "report":
        generate_reports()
    elif args.command == "route":
        route_task(args.task)
    else:
        record_learning(args.note)


if __name__ == "__main__":
    main()
