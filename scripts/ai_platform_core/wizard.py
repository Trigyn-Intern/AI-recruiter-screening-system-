"""Interactive wizard for collecting execution inputs."""

from __future__ import annotations

from .routing import ExecutionRequest
from .wizard_defaults import (
    PRIORITIES,
    PRIORITY_CHOICES,
    PROJECT_AREAS,
    TASK_TYPES,
)


def _prompt_required(question: str) -> str:
    """Prompt until the user supplies a non-empty value."""

    while True:
        value = input(f"{question}: ").strip()
        if value:
            return value
        print("This value is required. Please try again.")


def _prompt_optional(question: str, default: str = "") -> str:
    """Prompt for an optional value with an optional default."""

    suffix = f" [{default}]" if default else ""
    value = input(f"{question}{suffix}: ").strip()
    return value or default


def _choose(question: str, options: dict[str, str | tuple[str, str]], allow_custom: bool = True) -> str:
    """Render a numbered choice and return a label (or a custom value)."""

    labels: list[tuple[str, str, str]] = []
    for key, value in options.items():
        if isinstance(value, tuple):
            label, default_path = value
        else:
            label, default_path = value, ""
        labels.append((key, label, default_path))

    print()
    print(question)
    for key, label, _ in labels:
        print(f"  {key}) {label}")
    if allow_custom:
        print("  0) Enter custom value")
    while True:
        choice = input("Choice: ").strip()
        if choice == "0" and allow_custom:
            return _prompt_required("Custom value")
        for key, label, _ in labels:
            if choice == key:
                return label
        print("Invalid choice. Please pick a valid option.")


def _choose_priority() -> str:
    """Render the priority selector with validation."""

    print()
    print("Priority")
    for key, label in PRIORITY_CHOICES.items():
        print(f"  {key}) {label}")
    while True:
        choice = input("Choice: ").strip()
        if choice in PRIORITY_CHOICES:
            return PRIORITY_CHOICES[choice]
        if choice in PRIORITIES:
            return choice
        print("Invalid choice. Please pick a valid option.")


def _confirm(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer."""

    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{question} {suffix}: ").strip().lower()
        if not answer:
            return default
        if answer in {"y", "yes"}:
            return True
        if answer in {"n", "no"}:
            return False
        print("Please answer Y or N.")


def _multiline_notes() -> str:
    """Collect multiline notes terminated by a blank line."""

    print("Additional Notes (blank line to finish):")
    lines: list[str] = []
    while True:
        try:
            line = input("> ")
        except EOFError:
            break
        if line == "":
            break
        lines.append(line)
    return "\n".join(lines)


def _default_target_for(area_label: str) -> str:
    """Return the default target path for a given project area label."""

    for _, (label, default) in PROJECT_AREAS.items():
        if label == area_label:
            return default
    return ""


def run_wizard() -> ExecutionRequest:
    """Run the interactive wizard and return a populated ExecutionRequest."""

    print("=" * 60)
    print("AI ENGINEERING EXECUTION WIZARD")
    print("=" * 60)
    print()

    task = _prompt_required("Task Description")

    project_area = _choose("Project Area", PROJECT_AREAS)
    default_target = _default_target_for(project_area)
    target_location = _prompt_optional(
        "Target Folder or File",
        default=default_target,
    )
    if not target_location:
        target_location = _prompt_required("Target Folder or File")

    task_type = _choose("Task Type", TASK_TYPES, allow_custom=False)
    priority = _choose_priority()

    update_tests = _confirm("Generate Unit Tests?", default=True)
    update_docs = _confirm("Update Documentation?", default=True)
    security_review = _confirm("Require Security Review?", default=False)
    migration_notes = _confirm("Migration Required?", default=False)
    additional = _multiline_notes()

    return ExecutionRequest(
        task=task,
        project_area=project_area,
        target_location=target_location,
        task_type=task_type,
        priority=priority,
        update_tests=update_tests,
        update_docs=update_docs,
        security_review=security_review,
        migration_notes=migration_notes,
        additional_notes=additional,
    )