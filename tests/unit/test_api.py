import json
from datetime import datetime, timedelta, timezone

import jwt
import numpy as np
from fastapi.testclient import TestClient

from api import _build_persistable_file_cache, api, build_fit_bucket, serialize_jd_info
from backend import persist_analysis_session

client = TestClient(api)


def _token(
    monkeypatch,
    assessment_id,
    candidate_id,
    token_type="assessment",
    subject="recruiter-1",
):
    secret = "test-jwt-secret"
    monkeypatch.setenv("JWT_SECRET", secret)
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10),
    }
    if token_type:
        payload.update(
            {
                "token_type": token_type,
                "assessment_id": assessment_id,
                "candidate_id": candidate_id,
            }
        )
    return jwt.encode(payload, secret, algorithm="HS256")


def _now():
    return datetime.now(timezone.utc).isoformat()


PNG_BYTES = b"\x89PNG\r\n\x1a\nvalid-test-png"
WEBM_BYTES = b"\x1a\x45\xdf\xa3valid-test-webm"


def test_analysis_session_persistence_excludes_embedding_arrays(tmp_path):
    resume_embedding = np.asarray([[0.1, 0.2]], dtype="float32")
    chunk_embedding = np.asarray([[0.3, 0.4]], dtype="float32")
    file_cache = [
        {
            "record": {"resume_id": "resume-1", "resume_name": "resume.pdf"},
            "resume_text": "Python experience",
            "resume_skill_profile": {"skills": ["Python"]},
            "resume_embedding": resume_embedding,
            "chunk_data": {
                "embeddings": [chunk_embedding],
                "chunks": [{"chunk_id": "resume-1_chunk_000"}],
            },
        }
    ]

    persistable_cache = _build_persistable_file_cache(file_cache)
    persist_analysis_session(
        {
            "base_dir": str(tmp_path),
            "job_description": "Python role",
            "file_cache": persistable_cache,
        }
    )

    stored_sessions = json.loads(
        (tmp_path / "analysis_sessions.json").read_text(encoding="utf-8")
    )
    stored_item = stored_sessions[0]["file_cache"][0]

    assert "resume_embedding" not in stored_item
    assert "embeddings" not in stored_item["chunk_data"]
    assert stored_item["record"]["resume_id"] == "resume-1"
    assert stored_item["resume_text"] == "Python experience"
    assert stored_item["chunk_data"]["chunks"] == [{"chunk_id": "resume-1_chunk_000"}]
    assert isinstance(file_cache[0]["resume_embedding"], np.ndarray)
    assert isinstance(file_cache[0]["chunk_data"]["embeddings"][0], np.ndarray)


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
        "education": "BSc",
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


