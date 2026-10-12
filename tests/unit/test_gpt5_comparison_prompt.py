"""
Test that GPT-5 comparison prompts explicitly define the required JSON output structure.

This test verifies that the system prompt contains explicit field definitions
to ensure GPT-5 returns the correct JSON structure matching CANDIDATE_COMPARISON_SCHEMA.
"""

import pytest

from backend import (
    format_candidate_comparison_prompt,
    get_gpt5_comparison_system_prompt,
)


def test_gpt5_comparison_system_prompt_contains_required_fields():
    """Test that the GPT-5 comparison system prompt explicitly defines all required JSON fields."""
    system_prompt = get_gpt5_comparison_system_prompt()

    # Required top-level fields
    required_top_level_fields = ["comparison_summary", "candidates", "comparisons"]

    # Required candidate fields
    required_candidate_fields = [
        "candidate_id",
        "candidate_name",
        "strengths",
        "gaps",
        "jd_coverage",
        "evidence",
    ]

    # Required comparison fields
    required_comparison_fields = ["criterion", "candidate_observations", "summary"]

    # Required candidate_observation fields
    required_observation_fields = ["candidate_id", "status", "evidence"]

    # Check that all required fields are explicitly mentioned in the system prompt
    for field in required_top_level_fields:
        assert (
            field in system_prompt
        ), f"System prompt must explicitly mention '{field}' field"

    for field in required_candidate_fields:
        assert (
            field in system_prompt
        ), f"System prompt must explicitly mention '{field}' field"

    for field in required_comparison_fields:
        assert (
            field in system_prompt
        ), f"System prompt must explicitly mention '{field}' field"

    for field in required_observation_fields:
        assert (
            field in system_prompt
        ), f"System prompt must explicitly mention '{field}' field"


def test_gpt5_comparison_system_prompt_forbids_incorrect_fields():
    """Test that the system prompt explicitly forbids incorrect field names."""
    system_prompt = get_gpt5_comparison_system_prompt()

    # Fields that should NOT be in the output
    forbidden_fields = [
        "job_description",
        "comparison",  # singular form should be forbidden
    ]

    # Check that forbidden fields are mentioned in the strict output rules
    for field in forbidden_fields:
        assert (
            field in system_prompt
        ), f"System prompt must mention forbidden field '{field}'"

    # Check that there's a "Do NOT return" statement that includes these fields
    assert (
        "Do NOT return" in system_prompt
    ), "System prompt should contain 'Do NOT return' restrictions"


def test_gpt5_comparison_system_prompt_contains_json_structure():
    """Test that the system prompt contains an explicit JSON structure example."""
    system_prompt = get_gpt5_comparison_system_prompt()

    # Check for JSON structure indicators
    assert "{" in system_prompt, "System prompt should contain JSON structure example"
    assert "}" in system_prompt, "System prompt should contain JSON structure example"
    assert (
        '"comparison_summary"' in system_prompt
    ), "System prompt should show comparison_summary field"
    assert '"candidates"' in system_prompt, "System prompt should show candidates field"
    assert (
        '"comparisons"' in system_prompt
    ), "System prompt should show comparisons field"


def test_gpt5_comparison_user_prompt_reinforces_output_format():
    """Test that the user prompt reinforces the exact output format."""
    # Create mock data for testing
    job_description = {
        "experience": "5+ years",
        "primary_skills": ["Python", "React"],
        "secondary_skills": ["Docker"],
        "education": "Bachelor's degree",
    }

    candidates_data = [
        {
            "candidate_id": "cand1",
            "candidate_name": "John Doe",
            "matching_skills": ["Python"],
            "missing_skills": ["React"],
            "resume_skill_profile": {},
            "justification": "Test justification",
            "candidate_grading": {"grade": "A", "summary": "Test summary"},
            "matching_evidence": [
                {"skill": "Python", "evidence": "Used Python in project"}
            ],
        },
        {
            "candidate_id": "cand2",
            "candidate_name": "Jane Smith",
            "matching_skills": ["React"],
            "missing_skills": ["Python"],
            "resume_skill_profile": {},
            "justification": "Test justification",
            "candidate_grading": {"grade": "B", "summary": "Test summary"},
            "matching_evidence": [{"skill": "React", "evidence": "Built React app"}],
        },
    ]

    user_prompt = format_candidate_comparison_prompt(job_description, candidates_data)

    # Check that user prompt reinforces the output format
    assert (
        "comparison_summary" in user_prompt
    ), "User prompt should reinforce comparison_summary field"
    assert "candidates" in user_prompt, "User prompt should reinforce candidates field"
    assert (
        "comparisons" in user_prompt
    ), "User prompt should reinforce comparisons field"


def test_gpt5_comparison_system_prompt_contains_strict_rules():
    """Test that the system prompt contains strict output rules."""
    system_prompt = get_gpt5_comparison_system_prompt()

    # Check for strict output rules
    assert (
        "STRICT OUTPUT RULES" in system_prompt
    ), "System prompt should contain strict output rules"
    assert (
        "Return ONLY this JSON object" in system_prompt
    ), "System prompt should require ONLY JSON output"
    assert (
        "Do NOT return" in system_prompt
    ), "System prompt should forbid certain fields"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
