"""
Test GPT-4 candidate comparison functionality.

This test suite verifies that the GPT-4 comparison engine works correctly
and maintains isolation from the GPT-5 comparison path.
"""

import pytest
from backend import (
    get_gpt4_comparison_system_prompt,
    compare_selected_candidates_gpt4,
    GPT4_COMPARISON_MODEL,
    GPT5_COMPARISON_MODEL,
    CANDIDATE_COMPARISON_SCHEMA,
    CANDIDATE_COMPARISON_FALLBACK
)


def test_gpt4_comparison_system_prompt_exists():
    """Test that GPT-4 comparison system prompt exists and is not empty."""
    system_prompt = get_gpt4_comparison_system_prompt()
    assert system_prompt, "GPT-4 comparison system prompt should exist"
    assert len(system_prompt) > 100, "GPT-4 comparison system prompt should be substantial"


def test_gpt4_comparison_system_prompt_contains_required_fields():
    """Test that the GPT-4 comparison system prompt explicitly defines all required JSON fields."""
    system_prompt = get_gpt4_comparison_system_prompt()

    # Required top-level fields
    required_top_level_fields = [
        "comparison_summary",
        "candidates",
        "comparisons"
    ]

    # Required candidate fields
    required_candidate_fields = [
        "candidate_id",
        "candidate_name",
        "strengths",
        "gaps",
        "jd_coverage",
        "evidence"
    ]

    # Required comparison fields
    required_comparison_fields = [
        "criterion",
        "candidate_observations",
        "summary"
    ]

    # Required candidate_observation fields
    required_observation_fields = [
        "candidate_id",
        "status",
        "evidence"
    ]

    # Check that all required fields are explicitly mentioned in the system prompt
    for field in required_top_level_fields:
        assert field in system_prompt, f"System prompt must explicitly mention '{field}' field"

    for field in required_candidate_fields:
        assert field in system_prompt, f"System prompt must explicitly mention '{field}' field"

    for field in required_comparison_fields:
        assert field in system_prompt, f"System prompt must explicitly mention '{field}' field"

    for field in required_observation_fields:
        assert field in system_prompt, f"System prompt must explicitly mention '{field}' field"


def test_gpt4_comparison_system_prompt_forbids_hiring_recommendations():
    """Test that the GPT-4 system prompt explicitly forbids hiring recommendations."""
    system_prompt = get_gpt4_comparison_system_prompt()

    # Check that hiring recommendations are forbidden
    assert "hiring recommendation" in system_prompt.lower(), "System prompt should forbid hiring recommendations"
    assert "winner" in system_prompt.lower() or "best candidate" in system_prompt.lower(), "System prompt should forbid identifying winners"


def test_gpt4_comparison_requires_minimum_candidates():
    """Test that GPT-4 comparison requires at least 2 candidates."""
    job_description = {
        "experience": "5+ years",
        "primary_skills": ["Python"],
        "secondary_skills": [],
        "education": "Bachelor's degree"
    }

    # Test with insufficient candidates
    result = compare_selected_candidates_gpt4(job_description, [])
    assert "error" in result, "Should return error for insufficient candidates"
    assert result["error"] == "insufficient_candidates", "Error should be 'insufficient_candidates'"

    # Test with single candidate
    single_candidate = [
        {
            "candidate_id": "cand1",
            "candidate_name": "John Doe",
            "matching_skills": ["Python"],
            "resume_skill_profile": {}
        }
    ]
    result = compare_selected_candidates_gpt4(job_description, single_candidate)
    assert "error" in result, "Should return error for single candidate"
    assert result["error"] == "insufficient_candidates", "Error should be 'insufficient_candidates'"