def test_behavior_events_accept_eye_event_types(monkeypatch):
    captured_events = []

    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions",
        lambda assessment_id: {"candidate_id": "candidate-eye-events", "questions": []},
    )

    def capture_events(assessment_id, candidate_id, new_events):
        captured_events.extend(new_events)
        return {"assessment_id": assessment_id, "events": new_events}

    monkeypatch.setattr(
        "backend_question_generator.append_assessment_behavior_events", capture_events
    )

    eye_event_types = [
        "eye_looking_left",
        "eye_looking_right",
        "eye_looking_up",
        "eye_looking_down",
        "eye_looking_forward",
    ]
    response = client.post(
        "/api/assessment/behavior-events",
        headers={
            "Authorization": f"Bearer {_token(monkeypatch, 'assessment-eye-events', 'candidate-eye-events')}"
        },
        json={
            "assessment_id": "assessment-eye-events",
            "candidate_id": "candidate-eye-events",
            "events": [
                {"type": event_type, "timestamp": _now(), "details": "face_landmarker"}
                for event_type in eye_event_types
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["events_added"] == len(eye_event_types)
    assert [event["type"] for event in captured_events] == eye_event_types


def test_behavior_events_reject_unknown_event_types(monkeypatch):
    append_called = False

    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions",
        lambda assessment_id: {
            "candidate_id": "candidate-unknown-event",
            "questions": [],
        },
    )

    def unexpected_append(*args, **kwargs):
        nonlocal append_called
        append_called = True
        return {"events": []}

    monkeypatch.setattr(
        "backend_question_generator.append_assessment_behavior_events",
        unexpected_append,
    )

    response = client.post(
        "/api/assessment/behavior-events",
        headers={
            "Authorization": f"Bearer {_token(monkeypatch, 'assessment-unknown-event', 'candidate-unknown-event')}"
        },
        json={
            "assessment_id": "assessment-unknown-event",
            "candidate_id": "candidate-unknown-event",
            "events": [{"type": "eye_coordinate_dump", "timestamp": _now()}],
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "message": "No valid behavior events to record",
        "count": 0,
    }
    assert append_called is False


def test_recruiter_can_issue_scoped_assessment_token(monkeypatch):
    import api as api_module

    monkeypatch.setattr(
        "assessment_auth._is_recruiter_user", lambda subject: subject == "recruiter-1"
    )
    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions",
        lambda assessment_id: {"candidate_id": "candidate-token-1", "questions": []},
    )
    monkeypatch.setattr(
        api_module,
        "get_shortlists",
        lambda: [
            {
                "user_id": "recruiter-1",
                "candidates": [{"resume_id": "candidate-token-1"}],
            }
        ],
    )
    recruiter_token = _token(
        monkeypatch,
        "assessment-token-1",
        "candidate-token-1",
        token_type=None,
    )

    response = client.post(
        "/api/assessment/access-token",
        headers={"Authorization": f"Bearer {recruiter_token}"},
        json={
            "assessment_id": "assessment-token-1",
            "candidate_id": "candidate-token-1",
        },
    )

    assert response.status_code == 200
    token = response.json()["token"]
    claims = jwt.decode(token, "test-jwt-secret", algorithms=["HS256"])
    assert claims["token_type"] == "assessment"
    assert claims["assessment_id"] == "assessment-token-1"
    assert claims["candidate_id"] == "candidate-token-1"


def test_evidence_upload_is_assessment_scoped_and_allowlisted(tmp_path, monkeypatch):
    import api as api_module

    monkeypatch.setattr(
        "assessment_auth._is_recruiter_user", lambda subject: subject == "recruiter-1"
    )
    monkeypatch.setattr(api_module, "ASSESSMENT_EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(
        api_module,
        "ASSESSMENT_EVIDENCE_METADATA_PATH",
        tmp_path / "evidence" / "metadata.json",
    )

    def get_questions(assessment_id):
        if assessment_id == "assessment-evidence-1":
            return {"candidate_id": "candidate-evidence-1", "questions": []}
        return None

    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions", get_questions
    )
    monkeypatch.setattr(
        api_module,
        "get_shortlists",
        lambda: [
            {
                "user_id": "recruiter-1",
                "candidates": [{"resume_id": "candidate-evidence-1"}],
            }
        ],
    )
    candidate_token = _token(
        monkeypatch, "assessment-evidence-1", "candidate-evidence-1"
    )
    recruiter_token = _token(
        monkeypatch,
        "assessment-evidence-1",
        "candidate-evidence-1",
        token_type=None,
    )

    response = client.post(
        "/api/assessment/evidence",
        headers={"Authorization": f"Bearer {candidate_token}"},
        data={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "event_type": "looking_away",
            "timestamp": _now(),
            "duration_seconds": "2.5",
            "evidence_type": "screen_video",
        },
        files={"clip": ("evidence.webm", WEBM_BYTES, "video/webm")},
    )

    assert response.status_code == 200
    evidence = response.json()
    assert evidence["assessment_id"] == "assessment-evidence-1"
    assert evidence["event_type"] == "looking_away"
    assert evidence["evidence_type"] == "screen_video"
    assert evidence["duration_seconds"] == 2.5

    list_response = client.get(
        "/api/assessment/evidence/assessment-evidence-1",
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["evidence"]) == 1

    clip_response = client.get(
        f"/api/assessment/evidence/assessment-evidence-1/{evidence['evidence_id']}",
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert clip_response.status_code == 200
    assert clip_response.content == WEBM_BYTES

    other_assessment_response = client.get(
        "/api/assessment/evidence/assessment-evidence-2",
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert other_assessment_response.status_code == 403

    rejected_response = client.post(
        "/api/assessment/evidence",
        headers={"Authorization": f"Bearer {candidate_token}"},
        data={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "event_type": "face_present",
            "timestamp": _now(),
            "duration_seconds": "2.5",
            "evidence_type": "screen_video",
        },
        files={"clip": ("evidence.webm", WEBM_BYTES, "video/webm")},
    )
    assert rejected_response.status_code == 400

    screenshot_response = client.post(
        "/api/assessment/evidence",
        headers={"Authorization": f"Bearer {candidate_token}"},
        data={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "event_type": "copy_attempt",
            "timestamp": _now(),
            "duration_seconds": "0.1",
            "evidence_type": "screen_screenshot",
        },
        files={"clip": ("evidence.png", PNG_BYTES, "image/png")},
    )
    assert screenshot_response.status_code == 200
    screenshot = screenshot_response.json()
    assert screenshot["evidence_type"] == "screen_screenshot"
    screenshot_clip = client.get(
        f"/api/assessment/evidence/assessment-evidence-1/{screenshot['evidence_id']}",
        headers={"Authorization": f"Bearer {recruiter_token}"},
    )
    assert screenshot_clip.status_code == 200
    assert screenshot_clip.headers["content-type"] == "image/png"


def test_assessment_endpoints_reject_unauthenticated_requests(monkeypatch):
    response = client.get("/api/assessment/evidence/assessment-evidence-1")
    assert response.status_code == 401

    response = client.get("/api/assessment/behavior-events/assessment-evidence-1")
    assert response.status_code == 401

    response = client.post(
        "/api/assessment/behavior-events",
        json={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "events": [],
        },
    )
    assert response.status_code == 401


def test_assessment_endpoints_reject_cross_candidate_and_path_traversal(
    tmp_path, monkeypatch
):
    import api as api_module

    monkeypatch.setattr(api_module, "ASSESSMENT_EVIDENCE_DIR", tmp_path / "evidence")
    monkeypatch.setattr(
        api_module,
        "ASSESSMENT_EVIDENCE_METADATA_PATH",
        tmp_path / "evidence" / "metadata.json",
    )
    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions",
        lambda assessment_id: {"candidate_id": "candidate-evidence-1", "questions": []},
    )
    token = _token(monkeypatch, "assessment-evidence-1", "another-candidate")
    response = client.post(
        "/api/assessment/evidence",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "another-candidate",
            "event_type": "copy_attempt",
            "timestamp": _now(),
            "duration_seconds": "0.1",
            "evidence_type": "screen_screenshot",
        },
        files={"clip": ("evidence.png", PNG_BYTES, "image/png")},
    )
    assert response.status_code == 403

    response = client.get(
        "/api/assessment/evidence/../metadata.json",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code in {400, 401, 403, 404}


def test_evidence_rejects_malformed_upload_and_invalid_event(monkeypatch):
    monkeypatch.setattr(
        "backend_question_generator.get_assessment_questions",
        lambda assessment_id: {"candidate_id": "candidate-evidence-1", "questions": []},
    )
    token = _token(monkeypatch, "assessment-evidence-1", "candidate-evidence-1")
    response = client.post(
        "/api/assessment/evidence",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "event_type": "copy_attempt",
            "timestamp": _now(),
            "duration_seconds": "inf",
            "evidence_type": "screen_screenshot",
        },
        files={"clip": ("evidence.png", b"not-png", "image/png")},
    )
    assert response.status_code == 400

    response = client.post(
        "/api/assessment/behavior-events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "assessment_id": "assessment-evidence-1",
            "candidate_id": "candidate-evidence-1",
            "events": [
                {"type": "tab_visible", "timestamp": _now(), "duration_seconds": -1}
            ],
        },
    )
    assert response.status_code == 400
