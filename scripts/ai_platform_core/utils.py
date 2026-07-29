"""Filesystem and timestamp helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

UTC = timezone.utc

from .wizard_defaults import ROOT  # noqa: E402


def utc_now() -> datetime:
    return datetime.now(UTC)


def timestamp() -> str:
    return utc_now().strftime("%Y-%m-%d %H:%M UTC")


def timestamp_slug() -> str:
    return utc_now().strftime("%Y%m%d_%H%M%S")


def relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def write_text(path: Path, content: str) -> None:
    ensure_directory(path.parent)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    import json

    ensure_directory(path.parent)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def read_json(path: Path) -> Any:
    import json

    try:
        return json.loads(read_text(path) or "{}")
    except json.JSONDecodeError:
        return {}
