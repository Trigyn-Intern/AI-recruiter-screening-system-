"""Run pytest, bandit, safety, frontend build, and lighthouse conditionally."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .routing import ExecutionRequest
from .utils import relative


@dataclass(frozen=True)
class ToolResult:
    tool: str
    command: list[str]
    returncode: int | None
    duration_seconds: float
    status: str
    output_path: Path | None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool": self.tool,
            "command": self.command,
            "returncode": self.returncode,
            "duration_seconds": self.duration_seconds,
            "status": self.status,
            "output_path": str(self.output_path) if self.output_path else None,
            "error": self.error,
        }


def _run(tool: str, args: list[str], cwd: Path, output: Path, timeout: int = 600) -> ToolResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        return ToolResult(
            tool=tool,
            command=args,
            returncode=None,
            duration_seconds=round(time.monotonic() - start, 2),
            status="missing",
            output_path=None,
            error=str(exc),
        )
    except subprocess.TimeoutExpired as exc:
        return ToolResult(
            tool=tool,
            command=args,
            returncode=None,
            duration_seconds=round(time.monotonic() - start, 2),
            status="timeout",
            output_path=None,
            error=str(exc),
        )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        (completed.stdout or "") + "\n" + (completed.stderr or ""),
        encoding="utf-8",
        errors="ignore",
    )
    return ToolResult(
        tool=tool,
        command=args,
        returncode=completed.returncode,
        duration_seconds=round(time.monotonic() - start, 2),
        status="ok" if completed.returncode == 0 else "failed",
        output_path=output,
    )


def run_post_checks(
    root: Path,
    history_dir: Path,
    request: ExecutionRequest,
) -> dict[str, Any]:
    results: list[ToolResult] = []
    area = (request.project_area or "").lower()
    needs_frontend = "frontend" in area or "full stack" in area
    needs_backend = any(token in area for token in ("backend", "api", "database", "full stack"))

    if needs_backend or True:
        if shutil.which("pytest"):
            results.append(
                _run("pytest", ["python", "-m", "pytest", "-q"], root, history_dir / "pytest.log")
            )
        if shutil.which("bandit"):
            results.append(
                _run("bandit", ["bandit", "-r", "backend", "-q"], root, history_dir / "bandit.log")
            )
        if shutil.which("safety"):
            results.append(
                _run(
                    "safety",
                    ["safety", "check", "-r", "requirements.txt", "--output", "text"],
                    root,
                    history_dir / "safety.log",
                )
            )

    if needs_frontend:
        frontend_dir = root / "frontend"
        if frontend_dir.exists() and (frontend_dir / "package.json").exists():
            npm = shutil.which("npm") or "npm"
            results.append(
                _run("npm-build", [npm, "run", "build"], frontend_dir, history_dir / "npm_build.log", timeout=1200)
            )
            if shutil.which("npx"):
                results.append(
                    _run(
                        "lighthouse",
                        ["npx", "--yes", "lhci", "autorun", "--collect.numberOfRuns=1"],
                        root,
                        history_dir / "lighthouse.log",
                        timeout=1200,
                    )
                )

    overall = (
        "ok"
        if results and all(r.status == "ok" for r in results)
        else ("skipped" if not results else "failed")
    )

    return {
        "tools": [r.tool for r in results],
        "results": [r.to_dict() for r in results],
        "status": overall,
    }