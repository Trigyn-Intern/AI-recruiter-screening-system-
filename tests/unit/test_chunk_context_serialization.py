"""
Test that build_resume_analysis_context produces correct context strings.

This test verifies that the function handles different combinations of
resume_text and resume_skill_profile inputs, ensuring correct context
assembly for downstream AI analysis.
"""

import pytest

from backend import build_resume_analysis_context


def test_chunk_context_with_text_and_profile():
    """Test that context includes both raw text and indexed profile when both are present."""
    resume_skill_profile = {
        "resume_id": "resume1",
        "technical_skills": ["Python", "React"],
        "soft_skills": ["Communication"],
        "tools": ["Docker"],
        "domains": ["Web Development"],
        "skill_evidence": [
            {
                "skill": "Python",
                "evidence": "Experience in Python development",
                "source": "Resume text",
            },
            {
                "skill": "React",
                "evidence": "Experience in React framework",
                "source": "Resume text",
            },
        ],
    }

    context = build_resume_analysis_context(
        resume_text="John Doe\nSoftware Engineer\nExperience in Python development",
        resume_skill_profile=resume_skill_profile,
    )

    # Should include both raw text and indexed profile
    assert isinstance(context, str)
    assert "RAW RESUME TEXT:" in context
    assert "INDEXED RESUME PROFILE:" in context
    assert "John Doe" in context
    assert "Python" in context


def test_chunk_context_with_text_only():
    """Test that text-only input returns just the resume text."""
    context = build_resume_analysis_context(
        resume_text="Jane Smith\nData Scientist\nSkills in data analysis",
        resume_skill_profile=None,
    )

    assert isinstance(context, str)
    assert "Jane Smith" in context
    assert "Data Scientist" in context


def test_chunk_context_with_none_text():
    """Test that None/empty resume text with no profile returns empty string."""
    context = build_resume_analysis_context(
        resume_text=None,
        resume_skill_profile=None,
    )

    assert context == ""


def test_chunk_context_with_empty_text():
    """Test that empty string resume text with no profile returns empty string."""
    context = build_resume_analysis_context(
        resume_text="",
        resume_skill_profile=None,
    )

    assert context == ""


def test_chunk_context_with_profile_only():
    """Test that profile-only input returns indexed profile context."""
    resume_skill_profile = {
        "resume_id": "resume2",
        "technical_skills": ["SQL", "Python"],
        "soft_skills": [],
        "tools": [],
        "domains": [],
        "skill_evidence": [
            {
                "skill": "SQL",
                "evidence": "Queried databases using SQL",
                "source": "Resume text",
            }
        ],
    }

    context = build_resume_analysis_context(
        resume_text=None,
        resume_skill_profile=resume_skill_profile,
    )

    assert isinstance(context, str)
    assert "INDEXED RESUME PROFILE:" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
