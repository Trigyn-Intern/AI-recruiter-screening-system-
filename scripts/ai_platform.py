"""Backward-compatible entrypoint for the Local AI Engineering Platform."""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import Counter
from pathlib import Path
from datetime import datetime, timezone
UTC = timezone.utc

ROOT = Path(__file__).resolve().parents[1]
AI = ROOT / ".ai"
REPORTS = ROOT / "reports"
TEMP = AI / "temp"
HISTORY = AI / "history"
LEARNING = AI / "learning"

LESSON_CATEGORIES = [
    "Architecture", "Security", "Testing", "Documentation", "Performance",
    "Refactoring", "Deployment", "General",
]

SECRET_PATTERN = re.compile(
    r"(api[_ -]?key|secret|password|passwd|pwd|bearer\s+|jwt|token|resume|candidate|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _timestamp() -> str:
    return _utc_now().strftime("%Y-%m-%d %H:%M UTC")


def _status() -> None:
    from ai_platform_core import load_project_config
    from ai_platform_core.reports import _scan_repo
    from ai_platform_core.wizard_defaults import REPORTS as REPORTS_DIR

    files, tests, _ = _scan_repo(ROOT)
    history = sorted(HISTORY.glob("*/execution.json")) if HISTORY.exists() else []
    reports = sorted(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else []
    config = load_project_config()
    print("Status: healthy")
    print("Project:", config.get("project", {}).get("name", "Unknown"))
    print("Source files:", len(files))
    print("Test modules:", len(tests))
    print("Reports:", len(reports))
    print("Executions:", len(history))
    print("Privacy mode: local-only, no external APIs, no automatic source edits")


def _dashboard() -> None:
    from ai_platform_core.reports import _scan_repo
    from ai_platform_core.wizard_defaults import REPORTS as REPORTS_DIR

    files, tests, _ = _scan_repo(ROOT)
    reports = sorted(REPORTS_DIR.glob("*.md")) if REPORTS_DIR.exists() else []
    executions = sorted(HISTORY.glob("*/execution.json")) if HISTORY.exists() else []
    print("Reports:", len(reports))
    print("Source files:", len(files))
    print("Test modules:", len(tests))
    print("Executions:", len(executions))
    for report in reports:
        print("-", report.relative_to(ROOT).as_posix())


def _list_history() -> None:
    entries = sorted(HISTORY.glob("*/execution.json"), reverse=True) if HISTORY.exists() else []
    if not entries:
        print("No execution history found.")
        return
    for entry in entries:
        data: dict = {}
        try:
            data = json.loads(_read_text(entry) or "{}")
        except json.JSONDecodeError:
            pass
        print(f"- {data.get('timestamp_slug', entry.parent.name)} | {data.get('task', 'unknown')}")


def _validate() -> int:
    required = [
        AI / "project-config.yaml",
        AI / "workflows", AI / "skills", AI / "prompts",
        AI / "knowledge", AI / "templates", AI / "checklists",
        AI / "execution", AI / "learning", AI / "history",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        print("Missing:")
        for item in missing:
            print("-", item)
        return 1
    print("All required .ai folders and files present.")
    return 0


def _clean() -> None:
    if TEMP.exists():
        shutil.rmtree(TEMP)
    TEMP.mkdir(parents=True, exist_ok=True)
    print(f"Cleaned {TEMP.relative_to(ROOT).as_posix()}. Reports and history preserved.")


def _lessons() -> None:
    destination = LEARNING / "lessons-learned.md"
    if not destination.exists():
        print("No lessons recorded yet.")
        return
    pattern = re.compile(r"^- (?P<time>.*? UTC): \[(?P<category>[^\]]+)\] (?P<lesson>.*)$")
    found: list[dict[str, str]] = []
    for line in _read_text(destination).splitlines():
        match = pattern.match(line.strip())
        if match:
            found.append(match.groupdict())
    counts = Counter(item["category"] for item in found)
    for category in LESSON_CATEGORIES:
        print(f"- {category}: {counts.get(category, 0)}")


def _record_lesson(note: str) -> None:
    lower = note.lower()
    keywords = {
        "Architecture": ("architecture", "design", "boundary", "contract", "module"),
        "Security": ("security", "auth", "jwt", "xss", "csrf", "secret", "prompt injection"),
        "Testing": ("test", "pytest", "playwright", "coverage", "mock", "regression"),
        "Documentation": ("doc", "readme", "adr", "comment", "guide"),
        "Performance": ("performance", "latency", "speed", "cache", "timeout", "memory"),
        "Refactoring": ("refactor", "cleanup", "duplicate", "complexity", "split"),
        "Deployment": ("deploy", "release", "ci", "cd", "pipeline", "production", "staging"),
    }
    category = "General"
    for name, words in keywords.items():
        if any(word in lower for word in words):
            category = name
            break
    cleaned = SECRET_PATTERN.sub("[REDACTED]", note)
    destination = LEARNING / "lessons-learned.md"
    line = f"- {_timestamp()}: [{category}] {cleaned}\n"
    with destination.open("a", encoding="utf-8") as handle:
        handle.write(line)
    print(f"Recorded [{category}] lesson.")


def _search(keyword: str) -> None:
    folders = [AI / "workflows", AI / "prompts", AI / "knowledge", AI / "templates", LEARNING]
    needle = keyword.lower()
    found = False
    for folder in folders:
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*.md")):
            for number, line in enumerate(_read_text(path).splitlines(), start=1):
                if needle in line.lower():
                    print(f"{path.relative_to(ROOT).as_posix()}:{number}: {line.strip()[:180]}")
                    found = True
    if not found:
        print("No matches found.")


def main() -> int:
    from ai_platform_core.cli import build_parser as core_build_parser, main as core_main

    if len(sys.argv) < 2:
        core_build_parser().print_help()
        return 0

    command = sys.argv[1]
    if command in {"execute", "route", "config"}:
        return core_main(sys.argv[1:])

    if command == "report":
        from ai_platform_core.reports import generate_execution_reports, update_dashboard
        from ai_platform_core.wizard_defaults import HISTORY as HISTORY_DIR
        last = sorted(HISTORY_DIR.glob("*"), reverse=True)
        history_dir = last[0] if last else HISTORY_DIR
        inventory = generate_execution_reports(
            history_dir=history_dir,
            final_prompt_path=history_dir / "final_prompt.md",
            codex_result={"status": "not run"},
            post_checks_result={"status": "skipped", "tools": []},
            duration_seconds=0.0,
        )
        update_dashboard(
            inventory, {"status": "not run"},
            {"status": "skipped", "tools": []}, 0.0, history_dir,
        )
        return 0
    if command == "status":
        _status()
        return 0
    if command == "dashboard":
        _dashboard()
        return 0
    if command == "history":
        _list_history()
        return 0
    if command == "validate":
        return _validate()
    if command == "clean":
        _clean()
        return 0
    if command == "lessons":
        _lessons()
        return 0
    if command == "learn":
        if len(sys.argv) < 3:
            print("Usage: ai_platform.py learn <note>")
            return 1
        _record_lesson(" ".join(sys.argv[2:]))
        return 0
    if command == "search":
        if len(sys.argv) < 3:
            print("Usage: ai_platform.py search <keyword>")
            return 1
        _search(" ".join(sys.argv[2:]))
        return 0

    print(f"Unknown command: {command}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
