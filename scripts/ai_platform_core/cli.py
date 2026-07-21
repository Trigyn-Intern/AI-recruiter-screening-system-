"""Command-line orchestrator for the AI platform."""

from __future__ import annotations

import argparse
import json
import time
from typing import Any

from .config import load_project_config
from .context import merge_context
from .executor import CodexRunner
from .history import (
    HistoryPaths,
    make_history_paths,
    write_execution_json,
    write_execution_summary,
)
from .post_checks import run_post_checks
from .prompt_builder import build_final_prompt, write_prompt
from .reports import generate_execution_reports, update_dashboard
from .routing import ExecutionRequest, detect_route, route_summary
from .summary import print_completion, print_summary
from .utils import relative, timestamp
from .wizard import run_wizard
from .wizard_defaults import HISTORY, REPORTS, TEMP


def _one_shot_request(task: str) -> ExecutionRequest:
    return ExecutionRequest(
        task=task,
        project_area="",
        target_location="",
        task_type="Feature",
        priority="Medium",
        update_tests=True,
        update_docs=True,
        security_review=False,
        migration_notes=False,
        additional_notes="",
    )


def _confirm_run() -> bool:
    """Ask the user whether to proceed."""

    while True:
        answer = input("Proceed with execution? (Y/N): ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer Y or N.")


def _confirm_codex() -> bool:
    """Ask the user whether to launch Codex CLI."""

    while True:
        answer = input("Run implementation automatically with Codex CLI? (Y/N): ").strip().lower()
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer Y or N.")


def _request_payload(request: ExecutionRequest) -> dict[str, Any]:
    """Project the wizard request into a serialisable payload."""

    return {
        "project_area": request.project_area,
        "target_location": request.target_location,
        "task_type": request.task_type,
        "priority": request.priority,
        "update_tests": request.update_tests,
        "update_docs": request.update_docs,
        "security_review": request.security_review,
        "migration_notes": request.migration_notes,
        "additional_notes": request.additional_notes,
    }


def _print_completion(
    request: ExecutionRequest,
    paths: HistoryPaths,
    codex_result: dict[str, Any],
    post_checks_result: dict[str, Any],
    status: str,
    duration: float,
) -> None:
    print_completion(request, paths, codex_result, post_checks_result, status, duration)


def _run_pipeline(
    request: ExecutionRequest,
    run_codex: bool,
    codex: CodexRunner | None = None,
) -> int:
    codex = codex or CodexRunner()
    start = time.monotonic()
    route = detect_route(request)
    paths = make_history_paths(HISTORY)

    payload = _request_payload(request)
    context = merge_context(request.task, route, payload, timestamp())
    prompt_text = build_final_prompt(context)
    write_prompt(paths.final_prompt, prompt_text)
    write_prompt(TEMP / "final_prompt.md", prompt_text)

    if run_codex:
        codex_result = codex.run(paths.final_prompt)
    else:
        codex_result = {
            "status": "skipped",
            "reason": "user declined codex execution",
            "returncode": None,
            "duration_seconds": 0.0,
            "stdout_path": None,
            "stderr_path": None,
            "manual_command": codex.manual_command(paths.final_prompt) if codex.is_available() else None,
        }

    post_checks_result = run_post_checks(
        root=REPORTS.parent,
        history_dir=paths.history_dir,
        request=request,
    )

    if codex_result.get("status") == "ok" and post_checks_result.get("status") in {"ok", "skipped"}:
        status = "ok"
    elif codex_result.get("status") == "skipped":
        status = "manual_followup"
    else:
        status = "needs_attention"

    duration = time.monotonic() - start

    write_execution_json(paths, request, route, codex_result, post_checks_result, status)
    write_execution_summary(paths, request, route, codex_result, post_checks_result, status, duration)

    inventory = generate_execution_reports(
        history_dir=paths.history_dir,
        final_prompt_path=paths.final_prompt,
        codex_result=codex_result,
        post_checks_result=post_checks_result,
        duration_seconds=duration,
    )
    update_dashboard(inventory, codex_result, post_checks_result, duration, paths.history_dir)

    _print_completion(request, paths, codex_result, post_checks_result, status, duration)
    return 0


