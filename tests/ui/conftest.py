"""Shared pytest fixtures for the data-driven UI tests.

We rely on ``pytest-playwright`` for the browser lifecycle (it ships
session-scoped ``playwright`` / ``browser`` fixtures and per-test
``context`` / ``page`` fixtures). This file adds the scenario
loader, the parametrization hook, and a couple of tiny conveniences.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import yaml


# pytest-playwright reads PLAYWRIGHT_BROWSERS_PATH automatically.
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", r"D:\playwright\browsers")

ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = ROOT / "tests" / "data" / "scenarios.yaml"
SCREENSHOTS_DIR = ROOT / "tests" / "ui" / "screenshots"
DEFAULT_BASE_URL = "http://localhost:8501"

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_scenarios() -> dict:
    if not SCENARIOS_PATH.exists():
        raise FileNotFoundError(
            f"Scenario config not found at {SCENARIOS_PATH}"
        )

    with SCENARIOS_PATH.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    app_base_url = config.get("base_url") or os.environ.get(
        "APP_BASE_URL", DEFAULT_BASE_URL
    )
    scenarios = config.get("scenarios") or []

    if not scenarios:
        raise ValueError(
            "No scenarios defined in scenarios.yaml. "
            "Add at least one entry under 'scenarios:'."
        )

    return {
        "base_url": app_base_url,
        "scenarios": scenarios,
    }


# ---- Session-scoped fixtures ------------------------------------------------

@pytest.fixture(scope="session")
def app_config() -> dict:
    return _load_scenarios()


@pytest.fixture(scope="session")
def scenarios(app_config) -> list[dict]:
    return app_config["scenarios"]


@pytest.fixture(scope="session")
def app_base_url(app_config) -> str:
    """The Streamlit app URL. Named app_base_url to avoid shadowing
    pytest-playwright's built-in base_url fixture."""
    return app_config["base_url"]


@pytest.fixture(scope="session")
def screenshots_dir() -> Path:
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    return SCREENSHOTS_DIR


# ---- Parametrization hook ----------------------------------------------------

def pytest_generate_tests(metafunc):
    """Parametrize the scenario test with every row in scenarios.yaml."""

    if "scenario" not in metafunc.fixturenames:
        return

    config = _load_scenarios()
    ids = [s["id"] for s in config["scenarios"]]
    metafunc.parametrize(
        "scenario",
        config["scenarios"],
        ids=ids,
    )