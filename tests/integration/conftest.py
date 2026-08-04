"""Pytest configuration and shared fixtures for the consolidated test file.

The whole framework now lives in ``tests/ui/test_scenario_matrix.py`` -
the data-driven Playwright scenario matrix plus every backend unit and
integration probe that used to ship as separate files. This conftest
loads ``tests/data/scenarios.yaml`` and uses ``pytest_generate_tests``
to parametrize the single scenario-matrix test once per row, with CLI
options ``--scenario-config`` / ``--scenario-filter`` so the runner
(and CI) can target a subset of scenarios without editing the YAML.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pytest
import yaml


TESTS_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = TESTS_DIR.parent
DEFAULT_CONFIG = TESTS_DIR / "data" / "scenarios.yaml"
SCREENSHOT_DIR = Path(__file__).resolve().parent / "screenshots"


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise pytest.UsageError(
            f"Scenario config not found: {path}. "
            "Pass --scenario-config to point to a different file."
        )
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    scenarios = data.get("scenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise pytest.UsageError(
            f"Scenario config {path} must define a non-empty 'scenarios' list."
        )
    return {"path": path, "scenarios": scenarios}


def _resolve_filter(raw: str | None) -> List[str]:
    if not raw:
        return []
    return [token.strip() for token in re.split(r"[,\s]+", raw) if token.strip()]


def pytest_addoption(parser):
    group = parser.getgroup("scenario-matrix")
    group.addoption(
        "--scenario-config",
        action="store",
        default=os.environ.get("SCENARIO_CONFIG", str(DEFAULT_CONFIG)),
        help="Path to the YAML scenario config (default: tests/data/scenarios.yaml).",
    )
    group.addoption(
        "--scenario-filter",
        action="store",
        default=os.environ.get("SCENARIO_FILTER", ""),
        help=(
            "Comma- or whitespace-separated list of scenario IDs to run. "
            "Empty means run everything."
        ),
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "ui: end-to-end Playwright scenario runs")
    config.addinivalue_line("markers", "backend: backend unit tests")
    config.addinivalue_line(
        "markers", "integration: integration probes against the live FastAPI"
    )


@pytest.fixture(scope="session")
def scenario_config_path(request) -> Path:
    return Path(request.config.getoption("--scenario-config"))


@pytest.fixture(scope="session")
def scenarios(scenario_config_path) -> List[Dict[str, Any]]:
    return _load_yaml(scenario_config_path)["scenarios"]


@pytest.fixture(scope="session")
def data_root(scenario_config_path) -> Path:
    return scenario_config_path.resolve().parent


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get("WEB_BASE_URL", "http://localhost:5173")


@pytest.fixture(autouse=True)
def _ensure_screenshot_dir():
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


def pytest_generate_tests(metafunc):
    if "scenario" not in metafunc.fixturenames:
        return

    config_path = Path(metafunc.config.getoption("--scenario-config"))
    raw_filter = metafunc.config.getoption("--scenario-filter")
    selected = set(_resolve_filter(raw_filter))

    loaded = _load_yaml(config_path)
    scenarios: Iterable[Dict[str, Any]] = loaded["scenarios"]

    if selected:
        scenarios = [s for s in scenarios if s.get("id") in selected]
        missing = selected - {s.get("id") for s in scenarios}
        if missing:
            pytest.exit(f"Unknown scenario ids in --scenario-filter: {sorted(missing)}")

    ids = [s["id"] for s in scenarios]
    metafunc.parametrize("scenario", scenarios, ids=ids)
