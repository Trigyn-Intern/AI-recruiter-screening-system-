"""Load and merge all local orchestration context."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from .config import load_project_config
from .routing import Route
from .utils import read_text, relative
from .wizard_defaults import CHECKLISTS, KNOWLEDGE, PROMPTS, SKILLS, TEMPLATES, WORKFLOWS


def _load_document(path: Path) -> dict[str, str]:
    return {"path": relative(path), "content": read_text(path)}


def _load_named(folder: Path, names: Iterable[str]) -> list[dict[str, str]]:
    return [_load_document(folder / name) for name in names if (folder / name).exists()]


def _load_all(folder: Path, pattern: str = "*.md") -> list[dict[str, str]]:
    if not folder.exists():
        return []
    return [_load_document(path) for path in sorted(folder.glob(pattern)) if path.is_file()]


def merge_context(
    task: str,
    route: Route,
    request_payload: dict[str, Any],
    timestamp_str: str,
) -> dict[str, Any]:
    return {
        "generated_at": timestamp_str,
        "privacy_mode": {
            "local_only": True,
            "modifies_source_code": False,
            "external_api_calls": False,
            "internet_required": False,
        },
        "task": task,
        "request": request_payload,
        "project_config": load_project_config(),
        "route": {
            "kind": route.kind,
            "workflow": f".ai/workflows/{route.workflow}",
            "skills": [f".ai/skills/{name}" for name in route.skills],
            "checklists": [f".ai/checklists/{name}" for name in route.checklists],
        },
        "workflow": _load_document(WORKFLOWS / route.workflow),
        "skills": _load_named(SKILLS, route.skills),
        "prompts": _load_all(PROMPTS),
        "templates": _load_all(TEMPLATES),
        "knowledge": _load_all(KNOWLEDGE),
        "checklists": _load_named(CHECKLISTS, route.checklists),
    }