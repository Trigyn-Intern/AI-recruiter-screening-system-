import json
import os
import backend_question_generator as assessment_module
import pytest
from unittest.mock import patch
from backend_question_generator import (
    calculate_behavior_score,
    score_assessment_attempt,
    save_assessment_result,
    save_assessment_attempt,
    save_assessment_questions,
    ASSESSMENT_RESULTS_PATH,
    ASSESSMENT_ATTEMPTS_PATH,
    ASSESSMENT_QUESTIONS_PATH,
    ASSESSMENT_BEHAVIOR_EVENTS_PATH
)

TEST_ASSESSMENT_ID = "test_score_id"

@pytest.fixture(autouse=True)
def isolate_test_stores(tmp_path, monkeypatch):
    """Isolate assessment storage paths to temporary files during pytest execution to prevent touching vector_store runtime data."""
    q_file = tmp_path / "assessment_questions.json"
    att_file = tmp_path / "assessment_attempts.json"
    res_file = tmp_path / "assessment_results.json"
    behavior_file = tmp_path / "assessment_behavior_events.json"

    monkeypatch.setattr("backend_question_generator.ASSESSMENT_QUESTIONS_PATH", q_file)
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_ATTEMPTS_PATH", att_file)
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_RESULTS_PATH", res_file)
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_BEHAVIOR_EVENTS_PATH", behavior_file)


def test_behavior_score_is_deterministic_and_bounded():
    result = calculate_behavior_score([
        {"type": "tab_hidden", "timestamp": "t1"},
        {"type": "tab_hidden", "timestamp": "t1"},
        {"type": "tab_visible", "timestamp": "t2", "duration_seconds": 12.0},
        {"type": "face_absent", "timestamp": "t3"},
        {"type": "multiple_faces_detected", "timestamp": "t4"},
        {"type": "camera_error", "timestamp": "t5"},
        {"type": "camera_permission_denied", "timestamp": "t6"},
    ])

    assert result["behavior_score"] == 85
    assert result["behavior_summary"] == {
        "tab_switches": 1,
        "total_tab_away_seconds": 12.0,
        "face_absent_events": 1,
        "multiple_faces_events": 1,
        "camera_errors": 1,
        "permission_denied": 1,
    }


def test_behavior_score_is_100_without_events():
    result = calculate_behavior_score([])

    assert result["behavior_score"] == 100
    assert all(value == 0 for value in result["behavior_summary"].values())


def test_weighted_result_keeps_technical_score_separate():
    questions = {
        "questions": [
            {"id": f"q{i}", "type": "mcq", "skill": "Python", "correct_answer": "A"}
            for i in range(15)
        ]
    }
    attempt = {"answers": {f"q{i}": "A" if i < 12 else "B" for i in range(15)}}
    save_assessment_questions(TEST_ASSESSMENT_ID, questions)
    save_assessment_attempt(TEST_ASSESSMENT_ID, attempt)
    assessment_module.ASSESSMENT_BEHAVIOR_EVENTS_PATH.write_text(json.dumps({
        TEST_ASSESSMENT_ID: {
            "assessment_id": TEST_ASSESSMENT_ID,
            "events": [
                {"type": "tab_hidden", "timestamp": "t1"},
                {"type": "tab_hidden", "timestamp": "t2"},
            ],
        }
    }))

    result = score_assessment_attempt(TEST_ASSESSMENT_ID)

    assert result["technical_score"] == 12.0
    assert result["technical_percentage"] == 80.0
    assert result["behavior_score"] == 96
    assert result["overall_percentage"] == 83.2


def test_behavior_score_skips_malformed_durations():
    result = calculate_behavior_score([
        {"type": "tab_visible", "duration_seconds": -1},
        {"type": "tab_visible", "duration_seconds": "not-a-number"},
        {"type": "tab_visible", "duration_seconds": float("inf")},
        {"type": "tab_visible", "duration_seconds": 20000},
        {"type": "tab_hidden", "timestamp": {"unexpected": "object"}},
    ])

    assert result["behavior_score"] == 98
    assert result["behavior_summary"]["total_tab_away_seconds"] == 0.0


