"""
Performance test conftest.

The benchmark scripts import functions from backend.py directly.
backend.py imports sentence_transformers / torch at module level, which
crashes with a native error on mismatched torchvision wheels.

Strategy: install the same stubs the root conftest.py uses, THEN import
backend so its module-level imports bind to MagicMock instead of crashing.
The real PDF / DOCX parsing logic (PyPDF, python-docx) does NOT use torch
and is imported correctly after the stubs are in place.
"""
from __future__ import annotations

import sys
from unittest.mock import MagicMock

# ------------------------------------------------------------------ #
# Install stubs for the ML/GPU stack before backend.py is imported.  #
# This mirrors tests/conftest.py exactly.                            #
# ------------------------------------------------------------------ #
_STUBS = [
    "sentence_transformers",
    "torch",
    "torchvision",
    "faiss",
    "ollama",
    "google",
    "google.genai",
    "pandas",
    "sklearn",
    "sklearn.metrics",
    "sklearn.metrics.pairwise",
]

for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Allow the real docx / pypdf to load (they don't need torch).
for _real in ("docx", "pypdf"):
    sys.modules.pop(_real, None)

import importlib
importlib.import_module("pypdf")
importlib.import_module("docx")

# Now import backend — its torch/sentence_transformers references
# will resolve to MagicMock, but extract_text / extract_pdf_text etc.
# will work correctly because they only use pypdf and docx.
import backend  # noqa: E402  (must come after stubs)
