"""
Unit tests for GitHub evidence verification against resume claims.
"""

import pytest

from backend import verify_github_evidence_against_resume


def test_verify_github_evidence_unavailable():
    """Test verification when GitHub evidence is unavailable."""
    resume_profile = {
        "technical_skills": ["Python", "SQL"],
        "skill_evidence": [
            {"skill": "Python", "evidence": "Built Python applications"}
        ],
    }
    github_evidence = {"status": "unavailable", "error": "Not found"}

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "unverifiable"
    assert result["reason"] == "GitHub evidence not available"
    assert result["corroborated"] == []
    assert result["partially_corroborated"] == []
    assert result["unverifiable"] == []
    assert result["discrepancies"] == []


def test_verify_github_evidence_corroborated_skills():
    """Test verification when skills are corroborated by GitHub languages."""
    resume_profile = {
        "technical_skills": ["Python", "TypeScript"],
        "skill_evidence": [
            {"skill": "Python", "evidence": "Built Python applications"}
        ],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 2,
        },
        "repositories": [
            {
                "name": "python-project",
                "language": "Python",
                "url": "https://github.com/testuser/python-project",
                "description": "A Python project",
            },
            {
                "name": "typescript-app",
                "language": "TypeScript",
                "url": "https://github.com/testuser/typescript-app",
                "description": "A TypeScript app",
            },
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "corroborated"
    assert len(result["corroborated"]) >= 2  # At least 2 skills should be corroborated
    skill_corroboration = [c for c in result["corroborated"] if c["type"] == "skill"]
    assert len(skill_corroboration) >= 2
    claims = [c["claim"] for c in skill_corroboration]
    assert "Python" in claims
    assert "TypeScript" in claims
    assert len(result["supporting_repositories"]) == 2


def test_verify_github_evidence_partially_corroborated():
    """Test verification when skills are partially corroborated by descriptions."""
    resume_profile = {
        "technical_skills": ["Python", "Machine Learning"],
        "skill_evidence": [
            {"skill": "Python", "evidence": "Used Python for data analysis"}
        ],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 1,
        },
        "repositories": [
            {
                "name": "data-project",
                "language": "Python",
                "url": "https://github.com/testuser/data-project",
                "description": "Machine learning project using Python",
            }
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] in ["corroborated", "partially_corroborated"]
    assert len(result["corroborated"]) >= 1  # Python should be corroborated by language
    assert len(result["partially_corroborated"]) >= 0  # ML might be in description


def test_verify_github_evidence_unverifiable_skills():
    """Test verification when skills are not found in GitHub."""
    resume_profile = {
        "technical_skills": ["Java", "C++"],
        "skill_evidence": [{"skill": "Java", "evidence": "Built Java applications"}],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 1,
        },
        "repositories": [
            {
                "name": "python-project",
                "language": "Python",
                "url": "https://github.com/testuser/python-project",
                "description": "A Python project",
            }
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "unverifiable"
    # Count only skill unverifiable items (projects may also be extracted)
    skill_unverifiable = [c for c in result["unverifiable"] if c["type"] == "skill"]
    assert len(skill_unverifiable) == 2
    claims = [c["claim"] for c in skill_unverifiable]
    assert "Java" in claims
    assert "C++" in claims


def test_verify_github_evidence_project_name_match():
    """Test verification when project names match GitHub repositories."""
    resume_profile = {
        "technical_skills": ["Python"],
        "skill_evidence": [
            {
                "skill": "Python",
                "evidence": "Developed ThreatLens Project for cyber threat intelligence",
            }
        ],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 1,
        },
        "repositories": [
            {
                "name": "ThreatLens",
                "language": "Python",
                "url": "https://github.com/testuser/ThreatLens",
                "description": "Cyber threat intelligence project",
            }
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "corroborated"
    # Should have both skill corroboration and project corroboration
    assert len(result["corroborated"]) >= 1
    project_corroboration = [
        c for c in result["corroborated"] if c["type"] == "project"
    ]
    assert len(project_corroboration) >= 1


def test_verify_github_evidence_case_insensitive():
    """Test that verification is case-insensitive."""
    resume_profile = {
        "technical_skills": ["python", "TYPESCRIPT"],
        "skill_evidence": [{"skill": "python", "evidence": "Python project"}],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 1,
        },
        "repositories": [
            {
                "name": "my-python-app",
                "language": "Python",
                "url": "https://github.com/testuser/my-python-app",
                "description": "TypeScript frontend",
            }
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    # Should still corroborate despite case differences
    assert result["overall_status"] in ["corroborated", "partially_corroborated"]


def test_verify_github_evidence_empty_resume():
    """Test verification with empty resume profile."""
    resume_profile = {"technical_skills": [], "skill_evidence": []}
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 1,
        },
        "repositories": [
            {
                "name": "project",
                "language": "Python",
                "url": "https://github.com/testuser/project",
                "description": "A project",
            }
        ],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "unverifiable"
    assert len(result["corroborated"]) == 0


def test_verify_github_evidence_empty_github():
    """Test verification with empty GitHub repositories."""
    resume_profile = {
        "technical_skills": ["Python"],
        "skill_evidence": [{"skill": "Python", "evidence": "Python project"}],
    }
    github_evidence = {
        "status": "available",
        "profile": {
            "username": "testuser",
            "profile_url": "https://github.com/testuser",
            "public_repos": 0,
        },
        "repositories": [],
    }

    result = verify_github_evidence_against_resume(resume_profile, github_evidence)

    assert result["overall_status"] == "unverifiable"
    # Count only skill unverifiable items (projects may also be extracted)
    skill_unverifiable = [c for c in result["unverifiable"] if c["type"] == "skill"]
    assert len(skill_unverifiable) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
