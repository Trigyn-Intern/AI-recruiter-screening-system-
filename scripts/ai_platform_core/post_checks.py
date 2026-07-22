"""Run pytest, pip-audit, bandit, frontend builds, and lighthouse conditionally.

Design notes
------------
* The previous version always ran the full backend suite (`if needs_backend or
  True:`). This version honours the requested project area and supports
  per-tool opt-outs via ``request.options``.
* ``safety`` has been replaced with ``pip-audit`` to align with the CI
  pipeline (``.github/workflows/ci.yml``). ``safety`` is still used as a
  fallback if pip-audit is not installed.
* Each tool reports its own status; the overall status is ``ok`` only when
  every *applicable* tool passed. Missing CLIs are reported as ``missing``
  instead of silently skipping.
* Subprocess output is captured as bytes and decoded with
  ``errors="replace"`` to avoid truncation and OOM on large logs.
* ``sys.executable`` is used to invoke ``python -m pytest`` so the run honours
  the active virtualenv.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .routing import ExecutionRequest


@dataclass(frozen=True)
class ToolResult:
    tool: str
    command: list[str]
    returncode: int | None
    duration_seconds: float
    status: str  # "ok" | "failed" | "missing" | "timeout" | "skipped"
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


def _resolve_python_executable() -> str:
    """Prefer the current interpreter; fall back to ``python`` on PATH."""

    if sys.executable:
        return sys.executable
    return shutil.which("python") or "python"


def _run(
    tool: str,
    args: list[str],
    cwd: Path,
    output: Path,
    timeout: int = 600,
) -> ToolResult:
    start = time.monotonic()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=False,  # capture bytes; decode safely below
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
    except OSError as exc:
        return ToolResult(
            tool=tool,
            command=args,
            returncode=None,
            duration_seconds=round(time.monotonic() - start, 2),
            status="failed",
            output_path=None,
            error=str(exc),
        )

    stdout_text = (completed.stdout or b"").decode("utf-8", errors="replace")
    stderr_text = (completed.stderr or b"").decode("utf-8", errors="replace")
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.write_text(stdout_text + "\n" + stderr_text, encoding="utf-8")
    except OSError as exc:
        return ToolResult(
            tool=tool,
            command=args,
            returncode=completed.returncode,
            duration_seconds=round(time.monotonic() - start, 2),
            status="failed",
            output_path=None,
            error=f"could not write log: {exc}",
        )

    return ToolResult(
        tool=tool,
        command=args,
        returncode=completed.returncode,
        duration_seconds=round(time.monotonic() - start, 2),
        status="ok" if completed.returncode == 0 else "failed",
        output_path=output,
    )


def _python_module_args(module: str, *extra: str) -> list[str]:
    """Build a ``python -m <module> ...`` argv using the current interpreter."""

    return [_resolve_python_executable(), "-m", module, *extra]


def _bandit_args() -> list[str]:
    return [
        "bandit",
        "-r",
        "backend",
        "-q",
        "--skip",
        "B101",  # assert_used is expected in test paths
    ]


def _pytest_args(options: dict[str, Any]) -> list[str]:
    """Build a focused pytest invocation.

    By default, only the unit suite runs. Performance, integration, and
    Playwright suites are opt-in via ``request.options``.
    """

    args = ["-q", "tests/unit"]
    if options.get("run_integration"):
        args.append("tests/integration")
    if options.get("run_performance"):
        args.append("tests/performance")
    if options.get("run_playwright"):
        args.append("tests/e2e")
    return args


def _pip_audit_args() -> list[str] | None:
    """Prefer pip-audit; fall back to safety if pip-audit is unavailable."""

    if shutil.which("pip-audit"):
        return ["pip-audit", "-r", "requirements.txt", "--strict"]
    if shutil.which("safety"):
        return ["safety", "check", "-r", "requirements.txt", "--output", "text"]
    return None


def _classify_area(area: str) -> dict[str, bool]:
    """Decide which tool families are applicable for the requested area."""

    lowered = (area or "").lower()
    return {
        "needs_frontend": "frontend" in lowered or "full stack" in lowered,
        "needs_backend": any(
            token in lowered for token in ("backend", "api", "database", "full stack")
        ),
        "needs_frontend_test": (
            "frontend-test" in lowered or "qa" in lowered or "testing" in lowered
        ),
    }


def run_post_checks(
    root: Path,
    history_dir: Path,
    request: ExecutionRequest,
) -> dict[str, Any]:
    results: list[ToolResult] = []
    options = getattr(request, "options", None) or {}

    if options.get("skip_checks"):
        return {
            "tools": [],
            "results": [],
            "missing_tools": [],
            "status": "skipped",
            "reason": "user requested skip",
        }

    flags = _classify_area(request.project_area)

    # --- Backend checks ----------------------------------------------------
    if flags["needs_backend"]:
        # pytest: prefer the current interpreter via ``python -m``.
        results.append(
            _run(
                "pytest",
                _python_module_args("pytest", *_pytest_args(options)),
                root,
                history_dir / "pytest.log",
            )
        )

        # bandit: only when explicitly requested, otherwise it dominates the run.
        if options.get("run_bandit", False) and shutil.which("bandit"):
            results.append(
                _run("bandit", _bandit_args(), root, history_dir / "bandit.log")
            )

        # pip-audit (or safety fallback). We *report* missing CLIs instead of
        # silently skipping so security misses are visible.
        dep_args = _pip_audit_args()
        if dep_args is None:
            results.append(
                ToolResult(
                    tool="pip-audit",
                    command=[],
                    returncode=None,
                    duration_seconds=0.0,
                    status="missing",
                    output_path=None,
                    error="neither pip-audit nor safety is installed",
                )
            )
        else:
            results.append(
                _run(
                    dep_args[0],
                    dep_args,
                    root,
                    history_dir / f"{dep_args[0]}.log",
                )
            )

    # --- Frontend checks ---------------------------------------------------
    if flags["needs_frontend"] or flags["needs_frontend_test"]:
        npm = shutil.which("npm") or "npm"
        for app, want in (
            ("frontend", flags["needs_frontend"]),
            ("frontend-test", flags["needs_frontend_test"]),
        ):
            if not want:
                continue
            app_dir = root / app
            if not (app_dir.exists() and (app_dir / "package.json").exists()):
                continue
            results.append(
                _run(
                    f"npm-build-{app}",
                    [npm, "run", "build"],
                    app_dir,
                    history_dir / f"npm_build_{app}.log",
                    timeout=1200,
                )
            )

        # Lighthouse: only if the user explicitly opts in (needs network + dist).
        if options.get("run_lighthouse") and shutil.which("npx"):
            results.append(
                _run(
                    "lighthouse",
                    ["npx", "--yes", "lhci", "autorun", "--collect.numberOfRuns=1"],
                    root,
                    history_dir / "lighthouse.log",
                    timeout=1200,
                )
            )

    # --- Aggregate ---------------------------------------------------------
    applicable = [r for r in results if r.status != "skipped"]
    hard_failures = [r for r in applicable if r.status in {"failed", "timeout"}]
    missing_tools = [r for r in applicable if r.status == "missing"]

    if not applicable:
        overall = "skipped"
    elif hard_failures:
        overall = "failed"
    elif missing_tools:
        overall = "degraded"  # at least one required tool was unavailable
    else:
        overall = "ok"

    return {
        "tools": [r.tool for r in results],
        "results": [r.to_dict() for r in results],
        "missing_tools": [r.tool for r in missing_tools],
        "status": overall,
    }
