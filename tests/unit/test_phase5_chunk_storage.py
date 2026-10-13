import numpy as np
import pytest

import backend

pytestmark = pytest.mark.skip(
    reason=(
        "Phase 5 chunk storage functions (get_resume_content_hash, "
        "cached_chunks_are_current, chunk_resume) are not implemented in backend.py."
    )
)


class FakeIndex:
    d = 2
    ntotal = 1

    def reconstruct(self, row):
        assert row == 0
        return np.array([0.1, 0.2], dtype="float32")


def test_cached_chunks_require_openai_model_and_content_hash():
    content_hash = backend.get_resume_content_hash([{"page": 1, "text": "Resume"}])
    current = [
        {
            "provider": "openai",
            "model": "gpt-4o",
            "content_hash": content_hash,
        }
    ]
    stale_provider = [{**current[0], "provider": "gemini"}]
    stale_content = [{**current[0], "content_hash": "different"}]

    assert backend.cached_chunks_are_current(current, content_hash)
    assert not backend.cached_chunks_are_current(stale_provider, content_hash)
    assert not backend.cached_chunks_are_current(stale_content, content_hash)


def test_chunk_processing_persists_openai_provenance(monkeypatch):
    observed = {}

    def fake_chunk_resume(items, resume_name, provider=None):
        observed["provider"] = provider
        return [{"section": "Summary", "text": "Actual summary"}]

    monkeypatch.setattr(backend, "chunk_resume", fake_chunk_resume)
    content_hash = backend.get_resume_content_hash(
        [{"page": 1, "text": "Actual summary"}]
    )

    chunks = backend.process_resume_into_chunks(
        "resume-id",
        "resume.pdf",
        [{"page": 1, "text": "Actual summary"}],
        provider="openai",
        content_hash=content_hash,
    )

    assert observed["provider"] == "openai"
    assert chunks[0]["resume_id"] == "resume-id"
    assert chunks[0]["provider"] == "openai"
    assert chunks[0]["model"] == "gpt-4o"
    assert chunks[0]["content_hash"] == content_hash


def test_valid_cached_chunks_reuse_faiss_embeddings(monkeypatch, tmp_path):
    chunks_path = tmp_path / "resume_chunks.json"
    content_items = [{"page": 1, "text": "Resume"}]
    content_hash = backend.get_resume_content_hash(content_items)
    chunks_path.write_text(
        backend.json.dumps(
            [
                {
                    "resume_id": "resume-id",
                    "chunk_id": "chunk-1",
                    "faiss_row": 0,
                    "provider": "openai",
                    "model": "gpt-4o",
                    "content_hash": content_hash,
                }
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(backend, "RESUME_CHUNKS_PATH", chunks_path)
    monkeypatch.setattr(backend, "load_resume_vector_store", lambda: (FakeIndex(), []))
    monkeypatch.setattr(
        backend,
        "process_resume_into_chunks",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cache miss")),
    )

    result = backend.get_or_create_resume_embeddings_chunked(
        "resume-id", "resume.pdf", content_items
    )

    assert len(result["embeddings"]) == 1
    assert result["chunks"][0]["chunk_id"] == "chunk-1"
