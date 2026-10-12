import pytest
from fastapi.testclient import TestClient

from api import api

client = TestClient(api)

SAPNA_RESUME_ID = "0f2a320d90b526a6f90600387101322597a9ebd81c95174f40beb4ffb25718b6"

# Minimal fixture data matching the production schema stored in resume_chunks.json.
# The route supports both dict-keyed and list-based chunk stores.
_FIXTURE_CHUNKS = [
    {
        "resume_id": SAPNA_RESUME_ID,
        "chunk_id": f"chunk-{i}",
        "chunk_index": i,
        "text": f"Sample resume text for section {i}.",
        "section": f"Section {i}",
        "entity_id": f"entity-{i}",
        "entity_name": f"Entity {i}",
    }
    for i in range(13)
]


@pytest.fixture(autouse=True)
def _mock_chunks_store(monkeypatch):
    """Provide deterministic chunk data so tests don't depend on disk state."""
    monkeypatch.setattr(
        "api.read_json_file",
        lambda path, default=None: {SAPNA_RESUME_ID: _FIXTURE_CHUNKS},
    )


def test_resume_detail_returns_sapna_resume_text_and_chunks():
    response = client.get(f"/resume/{SAPNA_RESUME_ID}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["resume_text"]
    assert len(payload["chunks"]) == 13
    assert payload["chunks"][0]["text"]
    assert payload["chunks"][0]["section"]
    assert payload["chunks"][0]["chunk_id"]


def test_resume_detail_preserves_chunk_objects():
    response = client.get(f"/resume/{SAPNA_RESUME_ID}")

    chunk = response.json()["chunks"][0]
    assert "entity_id" in chunk
    assert "entity_name" in chunk
    assert "chunk_index" in chunk
    assert "text" in chunk


def test_resume_detail_returns_404_for_unknown_resume():
    response = client.get("/resume/does-not-exist")

    assert response.status_code == 404
