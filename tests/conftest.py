"""Pytest configuration: stub the heavy ML imports before backend.py loads.

``backend.py`` imports ``sentence_transformers`` / ``torch`` at module
load time. On systems where the torch and torchvision wheels are out of
sync that import path can crash with a native ``0xc0000139`` error
before any of our tests get to run.

We patch ``sentence_transformers`` and a few torch submodules here so the
Skills tests can be collected and executed without booting the full
embedding stack. The analyzer itself still works at runtime because
those modules exist in the real venv.

NOTE: ``numpy`` is intentionally NOT stubbed because several test
assertions (np.testing.assert_array_equal, np.asarray comparisons, etc.)
need the real package.
"""

from __future__ import annotations

import sys
import types
from unittest.mock import MagicMock


def _install_stub(name: str) -> None:
    if name in sys.modules:
        return
    sys.modules[name] = MagicMock()


def _install_package(name: str) -> str:
    if name in sys.modules:
        return sys.modules[name]
    package = types.ModuleType(name)
    package.__path__ = []
    sys.modules[name] = package
    return package


for _mod in [
    "sentence_transformers",
    "torch",
    "torchvision",
    "faiss",
    "ollama",
    "google",
    "google.genai",
    "pandas",
    "docx",
    "pypdf",
    "sklearn",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
]:
    _install_stub(_mod)

# Configure pytest-asyncio to auto-mark async tests.
import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as asyncio")
