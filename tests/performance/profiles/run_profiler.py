"""
CPU Profiler for AI Recruiter backend.

Profiles the extract_text + analyze_candidate_grading pipeline
and saves the top-30 most expensive call frames to profile_results.txt.

Run from the project root:
    python tests/performance/profiles/run_profiler.py
"""
from __future__ import annotations

import cProfile
import io
import pstats
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ------------------------------------------------------------------ #
# Stubs — must come BEFORE any backend import                        #
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

# Allow real docx / pypdf to load
for _real in ("docx", "pypdf"):
    sys.modules.pop(_real, None)

import importlib  # noqa: E402

importlib.import_module("pypdf")
importlib.import_module("docx")

# ------------------------------------------------------------------ #
# Now safe to import backend                                          #
# ------------------------------------------------------------------ #
PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from backend import extract_text, analyze_candidate_grading  # noqa: E402

SAMPLE_RESUMES_DIR = PROJECT_ROOT / "tests" / "data" / "resumes"
SAMPLE_JD_PATH     = PROJECT_ROOT / "tests" / "data" / "jds" / "jd_python_ml.txt"


def _load_resume_text(pdf_path: Path) -> str:
    buf = io.BytesIO(pdf_path.read_bytes())
    buf.name = pdf_path.name
    return extract_text(buf)


def run_heavy_ml_task() -> None:
    print("Profiling against real sample resumes...")

    if not SAMPLE_JD_PATH.is_file():
        raise SystemExit(f"Sample JD not found at {SAMPLE_JD_PATH}")
    job_text = SAMPLE_JD_PATH.read_text(encoding="utf-8")

    resume_files = sorted(SAMPLE_RESUMES_DIR.glob("*.pdf"))
    if not resume_files:
        raise SystemExit(f"No sample PDFs found in {SAMPLE_RESUMES_DIR}")

    matching_skills = ["Python", "FastAPI", "SQL"]
    missing_skills  = ["Kubernetes"]

    for pdf_path in resume_files:
        resume_text = _load_resume_text(pdf_path)
        print(f"  - {pdf_path.name}: {len(resume_text)} chars extracted")
        try:
            analyze_candidate_grading(
                resume_text,
                job_text,
                matching_skills,
                missing_skills,
                resume_name=pdf_path.name,
            )
            print("    graded OK")
        except Exception as e:
            print(f"    grading skipped (LLM unreachable): {e}")


if __name__ == "__main__":
    print("Starting Profiler...\n")
    pr = cProfile.Profile()
    pr.enable()

    run_heavy_ml_task()

    pr.disable()
    s = io.StringIO()
    pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(30)

    output_path = Path(__file__).parent / "profile_results.txt"
    output_path.write_text(s.getvalue(), encoding="utf-8")
    print(f"\nProfiling complete. Results saved to {output_path}")
