"""Project configuration loading and secret redaction."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .utils import read_text
from .wizard_defaults import CONFIG

SECRET_PATTERN = re.compile(
    r"(api[_ -]?key|secret|password|passwd|pwd|bearer\s+|jwt|token|"
    r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|"
    r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)",
    re.IGNORECASE,
)


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"').strip("'") for item in inner.split(",")]
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        return value[1:-1]
    return value


def load_project_config(path: Path = CONFIG) -> dict[str, Any]:
    if not path.exists():
        return {}
    config: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, config)]
    for raw_line in read_text(path).splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if value.strip():
            parent[key.strip()] = _parse_scalar(value.strip())
        else:
            child: dict[str, Any] = {}
            parent[key.strip()] = child
            stack.append((indent, child))
    return config


def redact_secrets(text: str) -> str:
    return SECRET_PATTERN.sub("[REDACTED]", text)
