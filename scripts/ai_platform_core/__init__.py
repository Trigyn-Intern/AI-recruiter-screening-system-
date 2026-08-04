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
    "CodexRunner",
    "ExecutionRequest",
    "HistoryPaths",
    "Route",
    "build_final_prompt",
    "detect_route",
    "ensure_directory",
    "generate_execution_reports",
    "load_project_config",
    "make_history_paths",
    "merge_context",
    "print_completion",
    "print_summary",
    "read_text",
    "redact_secrets",
    "relative",
    "run_post_checks",
    "run_wizard",
    "timestamp",
    "timestamp_slug",
    "update_dashboard",
    "utc_now",
    "write_execution_json",
    "write_execution_summary",
    "write_json",
    "write_text",
]
