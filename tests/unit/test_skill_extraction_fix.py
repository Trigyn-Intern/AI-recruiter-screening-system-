import json
import pytest

def test_get_resume_profile_skills_extracts_from_evidence():
    """Test that get_resume_profile_skills extracts skills from skill_evidence entries."""
    from backend import get_resume_profile_skills

    # Create a test profile similar to resume-1.pdf structure
    test_profile = {
        "technical_skills": ["Java", "JavaScript", "SQL"],
        "soft_skills": ["Communication"],
        "tools": ["Excel"],
        "domains": [],
        "skill_evidence": [
            {
                "skill": "Java",
                "evidence": "2012, Java Script and JQuery, Power Shell, InfoPath Forms, SQL Server"
            },
            {
                "skill": "SQL",
                "evidence": "Environment : SharePoint Server 2013, Office 365, ASP.NET, C#, HTML, SQL Server"
            },
            {
                "skill": "Web parts",
                "evidence": "Development of Custom Web parts, Editor Parts, Event Receivers"
            }
        ]
    }

    extracted_skills = get_resume_profile_skills(test_profile)

    # Should include skills from technical_skills and skill_evidence
    assert "Java" in extracted_skills
    assert "JavaScript" in extracted_skills
    assert "SQL" in extracted_skills
    assert "Web parts" in extracted_skills

    # Should extract technical terms from evidence text
    assert "ASP.NET" in extracted_skills  # From evidence text with dot pattern
    assert "C#" in extracted_skills  # From evidence text with hash pattern

def test_skill_extraction_handles_missing_evidence():
    """Test that get_resume_profile_skills handles profiles without skill_evidence."""
    from backend import get_resume_profile_skills

    test_profile = {
        "technical_skills": ["Python", "React"],
        "soft_skills": [],
        "tools": [],
        "domains": []
    }

    extracted_skills = get_resume_profile_skills(test_profile)

    assert "Python" in extracted_skills
    assert "React" in extracted_skills
    assert len(extracted_skills) == 2

def test_skill_extraction_removes_duplicates():
    """Test that get_resume_profile_skills removes duplicate skills."""
    from backend import get_resume_profile_skills

    test_profile = {
        "technical_skills": ["Python", "React"],
        "skill_evidence": [
            {"skill": "Python", "evidence": "Python development"},
            {"skill": "React", "evidence": "React development"}
        ]
    }

    extracted_skills = get_resume_profile_skills(test_profile)

    # Should not have duplicates
    assert len(extracted_skills) == len(set(extracted_skills))
    assert "Python" in extracted_skills
    assert "React" in extracted_skills

def test_indexed_candidate_detail_with_fixed_extraction():
    """Test that build_indexed_candidate_detail uses the improved skill extraction."""
    from backend import build_indexed_candidate_detail

    # Test profile similar to resume-1.pdf
    test_profile = {
        "technical_skills": ["Java", "JavaScript", "SQL"],
        "skill_evidence": [
            {
                "skill": "SQL",
                "evidence": "Environment : SharePoint Server 2013, Office 365, ASP.NET, C#, HTML, SQL Server"
            },
            {
                "skill": "Web parts",
                "evidence": "Development of Custom Web parts, Editor Parts, Event Receivers"
            }
        ]
    }

    job_description = "We need a SharePoint Developer with C#, ASP.NET, and Web Parts experience."

    result = build_indexed_candidate_detail(test_profile, job_description, 75.0)

    # Should not mark C#, ASP.NET, Web Parts as missing since they're in evidence
    missing_skills = result.get("missing_skills", [])

    # Check that key technical skills are not incorrectly marked as missing
    assert "C#" not in missing_skills, "C# should not be marked as missing"
    assert "ASP.NET" not in missing_skills, "ASP.NET should not be marked as missing"
    assert "Web Parts" not in missing_skills, "Web Parts should not be marked as missing"

    # These should be in matching skills
    matching_skills = result.get("matching_skills", [])
    assert len(matching_skills) > 0, "Should have matching skills"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