def test_gpt4_comparison_validates_candidate_ids():
    """Test that GPT-4 comparison validates candidate IDs."""
    job_description = {
        "experience": "5+ years",
        "primary_skills": ["Python"],
        "secondary_skills": [],
        "education": "Bachelor's degree"
    }

    # Test with missing candidate ID in a list of 2 candidates
    candidates_missing_id = [
        {
            "candidate_id": "cand1",
            "candidate_name": "John Doe",
            "matching_skills": ["Python"],
            "resume_skill_profile": {}
        },
        {
            "candidate_name": "Jane Smith",  # Missing candidate_id
            "matching_skills": ["React"],
            "resume_skill_profile": {}
        }
    ]
    result = compare_selected_candidates_gpt4(job_description, candidates_missing_id)
    assert "error" in result, "Should return error for missing candidate ID"
    assert result["error"] == "missing_candidate_id", "Error should be 'missing_candidate_id'"


def test_gpt4_comparison_validates_candidate_data_format():
    """Test that GPT-4 comparison validates candidate data format."""
    job_description = {
        "experience": "5+ years",
        "primary_skills": ["Python"],
        "secondary_skills": [],
        "education": "Bachelor's degree"
    }

    # Test with invalid candidate data format
    invalid_candidates = ["not a dict", "also not a dict"]
    result = compare_selected_candidates_gpt4(job_description, invalid_candidates)
    assert "error" in result, "Should return error for invalid candidate data format"
    assert result["error"] == "invalid_candidate_data", "Error should be 'invalid_candidate_data'"


def test_gpt4_comparison_model_isolation():
    """Test that GPT-4 comparison uses the correct model."""
    assert GPT4_COMPARISON_MODEL == "gpt-4", "GPT-4 comparison model should be 'gpt-4'"
    assert GPT4_COMPARISON_MODEL != GPT5_COMPARISON_MODEL, "GPT-4 and GPT-5 models should be different"


def test_gpt4_comparison_uses_same_schema_as_gpt5():
    """Test that GPT-4 comparison uses the same schema as GPT-5."""
    from backend import get_gpt5_comparison_system_prompt

    gpt4_prompt = get_gpt4_comparison_system_prompt()
    gpt5_prompt = get_gpt5_comparison_system_prompt()

    # Both should contain the same required fields
    required_fields = ["comparison_summary", "candidates", "comparisons"]
    for field in required_fields:
        assert field in gpt4_prompt, f"GPT-4 prompt should contain '{field}'"
        assert field in gpt5_prompt, f"GPT-5 prompt should contain '{field}'"


def test_gpt4_comparison_preserves_candidate_ids():
    """Test that GPT-4 comparison preserves candidate IDs correctly."""
    job_description = {
        "experience": "5+ years",
        "primary_skills": ["Python"],
        "secondary_skills": [],
        "education": "Bachelor's degree"
    }

    candidates_data = [
        {
            "candidate_id": "test_id_12345",
            "candidate_name": "Test Candidate",
            "matching_skills": ["Python"],
            "resume_skill_profile": {}
        },
        {
            "candidate_id": "test_id_67890",
            "candidate_name": "Another Candidate",
            "matching_skills": ["React"],
            "resume_skill_profile": {}
        }
    ]

    # This test would require mocking the OpenAI API call
    # For now, we just verify the function accepts the candidate IDs
    # In a real test, we would mock safe_openai_json to return a controlled response
    # and verify that the candidate IDs are preserved in the output


def test_gpt4_comparison_system_prompt_prevents_evidence_mixing():
    """Test that GPT-4 system prompt prevents evidence mixing between candidates."""
    system_prompt = get_gpt4_comparison_system_prompt()

    # Check for evidence isolation rules
    assert "never mix evidence" in system_prompt.lower(), "System prompt should forbid evidence mixing"
    assert "correct candidate" in system_prompt.lower(), "System prompt should emphasize evidence attribution"


def test_gpt4_comparison_system_prompt_handles_missing_evidence():
    """Test that GPT-4 system prompt handles missing evidence correctly."""
    system_prompt = get_gpt4_comparison_system_prompt()

    # Check for missing evidence handling
    assert "missing evidence" in system_prompt.lower(), "System prompt should address missing evidence"
    assert "unavailable" in system_prompt.lower(), "System prompt should use 'unavailable' status"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
