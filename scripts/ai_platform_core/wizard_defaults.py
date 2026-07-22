"""Constants, paths, and enums for the AI platform."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AI = ROOT / ".ai"

WORKFLOWS = AI / "workflows"
SKILLS = AI / "skills"
PROMPTS = AI / "prompts"
KNOWLEDGE = AI / "knowledge"
TEMPLATES = AI / "templates"
CHECKLISTS = AI / "checklists"
EXECUTION = AI / "execution"
LEARNING = AI / "learning"
HISTORY = AI / "history"
TEMP = AI / "temp"
CONFIG = AI / "project-config.yaml"

REPORTS = ROOT / "reports"
DASHBOARD_JSON = REPORTS / "ai-dashboard.json"

PROJECT_AREAS: dict[str, tuple[str, str]] = {
    "1": ("Frontend", "frontend/"),
    "2": ("Backend", "backend/"),
    "3": ("Full Stack", ""),
    "4": ("API", "api.py"),
    "5": ("Database", "backend/data/"),
    "6": ("DevOps", ".github/"),
    "7": ("Testing", "tests/"),
    "8": ("Documentation", "docs/"),
}

TASK_TYPES: dict[str, str] = {
    "1": "Feature",
    "2": "Bug Fix",
    "3": "Refactoring",
    "4": "Security",
    "5": "Performance",
    "6": "Documentation",
    "7": "Test Automation",
    "8": "Release",
}

PRIORITIES = ["Low", "Medium", "High", "Critical"]

PRIORITY_CHOICES: dict[str, str] = {str(i + 1): p for i, p in enumerate(PRIORITIES)}

WORKFLOW_MAP = {
    "feature": "feature-development.workflow.md",
    "bug": "bug-fix.workflow.md",
    "refactor": "refactoring.workflow.md",
    "hotfix": "hotfix.workflow.md",
    "security": "bug-fix.workflow.md",
    "performance": "refactoring.workflow.md",
    "documentation": "documentation.workflow.md",
    "test automation": "feature-development.workflow.md",
    "release": "release.workflow.md",
}

SKILL_MAP = {
    "feature": [
        "coding-standards.skill.md",
        "unit-testing.skill.md",
        "code-review.skill.md",
    ],
    "bug": ["unit-testing.skill.md", "code-review.skill.md", "security.skill.md"],
    "refactor": [
        "coding-standards.skill.md",
        "unit-testing.skill.md",
        "code-review.skill.md",
    ],
    "hotfix": ["security.skill.md", "unit-testing.skill.md", "code-review.skill.md"],
    "security": [
        "security.skill.md",
        "coding-standards.skill.md",
        "unit-testing.skill.md",
    ],
    "performance": [
        "coding-standards.skill.md",
        "unit-testing.skill.md",
        "code-review.skill.md",
    ],
    "documentation": ["documentation.skill.md"],
    "test automation": [
        "unit-testing.skill.md",
        "coding-standards.skill.md",
        "code-review.skill.md",
    ],
    "release": ["documentation.skill.md", "code-review.skill.md", "security.skill.md"],
}

CHECKLIST_MAP = {
    "feature": ["coding.md", "testing.md", "documentation.md"],
    "bug": ["coding.md", "testing.md", "security.md"],
    "refactor": ["coding.md", "testing.md"],
    "hotfix": ["coding.md", "testing.md", "security.md"],
    "security": ["coding.md", "testing.md", "security.md"],
    "performance": ["coding.md", "testing.md"],
    "documentation": ["documentation.md"],
    "test automation": ["testing.md", "coding.md"],
    "release": ["coding.md", "testing.md", "documentation.md", "security.md"],
}
