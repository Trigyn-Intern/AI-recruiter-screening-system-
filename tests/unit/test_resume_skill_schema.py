"""
Test that RESUME_SKILL_SCHEMA includes contact_info and can be returned by Gemini.
"""

import pytest
from jsonschema import validate

from backend import RESUME_SKILL_FALLBACK, RESUME_SKILL_SCHEMA, normalize_skill_evidence


def test_resume_skill_schema_includes_contact_info():
    """Test that RESUME_SKILL_SCHEMA includes contact_info property."""
    assert "properties" in RESUME_SKILL_SCHEMA
    assert "contact_info" in RESUME_SKILL_SCHEMA["properties"]

    contact_info_schema = RESUME_SKILL_SCHEMA["properties"]["contact_info"]
    assert contact_info_schema["type"] == "object"

    # Verify contact_info structure
    contact_properties = contact_info_schema["properties"]
    assert "email" in contact_properties
    assert "phone" in contact_properties
    assert "linkedin" in contact_properties
    assert "github" in contact_properties

    # Verify they accept strings and the fallback's missing-value nulls
    for field in ["email", "phone", "linkedin", "github"]:
        assert contact_properties[field]["type"] == ["string", "null"]


def test_resume_skill_schema_structure():
    """Test that the overall schema structure is intact."""
    assert RESUME_SKILL_SCHEMA["type"] == "object"

    # Verify required fields
    required_fields = RESUME_SKILL_SCHEMA["required"]
    assert "technical_skills" in required_fields
    assert "soft_skills" in required_fields
    assert "tools" in required_fields
    assert "domains" in required_fields
    assert "experience_summary" in required_fields

    # Verify contact_info is NOT required (allows missing contact)
    assert "contact_info" not in required_fields

    # Verify all expected properties exist
    properties = RESUME_SKILL_SCHEMA["properties"]
    assert "technical_skills" in properties
    assert "soft_skills" in properties
    assert "tools" in properties
    assert "domains" in properties
    assert "experience_summary" in properties
    assert "skill_evidence" in properties
    assert "contact_info" in properties


def test_contact_info_field_definitions():
    """Test that contact_info fields match the expected structure."""
    contact_info_schema = RESUME_SKILL_SCHEMA["properties"]["contact_info"]
    properties = contact_info_schema["properties"]

    # Verify each contact field accepts strings and nulls
    for field in ["email", "phone", "linkedin", "github"]:
        assert field in properties
        assert properties[field]["type"] == ["string", "null"]


def test_schema_allows_missing_contact_fields():
    """Test that the schema allows contact fields to be missing/null."""
    # contact_info is not in required fields, so it's optional
    required_fields = RESUME_SKILL_SCHEMA["required"]
    assert "contact_info" not in required_fields

    # Individual contact fields are not required within contact_info
    contact_info_schema = RESUME_SKILL_SCHEMA["properties"]["contact_info"]
    # contact_info doesn't have a required list, so all fields are optional
    assert "required" not in contact_info_schema


def test_resume_skill_fallback_validates_against_schema():
    validate(instance=RESUME_SKILL_FALLBACK, schema=RESUME_SKILL_SCHEMA)


def test_normalize_skill_evidence_preserves_chunk_id():
    result = normalize_skill_evidence(
        [
            {
                "skill": "Python",
                "evidence": "Built Python",
                "source": "Work",
                "chunk_id": "resume_chunk_001",
            }
        ]
    )

    assert result == [
        {
            "skill": "Python",
            "evidence": "Built Python",
            "source": "Work",
            "chunk_id": "resume_chunk_001",
        }
    ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
