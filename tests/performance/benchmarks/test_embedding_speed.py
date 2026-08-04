"""
Benchmark: sentence embedding generation speed.

Measures how long get_or_create_resume_embedding() takes on a cold run
(embedding not yet in FAISS) using a sample PDF from tests/data/resumes/.

Run:
    pytest tests/performance/benchmarks/test_embedding_speed.py -v
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from backend import extract_text, get_or_create_resume_embedding, get_resume_id

SAMPLE_RESUMES_DIR = Path(__file__).resolve().parents[3] / "tests" / "data" / "resumes"


def _pdf_files():
    if not SAMPLE_RESUMES_DIR.is_dir():
        return []
    return sorted(SAMPLE_RESUMES_DIR.glob("*.pdf"))


@pytest.fixture(scope="module")
def sample_resume_pdf():
    """Load the first available sample PDF into memory."""
    pdfs = _pdf_files()
    if not pdfs:
        pytest.skip("No sample PDFs found in tests/data/resumes/")
    pdf = pdfs[0]
    pdf_bytes = pdf.read_bytes()
    buf = io.BytesIO(pdf_bytes)
    buf.name = pdf.name
    text = extract_text(buf)
    buf.seek(0)
    resume_id = get_resume_id(buf)
    return {"text": text, "resume_id": resume_id, "name": pdf.name}


@pytest.mark.benchmark(group="embedding")
def test_embedding_speed(benchmark, sample_resume_pdf):
    """Benchmark cold embedding generation (not yet in FAISS)."""
    text = sample_resume_pdf["text"]
    rid  = sample_resume_pdf["resume_id"]
    name = sample_resume_pdf["name"]
    # Use a unique ID each run to force a cold (non-cached) embedding path
    cold_rid = f"bench-cold-{rid}"
    benchmark(get_or_create_resume_embedding, cold_rid, name, text)