def _handle_codex_gate(codex: CodexRunner) -> bool:
    """Ask the user whether Codex should run; show fallback when missing."""

    if codex.is_available():
        print()
        print("Codex CLI detected.")
        return _confirm_codex()
    print()
    print("Codex CLI not detected.")
    print("Generated prompt is available at:")
    print(f"  {relative(TEMP / 'final_prompt.md')}")
    print("You can manually execute:")
    print(f"  {codex.manual_command(TEMP / 'final_prompt.md')}")
    return False


def _show_summary_and_confirm(request: ExecutionRequest) -> bool:
    """Build the prompt context, print the summary, and ask the user to confirm."""

    route = detect_route(request)
    payload = _request_payload(request)
    context = merge_context(request.task, route, payload, timestamp())
    prompt_text = build_final_prompt(context)
    write_prompt(TEMP / "final_prompt.md", prompt_text)
    print_summary(request, route, prompt_text, context)
    return _confirm_run()


def _run_wizard_flow() -> int:
    """Full interactive flow: wizard -> summary -> confirm -> codex -> checks -> reports."""

    request = run_wizard()
    if not _show_summary_and_confirm(request):
        print("Cancelled by user. No artefacts were created.")
        return 0
    codex = CodexRunner()
    run_codex = _handle_codex_gate(codex)
    return _run_pipeline(request, run_codex=run_codex, codex=codex)


def _run_one_shot(task: str) -> int:
    """One-shot execute path: minimal request, summary, confirm, codex, checks, reports."""

    request = _one_shot_request(task)
    if not _show_summary_and_confirm(request):
        print("Cancelled by user.")
        return 0
    codex = CodexRunner()
    run_codex = _handle_codex_gate(codex)
    return _run_pipeline(request, run_codex=run_codex, codex=codex)


def _route(task: str) -> int:
    route = detect_route(_one_shot_request(task))
    summary = route_summary(route)
    print(f"Workflow: {summary['workflow']}")
    print("Skills:")
    for skill in summary["skills"]:
        print(f"- {skill}")
    print("Checklists:")
    for checklist in summary["checklists"]:
        print(f"- {checklist}")
    return 0


def _config() -> int:
    print(json.dumps(load_project_config(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Local AI Engineering Platform - run the interactive wizard or one-shot tasks.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("report", help="Generate engineering reports")
    sub.add_parser("status", help="Show platform health")
    sub.add_parser("dashboard", help="Show report/workflow/history/learning dashboard")
    sub.add_parser("history", help="List previous executions")
    sub.add_parser("validate", help="Validate required .ai folders and files")
    sub.add_parser("clean", help="Remove temporary files while preserving reports and history")
    sub.add_parser("lessons", help="List learned lessons grouped by category")

    config_cmd = sub.add_parser("config", help="Display parsed project config")
    route_cmd = sub.add_parser("route", help="Route a task")
    route_cmd.add_argument("task")
    execute_cmd = sub.add_parser(
        "execute",
        help="Run the interactive wizard. Pass a task to skip the wizard with a default request.",
    )
    execute_cmd.add_argument("task", nargs="?", default=None)
    learn_cmd = sub.add_parser("learn", help="Store a categorized privacy-screened lesson")
    learn_cmd.add_argument("note")
    search_cmd = sub.add_parser("search", help="Search .ai platform documents")
    search_cmd.add_argument("keyword")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "execute":
        if args.task:
            return _run_one_shot(args.task)
        return _run_wizard_flow()
    if args.command == "route":
        return _route(args.task)
    if args.command == "config":
        return _config()
    print(f"Command '{args.command}' is handled by the legacy bridge in scripts/ai_platform.py.")
    return 0