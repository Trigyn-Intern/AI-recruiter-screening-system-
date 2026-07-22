"""Core package for the local AI engineering platform."""

from .config import load_project_config, redact_secrets
from .context import merge_context
from .executor import CodexRunner
from .history import (
    HistoryPaths,
    make_history_paths,
    write_execution_json,
    write_execution_summary,
)
from .post_checks import run_post_checks
from .prompt_builder import build_final_prompt
from .reports import generate_execution_reports, update_dashboard
from .routing import ExecutionRequest, Route, detect_route
from .summary import print_completion, print_summary
from .utils import (
    ensure_directory,
    read_text,
    relative,
    timestamp,
    timestamp_slug,
    utc_now,
    write_json,
    write_text,
)
from .wizard import run_wizard

__all__ = [
    "utc_now",
    "timestamp",
    "timestamp_slug",
    "relative",
    "ensure_directory",
    "read_text",
    "write_text",
    "write_json",
    "load_project_config",
    "redact_secrets",
    "Route",
    "ExecutionRequest",
    "detect_route",
    "merge_context",
    "build_final_prompt",
    "HistoryPaths",
    "make_history_paths",
    "write_execution_json",
    "write_execution_summary",
    "CodexRunner",
    "run_post_checks",
    "generate_execution_reports",
    "update_dashboard",
    "run_wizard",
    "print_summary",
    "print_completion",
]
