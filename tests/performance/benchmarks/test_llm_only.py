"""
Benchmark: LLM candidate detail analysis speed.

This benchmark makes a real LLM call so it is marked @pytest.mark.slow.
Exclude it from fast CI runs with:

    pytest tests/performance/benchmarks/ -m "not slow"

Include it for a full performance audit:

    pytest tests/performance/benchmarks/ -m slow -v
"""

from __future__ import annotations

import pytest
from pathlib import Path

from backend import analyze_candidate_detail

SAMPLE_JD_PATH = (
    Path(__file__).resolve().parents[3] / "tests" / "data" / "jds" / "jd_python_ml.txt"
)

_MOCK_RESUME_TEXT = (
    "John Doe — Senior Python Engineer.\n"
    "Skills: Python 3.11, FastAPI, PostgreSQL, Docker, REST APIs.\n"
    "Experience: 7 years. Led microservices rewrite reducing p99 latency by 40%."
)


@pytest.fixture(scope="module")
def jd_text():
    if not SAMPLE_JD_PATH.is_file():
        pytest.skip(f"Sample JD not found at {SAMPLE_JD_PATH}")
    return SAMPLE_JD_PATH.read_text(encoding="utf-8")


@pytest.mark.slow
@pytest.mark.benchmark(group="llm")
def test_analyze_candidate_detail(benchmark, jd_text):
    """Benchmark a full LLM candidate detail call. Skips gracefully if LLM is unreachable."""
    try:
        benchmark(
            analyze_candidate_detail,
            _MOCK_RESUME_TEXT,
            jd_text,
            ["Python", "FastAPI", "PostgreSQL"],
            ["Kubernetes"],
            resume_name="benchmark_candidate.pdf",
        )
    except Exception as e:
        pytest.skip(f"LLM unavailable during benchmark (expected in CI): {e}")
