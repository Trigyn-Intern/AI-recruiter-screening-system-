"""
Test that the resume skill extraction prompt template includes contact_info.
"""

from backend import DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE


def test_prompt_template_includes_contact_info():
    """Test that the prompt template includes contact_info in the JSON format."""
    assert "contact_info" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    assert "email" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    assert "phone" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    assert "linkedin" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    assert "github" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE


def test_prompt_template_contact_extraction_rules():
    """Test that the prompt template includes rules for contact extraction."""
    assert (
        "Extract contact information" in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    )
    assert (
        "email, phone, LinkedIn, GitHub"
        in DEFAULT_RESUME_SKILL_EXTRACTION_PROMPT_TEMPLATE
    )


if __name__ == "__main__":
    test_prompt_template_includes_contact_info()
    test_prompt_template_contact_extraction_rules()
    print("All prompt template tests passed!")
