import os
import pytest
from unittest.mock import patch
from backend_question_generator import (
    score_assessment_attempt,
    save_assessment_result,
    save_assessment_attempt,
    save_assessment_questions,
    ASSESSMENT_RESULTS_PATH,
    ASSESSMENT_ATTEMPTS_PATH,
    ASSESSMENT_QUESTIONS_PATH
)

TEST_ASSESSMENT_ID = "test_score_id"

@pytest.fixture(autouse=True)
def isolate_test_stores(tmp_path, monkeypatch):
    """Isolate assessment storage paths to temporary files during pytest execution to prevent touching vector_store runtime data."""
    q_file = tmp_path / "assessment_questions.json"
    att_file = tmp_path / "assessment_attempts.json"
    res_file = tmp_path / "assessment_results.json"

    monkeypatch.setattr("backend_question_generator.ASSESSMENT_QUESTIONS_PATH", q_file)
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_ATTEMPTS_PATH", att_file)
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_RESULTS_PATH", res_file)

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
