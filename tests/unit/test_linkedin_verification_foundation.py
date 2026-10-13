"""Focused tests for LinkedIn verification foundation (Phase 1A).

Tests only the backend foundation without API integration.
"""

from unittest.mock import patch

import pytest

from backend import (
    DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT,
    DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE,
    LINKEDIN_VERIFICATION_FALLBACK,
    LINKEDIN_VERIFICATION_SCHEMA,
    RESUME_SKILL_FALLBACK,
    RESUME_SKILL_SCHEMA,
    extract_contact_info,
    normalize_captapi_response,
    normalize_linkedin_profile_url,
    normalize_linkedin_url,
    normalize_phone_number,
    safe_ai_json,
    safe_gemini_json,
    safe_ollama_json,
    verify_linkedin_evidence_against_resume,
)


def test_linkedin_system_prompt_exists():
    """Test that LinkedIn verification system prompt constant exists."""
    assert DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT is not None
    assert len(DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT) > 100
    assert (
        "Evidence Verification Assistant" in DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT
    )
    assert "identity_confirmed" in DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT


def test_linkedin_user_prompt_template_exists():
    """Test that LinkedIn verification user prompt template exists."""
    assert DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE is not None
    assert len(DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE) > 50
    assert "<job_requirements>" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE
    assert "<resume_evidence>" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE
    assert "<linkedin_profile>" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE
    assert "{jd_structured_json}" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE
    assert "{resume_json}" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE
    assert "{linkedin_json}" in DEFAULT_LINKEDIN_VERIFICATION_USER_PROMPT_TEMPLATE


def test_linkedin_schema_requires_identity_confirmed():
    """Test that LinkedIn verification schema requires identity_confirmed."""
    assert LINKEDIN_VERIFICATION_SCHEMA is not None
    assert "required" in LINKEDIN_VERIFICATION_SCHEMA
    assert "identity_confirmed" in LINKEDIN_VERIFICATION_SCHEMA["required"]
    assert "overall_status" in LINKEDIN_VERIFICATION_SCHEMA["required"]
    assert "summary" in LINKEDIN_VERIFICATION_SCHEMA["required"]
    assert "findings" in LINKEDIN_VERIFICATION_SCHEMA["required"]


def test_linkedin_schema_finding_fields():
    """Test that LinkedIn verification schema requires all finding fields."""
    findings_schema = LINKEDIN_VERIFICATION_SCHEMA["properties"]["findings"]
    assert "items" in findings_schema
    finding_required = findings_schema["items"]["required"]
    assert "claim" in finding_required
    assert "status" in finding_required
    assert "jd_relevance" in finding_required
    assert "recency" in finding_required
    assert "resume_evidence" in finding_required
    assert "resume_chunk_id" in finding_required
    assert "resume_section" in finding_required
    assert "linkedin_evidence" in finding_required
    assert "justification" in finding_required


def test_linkedin_fallback_contains_identity_confirmed():
    """Test that LinkedIn verification fallback contains identity_confirmed."""
    assert LINKEDIN_VERIFICATION_FALLBACK is not None
    assert "identity_confirmed" in LINKEDIN_VERIFICATION_FALLBACK
    assert "overall_status" in LINKEDIN_VERIFICATION_FALLBACK
    assert "summary" in LINKEDIN_VERIFICATION_FALLBACK
    assert "findings" in LINKEDIN_VERIFICATION_FALLBACK
    assert LINKEDIN_VERIFICATION_FALLBACK["identity_confirmed"] is False
    assert LINKEDIN_VERIFICATION_FALLBACK["overall_status"] == "UNVERIFIABLE"


