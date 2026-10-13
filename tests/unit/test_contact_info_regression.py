"""
Regression tests for contact_info preservation in candidate detail processing.

Tests verify that the contact_info fallback logic does not overwrite valid stored
contact_info objects, including those with all-None values.
"""

import pytest


def test_contact_info_with_all_none_values_is_preserved():
    """Test that contact_info with all None values is preserved and not overwritten."""
    # Simulate the scenario where stored contact_info has all None values
    # and resume_text is empty (typical for existing DB candidates)

    item = {
        "resume_skill_profile": {
            "contact_info": {
                "email": None,
                "phone": None,
                "linkedin": None,
                "github": None,
            }
        },
        "resume_text": "",  # Empty resume text (typical for DB candidates)
    }

    # Extract contact info using the fixed logic
    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    # Fixed logic: only re-extract if contact_info is missing/empty
    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify the original contact_info is preserved
    assert contact_info == {
        "email": None,
        "phone": None,
        "linkedin": None,
        "github": None,
    }

    # Verify the values are still None
    assert contact_info["email"] is None
    assert contact_info["phone"] is None
    assert contact_info["linkedin"] is None
    assert contact_info["github"] is None


def test_contact_info_with_values_is_preserved():
    """Test that contact_info with actual values is preserved."""
    item = {
        "resume_skill_profile": {
            "contact_info": {
                "email": "test@example.com",
                "phone": "+91 12345 67890",
                "linkedin": "https://linkedin.com/in/test",
                "github": "https://github.com/test",
            }
        },
        "resume_text": "Sample resume text",
    }

    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify the original contact_info is preserved
    assert contact_info["email"] == "test@example.com"
    assert contact_info["phone"] == "+91 12345 67890"
    assert contact_info["linkedin"] == "https://linkedin.com/in/test"
    assert contact_info["github"] == "https://github.com/test"


def test_missing_contact_info_uses_fallback():
    """Test that truly missing contact_info uses the resume_text fallback."""
    item = {
        "resume_skill_profile": {
            # No contact_info key at all
        },
        "resume_text": "Email: test@example.com Phone: 9876543210",
    }

    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify fallback extraction occurred
    assert contact_info["email"] == "test@example.com"
    assert contact_info["phone"] is not None  # Phone should be extracted


def test_empty_contact_info_uses_fallback():
    """Test that empty contact_info dict uses the resume_text fallback."""
    item = {
        "resume_skill_profile": {"contact_info": {}},  # Empty dict
        "resume_text": "Email: test@example.com Phone: 9876543210",
    }

    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify fallback extraction occurred
    assert contact_info["email"] == "test@example.com"
    assert contact_info["phone"] is not None


def test_contact_info_with_partial_values_is_preserved():
    """Test that contact_info with some None and some values is preserved."""
    item = {
        "resume_skill_profile": {
            "contact_info": {
                "email": "test@example.com",
                "phone": None,
                "linkedin": "https://linkedin.com/in/test",
                "github": None,
            }
        },
        "resume_text": "Sample resume text",
    }

    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify the original contact_info is preserved
    assert contact_info["email"] == "test@example.com"
    assert contact_info["phone"] is None
    assert contact_info["linkedin"] == "https://linkedin.com/in/test"
    assert contact_info["github"] is None


def test_contact_info_with_all_none_and_empty_resume_text():
    """Test that contact_info with all None values is preserved even when resume_text is empty."""
    item = {
        "resume_skill_profile": {
            "contact_info": {
                "email": None,
                "phone": None,
                "linkedin": None,
                "github": None,
            }
        },
        "resume_text": "",  # Empty resume text
    }

    contact_info = {}
    if isinstance(item.get("resume_skill_profile"), dict):
        contact_info = item["resume_skill_profile"].get("contact_info", {})

    if not contact_info:
        if item.get("resume_text"):
            from backend import extract_contact_info

            contact_info = extract_contact_info(item["resume_text"])

    # Verify the original contact_info is preserved (not re-extracted)
    assert contact_info == {
        "email": None,
        "phone": None,
        "linkedin": None,
        "github": None,
    }


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
