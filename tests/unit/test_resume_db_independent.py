import json

from backend import get_active_resume_db_records


def test_get_active_resume_db_records_loads_independently(tmp_path, monkeypatch):
    """Test that get_active_resume_db_records() works without FAISS dependency."""
    sample_skills = {
        "res1": {
            "resume_id": "res1",
            "resume_name": "resume1.pdf",
            "skills": ["Python"],
            "model": "local",
            "last_updated_at": "2026-01-01",
        },
        "res2": {
            "resume_id": "res2",
            "resume_name": "resume2.pdf",
            "skills": ["FastAPI"],
            "model": "local",
            "last_updated_at": "2026-01-01",
        },
    }
    mock_file = tmp_path / "resume_skills.json"
    mock_file.write_text(json.dumps(sample_skills), encoding="utf-8")
    monkeypatch.setattr("backend.RESUME_SKILLS_PATH", mock_file)

    records = get_active_resume_db_records()

    assert len(records) == 2
    for resume_id, record in records.items():
        assert "resume_id" in record
        assert "resume_name" in record
        assert "resume_skill_profile" in record
        assert "skills_model" in record
        assert "last_updated_at" in record


def test_get_active_resume_db_records_returns_empty_when_no_skills(
    tmp_path, monkeypatch
):
    """Test that get_active_resume_db_records() returns empty dict when skills store is empty."""
    mock_file = tmp_path / "resume_skills.json"
    mock_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("backend.RESUME_SKILLS_PATH", mock_file)

    records = get_active_resume_db_records()
    assert len(records) == 0
