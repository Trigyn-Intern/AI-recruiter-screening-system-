"""Pretty terminal output for the AI platform."""

from __future__ import annotations

from typing import Any

from .routing import ExecutionRequest, Route, route_summary
from .utils import relative
from .wizard_defaults import REPORTS


def print_summary(
    request: ExecutionRequest,
    route: Route,
    prompt_text: str,
    context: dict[str, Any],
) -> None:
    """Print the pre-execution summary and wait for user confirmation."""

    summary = route_summary(route)
    print()
    print("=============================")
    print("EXECUTION SUMMARY")
    print("=============================")
    print(f"Task: {request.task}")
    print(f"Project Area: {request.project_area or 'unspecified'}")
    print(f"Target: {request.target_location or 'unspecified'}")
    print(f"Task Type: {request.task_type}")
    print(f"Priority: {request.priority}")
    print(f"Workflow: {summary['workflow']}")
    print(f"Skills: {', '.join(summary['skills']) or 'none'}")
    print(f"Checklists: {', '.join(summary['checklists']) or 'none'}")
    print(f"Update Tests: {request.update_tests}")
    print(f"Update Docs: {request.update_docs}")
    print(f"Security Review: {request.security_review}")
    print(f"Migration Notes: {request.migration_notes}")
    print()
    print(f"Prompt Size: {len(prompt_text)} characters")
    print(f"Knowledge Files Loaded: {len(context.get('knowledge', []))}")
    print(f"Templates Loaded: {len(context.get('templates', []))}")
    print(f"Skills Loaded: {len(context.get('skills', []))}")
    print(f"Checklists Loaded: {len(context.get('checklists', []))}")
    print()


def print_completion(
    request: ExecutionRequest,
    paths: Any,
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    status: str,
    duration_seconds: float,
) -> None:
    """Print the final execution screen."""

    print()
    print("=============================")
    print("EXECUTION COMPLETE")
    print("=============================")
    print(f"Task: {request.task}")
    print(f"Status: {status}")
    print(f"Prompt: {relative(paths.final_prompt)}")
    print(f"History: {relative(paths.history_dir)}")
    print(f"Reports: {', '.join(sorted(p.name for p in REPORTS.glob('ai-*-report.md'))) or 'none'}")
    print(f"Codex Status: {codex_result.get('status', 'not run')}")
    print(f"Tests: {post_checks_result.get('status', 'skipped')}")
    print(f"Security: {'enabled' if request.security_review else 'skipped'}")
    print(f"Build: {'ran' if 'npm-build' in post_checks_result.get('tools', []) else 'skipped'}")
    print(f"Execution Time: {duration_seconds:.2f}s")
    print()