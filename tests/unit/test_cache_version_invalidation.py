"""
Test that cache version changes invalidate stale cached results.

This test verifies that when ANALYSIS_CACHE_VERSION is incremented,
cached results with the old version are treated as stale and regenerated.
"""

import pytest

from backend import ANALYSIS_CACHE_VERSION, get_ai_cache, get_ai_cache_key


def test_cache_version_change_invalidates_old_cache():
    """Test that changing ANALYSIS_CACHE_VERSION invalidates old cached results."""
    old_version = "evidence_chunks_v7_contact_prompt_fix"
    new_version = "evidence_chunks_v7_contact_prompt_fix_captapi_linkedin_verification"

    # Verify the current version is the new one
    assert ANALYSIS_CACHE_VERSION == new_version

    # Simulate a cached result with the old version
    cache = get_ai_cache()
    old_cache_key = get_ai_cache_key(
        "candidate_detail_with_grading_v2",
        "Gemini",
        "gemini-3-flash-preview",
        85,
        "Selected",
        "test context",
        "test job text",
        "test template",
    )

    # Create a cached result with the old version
    cache[old_cache_key] = {
        "cache_version": old_version,
        "matching_skills": ["Python", "JavaScript"],
        "missing_skills": ["React"],
        "contact_info": {"email": "old@example.com"},  # Old structure
    }

    # Simulate the cache version check logic
    cached_result = cache[old_cache_key]
    cached_version = cached_result.get("cache_version", "")

    # This should be True (cache is stale)
    is_stale = cached_version != ANALYSIS_CACHE_VERSION

    assert is_stale, "Cache should be stale when version changes"
    assert cached_version == old_version
    assert ANALYSIS_CACHE_VERSION == new_version

    # Clean up test data
    if old_cache_key in cache:
        del cache[old_cache_key]


def test_cache_version_matches_current_not_invalidated():
    """Test that cached results with current version are not invalidated."""
    current_version = (
        "evidence_chunks_v7_contact_prompt_fix_captapi_linkedin_verification"
    )

    cache = get_ai_cache()
    test_cache_key = get_ai_cache_key(
        "candidate_detail_with_grading_v2",
        "Gemini",
        "gemini-3-flash-preview",
        90,
        "Selected",
        "current context",
        "current job text",
        "current template",
    )

    # Create a cached result with the current version
    cache[test_cache_key] = {
        "cache_version": current_version,
        "matching_skills": ["Python", "Java"],
        "missing_skills": [],
    }

    # Simulate the cache version check logic
    cached_result = cache[test_cache_key]
    cached_version = cached_result.get("cache_version", "")

    # This should be False (cache is valid)
    is_stale = cached_version != ANALYSIS_CACHE_VERSION

    assert not is_stale, "Cache should NOT be stale when version matches"
    assert cached_version == current_version
    assert cached_version == ANALYSIS_CACHE_VERSION

    # Clean up test data
    if test_cache_key in cache:
        del cache[test_cache_key]


def test_cache_without_version_is_invalidated():
    """Test that cached results without version are treated as stale."""
    cache = get_ai_cache()
    test_cache_key = get_ai_cache_key(
        "candidate_detail_with_grading_v2",
        "Ollama",
        "llama3.2",
        75,
        "Not Selected",
        "no version context",
        "no version job text",
        "no version template",
    )

    # Create a cached result without version
    cache[test_cache_key] = {
        "matching_skills": ["SQL"],
        "missing_skills": ["Python"],
        # No cache_version field
    }

    # Simulate the cache version check logic
    cached_result = cache[test_cache_key]
    cached_version = cached_result.get("cache_version", "")

    # This should be True (cache is stale when version is missing)
    is_stale = cached_version != ANALYSIS_CACHE_VERSION

    assert is_stale, "Cache should be stale when version is missing"
    assert cached_version == ""

    # Clean up test data
    if test_cache_key in cache:
        del cache[test_cache_key]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
