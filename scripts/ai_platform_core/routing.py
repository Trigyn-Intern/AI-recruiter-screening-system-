"""Workflow, skill, and checklist selection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .wizard_defaults import CHECKLIST_MAP, SKILL_MAP, WORKFLOW_MAP


@dataclass(frozen=True)
class Route:
    kind: str
    workflow: str
    skills: list[str]
    checklists: list[str]


@dataclass(frozen=True)
class ExecutionRequest:
    task: str
    project_area: str
    target_location: str
    task_type: str
    priority: str
    update_tests: bool
    update_docs: bool
    security_review: bool
    migration_notes: bool
    additional_notes: str = ""
    options: dict[str, Any] = field(default_factory=dict)


_TASK_TYPE_TO_KIND = {
    "Feature": "feature",
    "Bug Fix": "bug",
    "Refactoring": "refactor",
    "Security": "security",
    "Performance": "performance",
    "Documentation": "documentation",
    "Test Automation": "test automation",
    "Release": "release",
}


def detect_route(request: ExecutionRequest) -> Route:
    kind = _TASK_TYPE_TO_KIND.get(request.task_type, "feature")
    workflow = WORKFLOW_MAP[kind]
    skills = list(SKILL_MAP[kind])
    checklists = list(CHECKLIST_MAP[kind])
    if request.security_review and "security.md" not in checklists:
        checklists.append("security.md")
    return Route(kind=kind, workflow=workflow, skills=skills, checklists=checklists)


def route_summary(route: Route) -> dict[str, Any]:
    return {
        "kind": route.kind,
        "workflow": f".ai/workflows/{route.workflow}",
        "skills": [f".ai/skills/{name}" for name in route.skills],
        "checklists": [f".ai/checklists/{name}" for name in route.checklists],
    }