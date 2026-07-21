"""Generate engineering reports and refresh the dashboard JSON."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import load_project_config
from .utils import read_text, relative, write_json, write_text
from .wizard_defaults import DASHBOARD_JSON, REPORTS

SKIP_PARTS = {
    ".git", ".github", "node_modules", "venv", "__pycache__", "dist", "build",
    ".next", ".idea", ".vscode", "coverage", "reports", "vector_store",
    ".lighthouseci", "zap-reports", "frontend-test",
}

SOURCE_SUFFIXES = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".cs", ".go", ".cpp", ".c",
    ".html", ".css", ".scss", ".sql", ".json", ".yaml", ".yml", ".md", ".txt",
}


def _scan_repo(root: Path) -> tuple[list[Path], list[Path], list[Path]]:
    files: list[Path] = []
    tests: list[Path] = []
    oversized: list[Path] = []
    max_lines = 400
    config = load_project_config()
    quality = config.get("code_quality", {}) if isinstance(config, dict) else {}
    if isinstance(quality, dict):
        try:
            max_lines = int(quality.get("max_file_lines", 400))
        except (TypeError, ValueError):
            max_lines = 400

    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        files.append(path)
        if path.name.startswith("test") or "tests" in path.parts:
            tests.append(path)
        try:
            line_count = sum(1 for _ in path.open("r", encoding="utf-8", errors="ignore"))
        except OSError:
            continue
        if line_count > max_lines:
            oversized.append(path)
    return files, tests, oversized


def _dependency_manifests(root: Path) -> list[Path]:
    names = {"requirements.txt", "package.json", "pyproject.toml", "Pipfile"}
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.name in names
        and not any(part in SKIP_PARTS for part in path.parts)
    ]


def _write(name: str, title: str, body: str) -> Path:
    target = REPORTS / name
    content = f"# {title}\n\n{body.strip()}\n"
    write_text(target, content)
    return target


def generate_execution_reports(
    history_dir: Path,
    final_prompt_path: Path,
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    duration_seconds: float,
) -> dict[str, int]:
    root = REPORTS.parent
    files, tests, oversized = _scan_repo(root)
    manifests = _dependency_manifests(root)

    _write(
        "ai-execution-report.md",
        "Execution Report",
        (
            "## Run\n\n"
            f"- History directory: {relative(history_dir)}\n"
            f"- Final prompt: {relative(final_prompt_path)}\n"
            f"- Duration: {duration_seconds:.2f}s\n"
            f"- Codex status: {codex_result.get('status', 'not run')}\n\n"
            "## Post Checks\n\n"
            f"- Tools: {', '.join(post_checks_result.get('tools', [])) or 'none'}\n"
            f"- Status: {post_checks_result.get('status', 'skipped')}\n\n"
            "## Artifacts\n\n"
            f"- {relative(final_prompt_path)}\n"
            f"- {relative(history_dir / 'execution.json')}\n"
            f"- {relative(history_dir / 'execution_summary.md')}\n"
        ),
    )

    long_rows = "\n".join(f"- {relative(path)}" for path in oversized) or "- none"
    _write(
        "ai-technical-debt-report.md",
        "Technical Debt Report",
        (
            "## Repository Inventory\n\n"
            f"- Source and policy files scanned: **{len(files)}**\n"
            f"- Test modules discovered: **{len(tests)}**\n"
            f"- Files above configured size limit: **{len(oversized)}**\n\n"
            "## Oversized Files\n\n"
            f"{long_rows}\n\n"
            "## Recommended Actions\n\n"
            "1. Split oversized modules by responsibility before adding new features.\n"
            "2. Convert each marker into an owned issue with a target release.\n"
            "3. Keep high-risk parser, auth, and LLM surfaces covered by focused tests.\n"
        ),
    )

    _write(
        "ai-architecture-report.md",
        "Architecture Report",
        (
            "## Current Components\n\n"
            "```mermaid\n"
            "flowchart LR\n"
            "  UI[React recruiter UI] --> AUTH[Express auth API]\n"
            "  UI --> API[FastAPI analyzer]\n"
            "  API --> LLM[Ollama or Gemini]\n"
            "  API --> STORE[FAISS vector store]\n"
            "  QA[React testing dashboard] --> REPORTS[Local reports]\n"
            "```\n\n"
            "## Validation Focus\n\n"
            "- Maintain a documented contract between the React UI, Express auth API, and FastAPI analyzer.\n"
            "- Keep candidate data local unless a hosted provider is explicitly selected.\n"
            "- Version vector-store metadata before modifying persisted structures.\n"
            "- Use deterministic fallback behavior when an LLM provider is unavailable.\n"
        ),
    )

    manifest_rows = "\n".join(f"- {relative(path)}" for path in manifests) or "- none"
    _write(
        "ai-dependency-report.md",
        "Dependency Analysis Report",
        (
            "## Dependency Manifests\n\n"
            f"{manifest_rows}\n\n"
            "## Required Follow-up\n\n"
            "Run Safety, Dependabot, npm audit, and GitHub Advanced Security where available.\n"
        ),
    )

    _write(
        "ai-security-report.md",
        "Security Report",
        (
            "## Required Controls\n\n"
            "- Validate file type, size, and parser errors for every upload.\n"
            "- Keep JWT signing material and AI-provider credentials only in environment variables.\n"
            "- Treat resume text and job descriptions as untrusted prompt input.\n"
            "- Prevent candidate PII from appearing in reports, logs, or external LLM requests without approval.\n"
            "- Run Bandit and dependency scans before pull-request approval.\n"
        ),
    )

    test_names = "\n".join(f"- {relative(path)}" for path in tests[:25]) or "- none"
    _write(
        "ai-quality-report.md",
        "Quality Report",
        (
            "## Inventory\n\n"
            f"- Source/policy files scanned: **{len(files)}**\n"
            f"- Test modules discovered: **{len(tests)}**\n"
            f"- Oversized files: **{len(oversized)}**\n\n"
            "## Test Modules\n\n"
            f"{test_names}\n\n"
            "## Post Check Status\n\n"
            f"- Tools: {', '.join(post_checks_result.get('tools', [])) or 'none'}\n"
            f"- Status: {post_checks_result.get('status', 'skipped')}\n"
        ),
    )

    _write(
        "ai-executive-report.md",
        "Executive Engineering Report",
        (
            "## Engineering Snapshot\n\n"
            "| Measure | Value |\n"
            "| --- | ---: |\n"
            f"| Scanned source and policy files | {len(files)} |\n"
            f"| Test modules | {len(tests)} |\n"
            f"| Files above size guideline | {len(oversized)} |\n"
            f"| Dependency manifests | {len(manifests)} |\n"
            f"| Execution duration | {duration_seconds:.2f}s |\n\n"
            "## Management Decision\n\n"
            "Release readiness requires green automated tests, completed security scans, and an approved pull request.\n"
        ),
    )

    return {
        "files": len(files),
        "tests": len(tests),
        "oversized": len(oversized),
        "manifests": len(manifests),
    }


def update_dashboard(
    inventory: dict[str, int],
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    duration_seconds: float,
    history_dir: Path,
) -> None:
    payload: dict[str, Any] = {
        "generated_at": history_dir.name,
        "history_dir": relative(history_dir),
        "source_files": inventory.get("files", 0),
        "test_modules": inventory.get("tests", 0),
        "oversized_files": inventory.get("oversized", 0),
        "dependency_manifests": inventory.get("manifests", 0),
        "codex_status": codex_result.get("status", "not run"),
        "post_checks_status": post_checks_result.get("status", "skipped"),
        "post_check_tools": post_checks_result.get("tools", []),
        "duration_seconds": round(duration_seconds, 2),
        "reports": sorted(p.name for p in REPORTS.glob("ai-*-report.md")) if REPORTS.exists() else [],
    }
    write_json(DASHBOARD_JSON, payload)