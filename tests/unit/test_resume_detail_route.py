from fastapi.testclient import TestClient

from api import api

client = TestClient(api)
SAPNA_RESUME_ID = "0f2a320d90b526a6f90600387101322597a9ebd81c95174f40beb4ffb25718b6"


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
