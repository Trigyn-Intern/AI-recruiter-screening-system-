"""Persist execution artefacts under .ai/history/<timestamp>/."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .routing import ExecutionRequest, Route
from .utils import ensure_directory, relative, timestamp_slug, write_json, write_text


@dataclass(frozen=True)
class HistoryPaths:
    history_dir: Path
    final_prompt: Path
    execution_json: Path
    execution_summary: Path
    codex_stdout: Path
    codex_stderr: Path
    post_checks: Path


def make_history_paths(history_root: Path) -> HistoryPaths:
    history_dir = ensure_directory(history_root / timestamp_slug())
    return HistoryPaths(
        history_dir=history_dir,
        final_prompt=history_dir / "final_prompt.md",
        execution_json=history_dir / "execution.json",
        execution_summary=history_dir / "execution_summary.md",
        codex_stdout=history_dir / "codex_stdout.log",
        codex_stderr=history_dir / "codex_stderr.log",
        post_checks=history_dir / "post_checks.json",
    )


def write_execution_json(
    paths: HistoryPaths,
    request: ExecutionRequest,
    route: Route,
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    status: str,
) -> None:
    payload: dict[str, Any] = {
        "timestamp_slug": paths.history_dir.name,
        "task": request.task,
        "request": {
            "project_area": request.project_area,
            "target_location": request.target_location,
            "task_type": request.task_type,
            "priority": request.priority,
            "update_tests": request.update_tests,
            "update_docs": request.update_docs,
            "security_review": request.security_review,
            "migration_notes": request.migration_notes,
            "additional_notes": request.additional_notes,
        },
        "route": {
            "kind": route.kind,
            "workflow": f".ai/workflows/{route.workflow}",
            "skills": [f".ai/skills/{name}" for name in route.skills],
            "checklists": [f".ai/checklists/{name}" for name in route.checklists],
        },
        "artifacts": {
            "history_dir": relative(paths.history_dir),
            "final_prompt": relative(paths.final_prompt),
            "execution_json": relative(paths.execution_json),
            "execution_summary": relative(paths.execution_summary),
        },
        "codex": codex_result,
        "post_checks": post_checks_result,
        "status": status,
    }
    write_json(paths.execution_json, payload)


def write_execution_summary(
    paths: HistoryPaths,
    request: ExecutionRequest,
    route: Route,
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    status: str,
    duration_seconds: float,
) -> None:
    skills = ", ".join(route.skills) or "none"
    checklists = ", ".join(route.checklists) or "none"
    summary = f"""# Execution Summary

Run: {paths.history_dir.name}

- Task: {request.task}
- Project Area: {request.project_area}
- Target Location: {request.target_location}
- Task Type: {request.task_type}
- Priority: {request.priority}
- Workflow: .ai/workflows/{route.workflow}
- Skills: {skills}
- Checklists: {checklists}
- Update Tests: {request.update_tests}
- Update Docs: {request.update_docs}
- Security Review: {request.security_review}
- Migration Notes: {request.migration_notes}

## Codex

- Status: {codex_result.get("status", "not run")}
- Return Code: {codex_result.get("returncode", "n/a")}
- Duration: {codex_result.get("duration_seconds", 0):.2f}s

## Post Checks

- Tools: {", ".join(post_checks_result.get("tools", [])) or "none"}
- Status: {post_checks_result.get("status", "skipped")}

## Final Status

- Status: {status}
- Total Duration: {duration_seconds:.2f}s

## Privacy

- Local-only execution. No external APIs. No source-code changes by the platform.
"""
    write_text(paths.execution_summary, summary)
