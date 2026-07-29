"""Cache hit-rate benchmark.

Measures how fast get_or_create_resume_embedding is once the resume is
already in the FAISS index. This is the hot path: the same resume gets
re-uploaded every time a recruiter tweaks the JD, and we want that to
be near-free.
"""
import io
import pytest
import sys
import os
from pathlib import Path

# Ensure the root directory is in the Python path
sys.path.append(
    os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
)
from backend import (
    extract_text,
    get_or_create_resume_embedding,
    get_resume_id,
    faiss_index_lookup,
)

SAMPLE_RESUMES_DIR = Path(__file__).resolve().parents[3] / "tests" / "data" / "resumes"


def _resume_files():
    if not SAMPLE_RESUMES_DIR.is_dir():
        pytest.skip(f"sample resumes not found at {SAMPLE_RESUMES_DIR}")
    return sorted(SAMPLE_RESUMES_DIR.glob("*.pdf"))


@pytest.fixture(scope="module")
def warm_resume():
    """Pre-load one resume into FAISS so the benchmark measures cache hits."""
    pdf = next(iter(_resume_files()))
    pdf_bytes = pdf.read_bytes()
    buf = io.BytesIO(pdf_bytes)
    buf.name = pdf.name
    text = extract_text(buf)
    rid = get_resume_id(buf)
    # First call populates FAISS; subsequent calls hit the cache.
    get_or_create_resume_embedding(rid, pdf.name, text)
    return text, rid, pdf.name


@pytest.mark.benchmark(group="embedding")
def test_cold_embedding(benchmark, warm_resume):
    """Cold path: not in FAISS. Includes the actual embedding model call."""
    text, rid, name = warm_resume
    # Re-create a *different* resume_id so the cache check misses.
    fake_rid = "cold-" + rid
    benchmark(get_or_create_resume_embedding, fake_rid, name, text)


@pytest.mark.benchmark(group="embedding")
def test_warm_embedding(benchmark, warm_resume):
    """Warm path: already in FAISS. Should be orders of magnitude faster."""
    text, rid, name = warm_resume
    # Sanity check: the cache should actually hit
    cached = faiss_index_lookup(rid)
    assert cached is not None, "warm resume must be in FAISS before benchmarking"
    benchmark(get_or_create_resume_embedding, rid, name, text)