def test_normalize_linkedin_url():
    """Test LinkedIn URL normalization."""
    test_cases = [
        ("linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("https://linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("http://linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("https://www.linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("linkedin.com/in/johndoe/", "linkedin.com/in/johndoe"),
        ("johndoe", "linkedin.com/in/johndoe"),
        (None, None),
    ]

    for input_url, expected in test_cases:
        result = normalize_linkedin_url(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"


def test_normalize_linkedin_profile_url():
    """Test LinkedIn profile URL normalization for Captapi."""
    test_cases = [
        ("linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        ("https://linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        ("https://www.linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        ("linkedin.com/in/johndoe/", "https://linkedin.com/in/johndoe"),
        (None, None),
    ]

    for input_url, expected in test_cases:
        result = normalize_linkedin_profile_url(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"


def test_normalize_captapi_response():
    """Test Captapi response normalization."""
    raw_profile = {
        "fullName": "John Doe",
        "headline": "Software Engineer",
        "location": "San Francisco",
        "experience": [{"company": "Tech Corp"}],
        "education": [{"school": "University"}],
        "skills": ["Python", "React"],
        "profileUrl": "linkedin.com/in/johndoe",
    }

    normalized = normalize_captapi_response(raw_profile)

    assert normalized is not None
    assert normalized["name"] == "John Doe"
    assert normalized["headline"] == "Software Engineer"
    assert normalized["location"] == "San Francisco"
    assert normalized["experience"] == [{"company": "Tech Corp"}]
    assert normalized["education"] == [{"school": "University"}]
    assert normalized["skills"] == ["Python", "React"]
    assert normalized["profile_url"] == "linkedin.com/in/johndoe"


def test_normalize_captapi_response_none():
    """Test Captapi response normalization with None."""
    assert normalize_captapi_response(None) is None


def test_resume_skill_schema_has_contact_info():
    """Test that RESUME_SKILL_SCHEMA includes contact_info field."""
    assert "contact_info" in RESUME_SKILL_SCHEMA["properties"]
    contact_props = RESUME_SKILL_SCHEMA["properties"]["contact_info"]["properties"]
    assert "email" in contact_props
    assert "phone" in contact_props
    assert "linkedin" in contact_props
    assert "github" in contact_props


def test_resume_skill_fallback_has_contact_info():
    """Test that RESUME_SKILL_FALLBACK includes contact_info."""
    assert "contact_info" in RESUME_SKILL_FALLBACK
    assert RESUME_SKILL_FALLBACK["contact_info"]["email"] is None
    assert RESUME_SKILL_FALLBACK["contact_info"]["phone"] is None
    assert RESUME_SKILL_FALLBACK["contact_info"]["linkedin"] is None
    assert RESUME_SKILL_FALLBACK["contact_info"]["github"] is None


def test_safe_ai_json_accepts_system_prompt():
    """Test that safe_ai_json accepts system_prompt parameter."""
    # This is a signature test - we just verify the function accepts the parameter
    import inspect

    sig = inspect.signature(safe_ai_json)
    assert "system_prompt" in sig.parameters


def test_safe_gemini_json_accepts_system_prompt():
    """Test that safe_gemini_json accepts system_prompt parameter."""
    import inspect

    sig = inspect.signature(safe_gemini_json)
    assert "system_prompt" in sig.parameters


def test_safe_ollama_json_accepts_system_prompt():
    """Test that safe_ollama_json accepts system_prompt parameter."""
    import inspect

    sig = inspect.signature(safe_ollama_json)
    assert "system_prompt" in sig.parameters


@patch("backend.safe_gemini_json")
def test_safe_ai_json_forwards_system_prompt_to_gemini(mock_gemini):
    """Test that safe_ai_json forwards system_prompt to safe_gemini_json."""
    mock_gemini.return_value = {"result": "test"}

    safe_ai_json(
        "test prompt",
        {"type": "object"},
        {"fallback": True},
        provider="Gemini",
        system_prompt="test system prompt",
    )

    mock_gemini.assert_called_once()
    call_kwargs = mock_gemini.call_args[1]
    assert call_kwargs["system_prompt"] == "test system prompt"


@patch("backend.safe_ollama_json")
def test_safe_ai_json_forwards_system_prompt_to_ollama(mock_ollama):
    """Test that safe_ai_json forwards system_prompt to safe_ollama_json."""
    mock_ollama.return_value = {"result": "test"}

    safe_ai_json(
        "test prompt",
        {"type": "object"},
        {"fallback": True},
        provider="Ollama",
        system_prompt="test system prompt",
    )

    mock_ollama.assert_called_once()
    call_kwargs = mock_ollama.call_args[1]
    assert call_kwargs["system_prompt"] == "test system prompt"


@patch("backend.ollama")
def test_safe_ollama_json_uses_system_prompt_in_messages(mock_ollama):
    """Test that safe_ollama_json uses system_prompt in messages."""
    mock_ollama.chat.return_value = {"message": {"content": '{"result": "test"}'}}

    safe_ollama_json(
        "test prompt",
        {"type": "object"},
        {"fallback": True},
        system_prompt="custom system instruction",
    )

    mock_ollama.chat.assert_called_once()
    call_args = mock_ollama.chat.call_args
    messages = call_args[1]["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[0]["content"] == "custom system instruction"
    assert messages[1]["role"] == "user"
    assert messages[1]["content"] == "test prompt"


@patch("backend.ollama")
def test_safe_ollama_json_default_system_prompt(mock_ollama):
    """Test that safe_ollama_json uses default system prompt when none provided."""
    mock_ollama.chat.return_value = {"message": {"content": '{"result": "test"}'}}

    safe_ollama_json(
        "test prompt", {"type": "object"}, {"fallback": True}, system_prompt=None
    )

    mock_ollama.chat.assert_called_once()
    call_args = mock_ollama.chat.call_args
    messages = call_args[1]["messages"]
    assert messages[0]["role"] == "system"
    assert "JSON API" in messages[0]["content"]


def test_verify_linkedin_evidence_against_resume_callable():
    """Test that verify_linkedin_evidence_against_resume is callable."""
    assert callable(verify_linkedin_evidence_against_resume)


@patch("backend.safe_ai_json")
def test_verify_linkedin_evidence_against_resume_uses_system_prompt(mock_ai):
    """Test that verify_linkedin_evidence_against_resume passes system_prompt to safe_ai_json."""
    mock_ai.return_value = {
        "identity_confirmed": True,
        "overall_status": "CORROBORATED",
        "summary": "Test summary",
        "findings": [],
    }

    resume_profile = {"skills": {"contact_info": {"linkedin": "linkedin.com/in/test"}}}
    linkedin_profile = {"name": "Test User"}
    jd_structured = {"experience": "Test"}

    verify_linkedin_evidence_against_resume(
        resume_profile, linkedin_profile, jd_structured
    )

    mock_ai.assert_called_once()
    call_kwargs = mock_ai.call_args[1]
    assert call_kwargs["system_prompt"] == DEFAULT_LINKEDIN_VERIFICATION_SYSTEM_PROMPT


@patch("backend.safe_ai_json")
def test_verify_linkedin_evidence_against_resume_uses_schema(mock_ai):
    """Test that verify_linkedin_evidence_against_resume uses correct schema."""
    mock_ai.return_value = {
        "identity_confirmed": True,
        "overall_status": "CORROBORATED",
        "summary": "Test summary",
        "findings": [],
    }

    resume_profile = {"skills": {"contact_info": {}}}
    linkedin_profile = {"name": "Test User"}
    jd_structured = {"experience": "Test"}

    verify_linkedin_evidence_against_resume(
        resume_profile, linkedin_profile, jd_structured
    )

    mock_ai.assert_called_once()
    call_args = mock_ai.call_args
    assert call_args[0][1] == LINKEDIN_VERIFICATION_SCHEMA


@patch("backend.safe_ai_json")
def test_verify_linkedin_evidence_against_resume_uses_fallback(mock_ai):
    """Test that verify_linkedin_evidence_against_resume uses correct fallback."""
    mock_ai.return_value = {
        "identity_confirmed": True,
        "overall_status": "CORROBORATED",
        "summary": "Test summary",
        "findings": [],
    }

    resume_profile = {"skills": {"contact_info": {}}}
    linkedin_profile = {"name": "Test User"}
    jd_structured = {"experience": "Test"}

    verify_linkedin_evidence_against_resume(
        resume_profile, linkedin_profile, jd_structured
    )

    mock_ai.assert_called_once()
    call_args = mock_ai.call_args
    assert call_args[0][2] == LINKEDIN_VERIFICATION_FALLBACK


def test_contact_info_structure_in_sapna_profile():
    """Test that contact_info is properly structured in resume skill profile."""
    # Test with realistic resume text matching Sapna's format
    text = """
    Sapna Rathore
    Intern at Trigyn Technologies
    Email: sapna@example.com
    Phone: 9876543210
    LinkedIn: linkedin.com/in/sapna-rathore
    GitHub: github.com/sapnarathore0810
    """

    contact_info = extract_contact_info(text)

    assert contact_info["email"] == "sapna@example.com"
    assert contact_info["phone"] == "+91 98765 43210"
    assert contact_info["linkedin"] == "https://linkedin.com/in/sapna-rathore"
    assert contact_info["github"] == "https://github.com/sapnarathore0810"


def test_phone_normalization_indian():
    """Test phone normalization for Indian numbers."""
    test_cases = [
        ("9876543210", "+91 98765 43210"),
        ("+91 9876543210", "+91 98765 43210"),
        ("91 9876543210", "+91 98765 43210"),
    ]

    for input_phone, expected in test_cases:
        result = normalize_phone_number(input_phone)
        assert (
            result == expected
        ), f"Failed for {input_phone}: got {result}, expected {expected}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
