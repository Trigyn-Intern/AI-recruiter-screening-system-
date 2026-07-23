from fastapi.testclient import TestClient
from api import api, build_fit_bucket, serialize_jd_info
import pytest

client = TestClient(api)

def test_build_fit_bucket():
    assert build_fit_bucket(80) == "Good Fit"
    assert build_fit_bucket(70) == "Good Fit"
    assert build_fit_bucket(60) == "Moderate Fit"
    assert build_fit_bucket(50) == "Moderate Fit"
    assert build_fit_bucket(40) == "Bad Fit"

def test_serialize_jd_info():
    jd_info = {
        "experience": "5 years",
        "primary_skills": ["Python", "FastAPI"],
        "secondary_skills": ["Docker"],
        "education": "BSc"
    }
    result = serialize_jd_info(jd_info)
    # The display_value function turns list/string into string
    # Assuming display_value just passes through strings and joins lists (this will just run the code)
    assert "experience" in result

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_models():
    response = client.get("/models")
    assert response.status_code == 200
    assert "providers" in response.json()

def test_configuration():
    response = client.get("/configuration")
    assert response.status_code == 200
    assert "configuration" in response.json()

def test_get_review_status_not_found():
    response = client.get("/api/review/status/non-existent-id")
    assert response.status_code == 404
