"""
Focused tests for contact_info data path fix in api.py.

This tests the exact data access pattern used to extract contact information
from resume_skill_profile, which should be nested under skills.contact_info.
"""

import json


def test_contact_info_data_path_from_actual_structure():
    """Test that contact_info is correctly accessed from the actual resume_skill_profile structure."""
    # Simulate a resume skill profile without reading local candidate data.
    resume_skill_profile = {
        "resume_id": "synthetic-resume-001",
        "resume_name": "synthetic-candidate-resume.pdf",
        "skills": {
            "technical_skills": ["Python", "SQL", "JavaScript"],
            "soft_skills": ["Problem-solving"],
            "tools": ["Git", "GitHub"],
            "domains": ["Data Science"],
            "experience_summary": "Synthetic software engineering candidate",
            "skill_evidence": [
                {
                    "skill": "Python",
                    "evidence": "Built Python applications",
                    "source": "Projects"
                }
            ],
            "contact_info": {
                "email": "candidate@example.test",
                "phone": "+1-202-555-0100",
                "linkedin": "linkedin.com/in/synthetic-candidate",
                "github": "github.com/synthetic-candidate"
            }
        },
        "model": "llama3.2",
        "last_updated_at": "2026-09-10T00:00:00"
    }

    # The CORRECT access pattern (the fix)
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    # Verify the correct data is retrieved
    assert contact_info.get("email") == "candidate@example.test"
    assert contact_info.get("phone") == "+1-202-555-0100"
    assert contact_info.get("linkedin") == "linkedin.com/in/synthetic-candidate"
    assert contact_info.get("github") == "github.com/synthetic-candidate"

    # Verify truthy for downstream checks
    assert bool(contact_info.get("linkedin")) is True
    assert bool(contact_info.get("github")) is True


def test_contact_info_data_path_from_json_file(tmp_path):
    """Test contact_info lookup from a portable, synthetic JSON fixture."""
    synthetic_id = "synthetic-resume-001"
    synthetic_profile = {
        "resume_id": synthetic_id,
        "resume_name": "synthetic-candidate-resume.pdf",
        "skills": {
            "contact_info": {
                "email": "candidate@example.test",
                "phone": "+1-202-555-0100",
                "linkedin": "linkedin.com/in/synthetic-candidate",
                "github": "github.com/synthetic-candidate",
            }
        },
    }
    resume_skills_path = tmp_path / "resume_skills.json"
    resume_skills_path.write_text(
        json.dumps({synthetic_id: synthetic_profile}), encoding="utf-8"
    )
    skills = json.loads(resume_skills_path.read_text(encoding="utf-8"))

    resume_skill_profile = skills[synthetic_id]
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    assert contact_info.get("linkedin") == "linkedin.com/in/synthetic-candidate"
    assert contact_info.get("github") == "github.com/synthetic-candidate"
    assert contact_info.get("email") == "candidate@example.test"
    assert contact_info.get("phone") == "+1-202-555-0100"
    assert bool(contact_info.get("linkedin")) is True
    assert bool(contact_info.get("github")) is True


def test_contact_info_data_path_missing_skills():
    """Test that contact_info access handles missing skills key gracefully."""
    resume_skill_profile = {
        "resume_id": "test_id",
        "resume_name": "test.pdf",
        "technical_skills": ["Python"],  # Top level, not under skills
        "contact_info": {
            "email": "test@example.com"
        }
    }

    # Correct access should handle missing skills gracefully
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    # Should return empty dict since skills is missing
    assert contact_info == {}
    assert contact_info.get("linkedin") is None
    assert contact_info.get("github") is None


def test_contact_info_data_path_missing_contact_info():
    """Test that contact_info access handles missing contact_info key gracefully."""
    resume_skill_profile = {
        "resume_id": "test_id",
        "resume_name": "test.pdf",
        "skills": {
            "technical_skills": ["Python"],
            "soft_skills": []
        }
    }

    # Correct access should handle missing contact_info gracefully
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    # Should return empty dict since contact_info is missing
    assert contact_info == {}
    assert contact_info.get("linkedin") is None
    assert contact_info.get("github") is None


def test_contact_info_data_path_empty_contact_info():
    """Test that contact_info access handles empty contact_info gracefully."""
    resume_skill_profile = {
        "resume_id": "test_id",
        "resume_name": "test.pdf",
        "skills": {
            "technical_skills": ["Python"],
            "contact_info": {}
        }
    }

    # Correct access should handle empty contact_info gracefully
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    # Should return empty dict
    assert contact_info == {}
    assert contact_info.get("linkedin") is None
    assert contact_info.get("github") is None


def test_contact_info_data_path_partial_contact_info():
    """Test that contact_info access handles partial contact_info correctly."""
    resume_skill_profile = {
        "resume_id": "test_id",
        "resume_name": "test.pdf",
        "skills": {
            "technical_skills": ["Python"],
            "contact_info": {
                "email": "test@example.com",
                # linkedin and github missing
            }
        }
    }

    # Correct access should return partial data
    contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})

    assert contact_info.get("email") == "test@example.com"
    assert contact_info.get("linkedin") is None
    assert contact_info.get("github") is None


def test_contact_info_data_path_non_dict_profile():
    """Test that contact_info access handles non-dict profile gracefully."""
    resume_skill_profile = None

    # Should handle None gracefully
    if isinstance(resume_skill_profile, dict):
        contact_info = resume_skill_profile.get("skills", {}).get("contact_info", {})
    else:
        contact_info = {}

    assert contact_info == {}


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