def test_rescoring_ignores_malformed_persisted_events():
    questions = {
        "questions": [
            {"id": "q1", "type": "mcq", "skill": "Python", "correct_answer": "A"}
        ]
    }
    save_assessment_questions(TEST_ASSESSMENT_ID, questions)
    save_assessment_attempt(TEST_ASSESSMENT_ID, {"answers": {"q1": "A"}})
    assessment_module.ASSESSMENT_BEHAVIOR_EVENTS_PATH.write_text(json.dumps({
        TEST_ASSESSMENT_ID: {
            "assessment_id": TEST_ASSESSMENT_ID,
            "events": [
                {"type": "tab_visible", "duration_seconds": "bad"},
                {"type": "tab_visible", "duration_seconds": -4},
            ],
        }
    }))

    first = score_assessment_attempt(TEST_ASSESSMENT_ID)
    second = score_assessment_attempt(TEST_ASSESSMENT_ID)

    assert first["overall_percentage"] == 100.0
    assert second["overall_percentage"] == first["overall_percentage"]

def test_mcq_scoring():
    questions = {
        "questions": [
            {"id": "q1", "type": "mcq", "skill": "Python", "correct_answer": "A"},
            {"id": "q2", "type": "mcq", "skill": "React", "correct_answer": "B"},
            {"id": "q3", "type": "mcq", "skill": "Python", "correct_answer": "C"}
        ]
    }
    attempt = {
        "answers": {
            "q1": "A", # correct
            "q2": "c", # incorrect
            # q3 unanswered
        }
    }
    
    save_assessment_questions(TEST_ASSESSMENT_ID, questions)
    save_assessment_attempt(TEST_ASSESSMENT_ID, attempt)
    
    result = score_assessment_attempt(TEST_ASSESSMENT_ID)
    
    assert result["total_score"] == 1.0
    assert result["max_score"] == 3.0
    
    skill_py = next(s for s in result["skill_scores"] if s["skill"] == "Python")
    assert skill_py["score"] == 1.0
    assert skill_py["max_score"] == 2.0
    
    skill_react = next(s for s in result["skill_scores"] if s["skill"] == "React")
    assert skill_react["score"] == 0.0

def test_short_answer_scoring_with_mock():
    questions = {
        "questions": [
            {"id": "q1", "type": "short_answer", "skill": "AI", "question": "Explain.", "expected_answer": "...", "evaluation_points": ["a", "b"]}
        ]
    }
    attempt = {
        "answers": {
            "q1": "my short answer"
        }
    }
    save_assessment_questions(TEST_ASSESSMENT_ID, questions)
    save_assessment_attempt(TEST_ASSESSMENT_ID, attempt)
    
    with patch("backend_question_generator.safe_ai_json") as mock_ai:
        mock_ai.return_value = {
            "score": 0.75,
            "evaluation_points_met": ["a"],
            "evaluation_points_missed": ["b"],
            "reason": "good"
        }
        
        result = score_assessment_attempt(TEST_ASSESSMENT_ID)
        
        assert mock_ai.call_count == 1
        assert result["total_score"] == 0.75
        q_res = result["question_results"][0]
        assert q_res["score"] == 0.75
        
        # Test idempotency
        result2 = score_assessment_attempt(TEST_ASSESSMENT_ID)
        assert mock_ai.call_count == 1 # still 1
        assert result2["total_score"] == 0.75

def test_missing_assessment_handling():
    with pytest.raises(ValueError, match="Assessment questions not found"):
        score_assessment_attempt("missing_id")

def test_full_15_questions_scoring():
    questions = {"questions": []}
    attempt = {"answers": {}}
    for i in range(10):
        q_id = f"mcq_{i}"
        questions["questions"].append({"id": q_id, "type": "mcq", "skill": "General", "correct_answer": "A"})
        attempt["answers"][q_id] = "A" # All correct
        
    for i in range(5):
        q_id = f"sa_{i}"
        questions["questions"].append({"id": q_id, "type": "short_answer", "skill": "General"})
        attempt["answers"][q_id] = "answer"
        
    save_assessment_questions(TEST_ASSESSMENT_ID, questions)
    save_assessment_attempt(TEST_ASSESSMENT_ID, attempt)
    
    with patch("backend_question_generator.safe_ai_json") as mock_ai:
        mock_ai.return_value = {"score": 1, "evaluation_points_met": [], "evaluation_points_missed": [], "reason": ""}
        result = score_assessment_attempt(TEST_ASSESSMENT_ID)
        assert result["total_score"] == 15.0
        assert result["max_score"] == 15.0
        assert result["percentage"] == 100.0
