"""Unit tests for the Report Summary helpers added to api.py.

These tests cover the pure helpers (HTML stripping, report-id hashing,
JSON extraction) without booting FastAPI, the LLM provider, or the
local filesystem. They run with the standard test runner:

    pytest tests/unit/test_report_summary.py -v
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
API_PY = REPO_ROOT / "api.py"


def _install_fake_module(name: str, **attrs) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    sys.modules[name] = module
    return module


@pytest.fixture(scope="module")
def api_module():
    """Load api.py with heavy deps stubbed so import is fast and offline.

    The full module pulls in FastAPI, the analyzer pipeline, and torch.
    For these helper-level tests we only need the module object that
    already finished importing those (it does so via conftest at
    collection time anyway), so the test simply imports api if it is
    already in sys.modules, else loads it with minimal stubs.
    """
    if "api" in sys.modules:
        return importlib.import_module("api")

    # Minimal FastAPI + pydantic stub for environments where api.py
    # has not been imported yet (e.g. a focused unit-test run).
    fake_fastapi = _install_fake_module("fastapi")
    fake_fastapi.FastAPI = lambda *a, **kw: types.SimpleNamespace(
        add_middleware=lambda *a, **kw: None,
        mount=lambda *a, **kw: None,
        get=lambda *a, **kw: lambda f: f,
        post=lambda *a, **kw: lambda f: f,
        put=lambda *a, **kw: lambda f: f,
    )
    fake_fastapi.File = lambda *a, **kw: None
    fake_fastapi.Form = lambda *a, **kw: None
    fake_fastapi.HTTPException = type("HTTPException", (Exception,), {})
    fake_fastapi.BackgroundTasks = object
    _install_fake_module(
        "fastapi.middleware",
    )
    fake_cors = _install_fake_module("fastapi.middleware.cors")
    fake_cors.CORSMiddleware = object
    fake_static = _install_fake_module("fastapi.staticfiles")
    fake_static.StaticFiles = lambda *a, **kw: None
    fake_responses = _install_fake_module("fastapi.responses")
    fake_responses.FileResponse = object
    _install_fake_module("pydantic").BaseModel = type(
        "BaseModel", (), {"__init_subclass__": classmethod(lambda cls, **kw: None)}
    )

    spec = importlib.util.spec_from_file_location("api", API_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["api"] = module
    spec.loader.exec_module(module)
    return module


def test_strip_html_removes_tags_and_decodes_entities(api_module):
    stripped = api_module._strip_html(
        "<html><body><h1>Hello &amp; <em>world</em></h1>"
        "<script>alert(1)</script></body></html>"
    )
    assert "<" not in stripped
    assert ">" not in stripped
    assert "alert" not in stripped
    assert "Hello" in stripped and "world" in stripped


def test_report_id_for_is_stable_and_short(api_module):
    rid = api_module._report_id_for("reports/ci/ci-summary.html")
    assert len(rid) == 16
    assert api_module._report_id_for("reports/ci/ci-summary.html") == rid
    assert (
        api_module._report_id_for("reports/ci/ci-summary.html")
        != api_module._report_id_for(".code-review/checklist-report.html")
    )


def test_safe_json_loads_direct(api_module):
    parsed = api_module._safe_json_loads('{"a": 1, "b": [1, 2]}')
    assert parsed == {"a": 1, "b": [1, 2]}


def test_safe_json_loads_from_fenced_block(api_module):
    parsed = api_module._safe_json_loads(
        "Some prose.\n```json\n{\"a\": 2}\n```\nTail text."
    )
    assert parsed == {"a": 2}


def test_safe_json_loads_from_substring(api_module):
    parsed = api_module._safe_json_loads('prefix {"a": 3, "b": "x"} suffix')
    assert parsed == {"a": 3, "b": "x"}


def test_safe_json_loads_returns_none_on_garbage(api_module):
    assert api_module._safe_json_loads("totally not json") is None
    assert api_module._safe_json_loads("") is None
    assert api_module._safe_json_loads(None) is None