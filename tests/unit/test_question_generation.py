"""Unit tests for Question Generation Engine & Validation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import pytest

from backend_question_generator import (
    extract_jd_skills,
    generate_candidate_assessment,
    generate_fallback_questions,
    get_assessment_questions,
    validate_question,
    validate_questions_set,
)


@pytest.fixture(autouse=True)
def isolate_question_store(tmp_path, monkeypatch):
    """Isolate assessment questions storage path to a temporary file during test execution."""
    q_file = tmp_path / "assessment_questions.json"
    monkeypatch.setattr("backend_question_generator.ASSESSMENT_QUESTIONS_PATH", q_file)


def test_mcq_validation():
    """Test MCQ question schema validation."""
    valid_mcq = {
        "id": "q1",
        "question": "What is Python?",
        "type": "mcq",
        "skill": "Python",
        "difficulty": "easy",
        "options": ["Language", "Animal", "Database", "OS"],
        "correct_answer": "Language",
        "explanation": "Python is a programming language.",
    }
    is_valid, msg = validate_question(valid_mcq)
    assert is_valid is True, msg

    # Invalid: missing option
    invalid_mcq = dict(valid_mcq, options=["Language", "Animal"])
    is_valid, msg = validate_question(invalid_mcq)
    assert is_valid is False
    assert "4 options" in msg

    # Invalid: correct_answer not in options
    invalid_mcq2 = dict(valid_mcq, correct_answer="NonExistent")
    is_valid, msg = validate_question(invalid_mcq2)
    assert is_valid is False
    assert "not present in options" in msg


def test_short_answer_validation():
    """Test Short Answer question schema validation."""
    valid_short = {
        "id": "q11",
        "question": "Explain RAG architecture.",
        "type": "short_answer",
        "skill": "RAG",
        "difficulty": "hard",
        "expected_answer": "Retrieval Augmented Generation combines vector search with LLMs.",
        "evaluation_points": ["Vector search", "LLM context window"],
    }
    is_valid, msg = validate_question(valid_short)
    assert is_valid is True, msg

    # Invalid: missing evaluation_points
    invalid_short = dict(valid_short, evaluation_points=[])
    is_valid, msg = validate_question(invalid_short)
    assert is_valid is False
    assert "at least one evaluation point" in msg


def test_question_count_and_types_validation():
    """Test question set count and 10 MCQ / 5 Short Answer ratio validation."""
    skills = ["Python", "SQL", "RAG"]
    questions = generate_fallback_questions(skills)

    is_valid, msg = validate_questions_set(questions)
    assert is_valid is True, msg
    assert len(questions) == 15

    # Test count failure
    is_valid, msg = validate_questions_set(questions[:10])
    assert is_valid is False
    assert "Expected exactly 15 questions" in msg


def test_duplicate_question_detection():
    """Test detection of duplicate question IDs or text."""
    skills = ["Python", "SQL"]
    questions = generate_fallback_questions(skills)

    # Introduce duplicate ID
    questions_dup_id = [dict(q) for q in questions]
    questions_dup_id[1]["id"] = "q1"
    is_valid, msg = validate_questions_set(questions_dup_id)
    assert is_valid is False
    assert "Duplicate question id" in msg

    # Introduce duplicate text
    questions_dup_text = [dict(q) for q in questions]
    questions_dup_text[1]["question"] = questions_dup_text[0]["question"]
    is_valid, msg = validate_questions_set(questions_dup_text)
    assert is_valid is False
    assert "Duplicate question text" in msg


def test_skill_coverage_extraction():
    """Test skill extraction and distribution from JD."""
    jd_data = {
        "job_title": "AI/ML Engineer",
        "primary_skills": "Python, SQL, Machine Learning, RAG, LLMs",
        "secondary_skills": "Docker, FastAPI, Git",
    }
    extracted = extract_jd_skills(jd_data)
    assert "Python" in extracted
    assert "SQL" in extracted
    assert "Machine Learning" in extracted or "RAG" in extracted


def test_assessment_id_association_and_persistence(tmp_path, monkeypatch):
    """Test assessment persistence tied to assessment_id and candidate_id."""
    temp_file = tmp_path / "test_questions.json"
    monkeypatch.setattr(
        "backend_question_generator.ASSESSMENT_QUESTIONS_PATH", temp_file
    )

    assessment_id = "test_asm_123"
    candidate_id = "cand_456"
    jd = {"job_title": "Full Stack Dev", "primary_skills": "Python, React"}
    resume = {
        "candidate_name": "Test Candidate",
        "skills": {"technical_skills": ["Python"]},
    }

    payload = generate_candidate_assessment(
        assessment_id=assessment_id,
        candidate_id=candidate_id,
        job_description=jd,
        candidate_resume=resume,
        job_role="Full Stack Dev",
    )

    assert payload["assessment_id"] == assessment_id
    assert payload["candidate_id"] == candidate_id
    assert len(payload["questions"]) == 15

    # Retrieve persisted questions
    persisted = get_assessment_questions(assessment_id)
    assert persisted is not None
    assert persisted["assessment_id"] == assessment_id
    assert len(persisted["questions"]) == 15


def test_failure_handling_invalid_llm_json(monkeypatch):
    """Test graceful fallback handling when LLM returns invalid JSON or errors."""

    def mock_bad_llm(*args, **kwargs):
        return None

    monkeypatch.setattr("backend_question_generator.safe_ai_json", mock_bad_llm)

    payload = generate_candidate_assessment(
        assessment_id="test_asm_fail_1",
        candidate_id="cand_fail_1",
        job_description="Need Python and SQL Developer.",
        job_role="Python Developer",
    )

    assert payload is not None
    assert payload["generation_source"] == "fallback"
    assert len(payload["questions"]) == 15
    is_valid, msg = validate_questions_set(payload["questions"])
    assert is_valid is True, msg
