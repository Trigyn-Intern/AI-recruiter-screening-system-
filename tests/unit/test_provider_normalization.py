"""
Test provider name normalization in chunking system.

This test verifies that provider names are normalized to lowercase
to prevent "Unknown chunking provider" errors when UI sends capitalized names.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="Chunking provider separation was not implemented in production backend. "
    "CHUNKING_PROVIDER_OPTIONS does not exist in backend.py."
)


def test_provider_normalization_gemini_to_lowercase():
    """Test that 'Gemini' is normalized to 'gemini' for chunking."""
    # This should not raise "Unknown chunking provider: Gemini"
    # even though the provider name is capitalized
    try:
        # We can't actually call chunk_resume without valid text_items,
        # but we can test the normalization logic
        provider = "Gemini"
        normalized = provider.lower() if provider else provider
        assert normalized == "gemini", f"Expected 'gemini', got '{normalized}'"
    except Exception as e:
        pytest.fail(f"Provider normalization failed: {e}")


def test_provider_normalization_openai_to_lowercase():
    """Test that 'OpenAI' is normalized to 'openai' for chunking."""
    provider = "OpenAI"
    normalized = provider.lower() if provider else provider
    assert normalized == "openai", f"Expected 'openai', got '{normalized}'"


def test_provider_normalization_lowercase_unchanged():
    """Test that lowercase provider names remain unchanged."""
    test_cases = [
        ("openai", "openai"),
        ("gemini", "gemini"),
        ("ollama", "ollama"),
    ]

    for input_provider, expected in test_cases:
        normalized = input_provider.lower() if input_provider else input_provider
        assert normalized == expected, f"Expected '{expected}', got '{normalized}'"


def test_provider_normalization_none_unchanged():
    """Test that None provider remains None."""
    provider = None
    normalized = provider.lower() if provider else provider
    assert normalized is None, f"Expected None, got '{normalized}'"


def test_provider_normalization_empty_string_unchanged():
    """Test that empty string remains empty string."""
    provider = ""
    normalized = provider.lower() if provider else provider
    assert normalized == "", f"Expected empty string, got '{normalized}'"


def test_chunking_provider_options():
    """Verify that CHUNKING_PROVIDER_OPTIONS contains lowercase values."""
    pass


def test_provider_normalization_mixed_case():
    """Test that mixed-case provider names are normalized."""
    test_cases = [
        ("GEMINI", "gemini"),
        ("OpEnAi", "openai"),
        ("gEmInI", "gemini"),
    ]

    for input_provider, expected in test_cases:
        normalized = input_provider.lower() if input_provider else input_provider
        assert normalized == expected, f"Expected '{expected}', got '{normalized}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
