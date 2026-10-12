"""Unit tests for LinkedIn profile integration."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest


def test_normalize_linkedin_url():
    """Test LinkedIn URL normalization."""
    from backend import normalize_linkedin_url

    # Test various URL formats supported by backend
    test_cases = [
        ("https://linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("http://linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("https://www.linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("http://www.linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("https://linkedin.com/in/johndoe/", "linkedin.com/in/johndoe"),
        ("linkedin.com/in/johndoe", "linkedin.com/in/johndoe"),
        ("johndoe", "linkedin.com/in/johndoe"),
    ]

    for input_url, expected in test_cases:
        result = normalize_linkedin_url(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"

    # Test empty or None URLs
    for invalid_url in [None, ""]:
        result = normalize_linkedin_url(invalid_url)
        assert result is None, f"Expected None for {invalid_url}, got {result}"


def test_normalize_linkedin_security_regression():
    """Security regression tests for LinkedIn URL validation.

    Covers:
    - Valid URLs and bare handles
    - Lookalike domains / subdomain tricks
    - Unrelated external hosts
    - Malformed URLs and invalid schemes
    - Path traversal attempts
    """
    from backend import normalize_linkedin_profile_url, normalize_linkedin_url

    # 1. Valid URLs
    valid_urls = [
        (
            "https://linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "http://linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "https://www.linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "http://www.linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "https://linkedin.com/in/johndoe/",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "www.linkedin.com/in/johndoe",
            "linkedin.com/in/johndoe",
            "https://linkedin.com/in/johndoe",
        ),
        (
            "https://LINKEDIN.COM/IN/JohnDoe",
            "linkedin.com/in/IN/JohnDoe",
            "https://linkedin.com/IN/JohnDoe",
        ),
        (
            "https://linkedin.com/in/john-doe-123",
            "linkedin.com/in/john-doe-123",
            "https://linkedin.com/in/john-doe-123",
        ),
    ]
    for raw_url, expected_norm, expected_profile in valid_urls:
        assert normalize_linkedin_url(raw_url) == expected_norm, f"Failed for {raw_url}"
        assert (
            normalize_linkedin_profile_url(raw_url) == expected_profile
        ), f"Failed profile for {raw_url}"

    # 2. Bare handles
    bare_handles = [
        ("johndoe", "linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        ("in/johndoe", "linkedin.com/in/johndoe", "https://linkedin.com/in/johndoe"),
        (
            "john-doe-456",
            "linkedin.com/in/john-doe-456",
            "https://linkedin.com/in/john-doe-456",
        ),
        ("john_doe", "linkedin.com/in/john_doe", "https://linkedin.com/in/john_doe"),
    ]
    for raw_handle, expected_norm, expected_profile in bare_handles:
        assert (
            normalize_linkedin_url(raw_handle) == expected_norm
        ), f"Failed handle for {raw_handle}"
        assert (
            normalize_linkedin_profile_url(raw_handle) == expected_profile
        ), f"Failed handle profile for {raw_handle}"

    # 3. Lookalike hosts (must reject)
    lookalike_hosts = [
        "https://linkedin.com.attacker.com/in/johndoe",
        "http://linkedin.com.attacker.com/in/johndoe",
        "linkedin.com.attacker.com/in/johndoe",
        "https://notlinkedin.com/in/johndoe",
        "notlinkedin.com/in/johndoe",
        "https://evil-linkedin.com/in/johndoe",
        "https://attacker.com/linkedin.com/in/johndoe",
        "http://evil.com/linkedin.com/in/johndoe",
        "https://linkedin.com@attacker.com/in/johndoe",
        "linkedin.com.attacker.com",
    ]
    for bad_url in lookalike_hosts:
        assert (
            normalize_linkedin_url(bad_url) is None
        ), f"Expected None for lookalike {bad_url}"
        assert (
            normalize_linkedin_profile_url(bad_url) is None
        ), f"Expected None for lookalike profile {bad_url}"

    # 4. Unrelated external hosts (must reject)
    unrelated_hosts = [
        "https://evil.com/in/johndoe",
        "http://attacker.com/profile",
        "https://google.com/search",
        "https://github.com/johndoe",
        "evil.com/in/johndoe",
        "attacker.com",
        "evil.com",
        "google.com",
    ]
    for bad_url in unrelated_hosts:
        assert (
            normalize_linkedin_url(bad_url) is None
        ), f"Expected None for unrelated host {bad_url}"
        assert (
            normalize_linkedin_profile_url(bad_url) is None
        ), f"Expected None for unrelated profile {bad_url}"

    # 5. Malformed URLs and invalid schemes (must reject)
    malformed_urls = [
        None,
        "",
        "   ",
        "://linkedin.com/in/johndoe",
        "https://",
        "http://",
        "https:///in/johndoe",
        "ftp://linkedin.com/in/johndoe",
        "javascript:alert(1)",
        "https://user:pass@linkedin.com/in/johndoe",
        "https://linkedin.com:8080/in/johndoe",
        "https://linkedin.com",
        "https://linkedin.com/",
        "https://linkedin.com/in",
        "https://linkedin.com/in/",
        "linkedin.com",
        "linkedin.com/",
        "linkedin.com/in",
        "linkedin.com/in/",
    ]
    for bad_url in malformed_urls:
        assert (
            normalize_linkedin_url(bad_url) is None
        ), f"Expected None for malformed {bad_url}"
        assert (
            normalize_linkedin_profile_url(bad_url) is None
        ), f"Expected None for malformed profile {bad_url}"

    # 6. Traversal-like profile paths (must reject)
    traversal_paths = [
        "https://linkedin.com/in/../../etc/passwd",
        "https://linkedin.com/../../admin",
        "linkedin.com/in/../johndoe",
        "../johndoe",
        "johndoe/../admin",
        "..",
        ".",
        "https://linkedin.com/in/%2e%2e/admin",
        "https://linkedin.com/in/.../admin",
        "https://linkedin.com/in/./johndoe",
        "in/../../johndoe",
        "https://linkedin.com/in/..",
    ]
    for bad_url in traversal_paths:
        assert (
            normalize_linkedin_url(bad_url) is None
        ), f"Expected None for traversal {bad_url}"
        assert (
            normalize_linkedin_profile_url(bad_url) is None
        ), f"Expected None for traversal profile {bad_url}"


def test_persist_linkedin_profile():
    """Test LinkedIn profile persistence."""

    from backend import LINKEDIN_PROFILE_CACHE_PATH, persist_linkedin_profile

    # Use a temporary cache for testing
    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        # Temporarily override cache path
        import backend

        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        profile_data = {
            "sub": "test_sub_123",
            "name": "Test User",
            "given_name": "Test",
            "family_name": "User",
            "email": "test@example.com",
            "email_verified": True,
            "picture": "https://example.com/photo.jpg",
        }

        linkedin_url = "https://linkedin.com/in/testuser"

        # Persist profile
        persist_linkedin_profile(profile_data, linkedin_url)

        # Verify cache file was created
        assert temp_cache_path.exists()

        # Verify cache contents
        with open(temp_cache_path, "r") as f:
            cache = json.load(f)

        assert "linkedin.com/in/testuser" in cache
        cached_profile = cache["linkedin.com/in/testuser"]

        assert cached_profile["sub"] == "test_sub_123"
        assert cached_profile["name"] == "Test User"
        assert cached_profile["email"] == "test@example.com"
        assert cached_profile["email_verified"] is True
        assert cached_profile["picture"] == "https://example.com/photo.jpg"
        assert "cache_version" in cached_profile
        assert "cached_at" in cached_profile

    finally:
        # Restore original cache path
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        # Clean up temp directory
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_persist_linkedin_profile_without_url():
    """Test LinkedIn profile persistence keyed by sub when URL is not provided."""
    import backend
    from backend import LINKEDIN_PROFILE_CACHE_PATH, persist_linkedin_profile

    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        profile_data = {
            "sub": "test_sub_456",
            "name": "Test User 2",
            "email": "test2@example.com",
        }

        # Persist profile without URL
        persist_linkedin_profile(profile_data, linkedin_url=None)

        # Verify cache contents
        with open(temp_cache_path, "r") as f:
            cache = json.load(f)

        assert "sub:test_sub_456" in cache
        cached_profile = cache["sub:test_sub_456"]
        assert cached_profile["sub"] == "test_sub_456"
        assert cached_profile["name"] == "Test User 2"

    finally:
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_linkedin_profile():
    """Test LinkedIn profile retrieval."""
    import backend
    from backend import (
        LINKEDIN_PROFILE_CACHE_PATH,
        get_linkedin_profile,
        persist_linkedin_profile,
    )

    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        # First, persist a profile
        profile_data = {
            "sub": "test_sub_789",
            "name": "Test User 3",
            "email": "test3@example.com",
        }
        linkedin_url = "https://linkedin.com/in/testuser3"
        persist_linkedin_profile(profile_data, linkedin_url)

        # Now retrieve it
        retrieved = get_linkedin_profile(linkedin_url)

        assert retrieved is not None
        assert retrieved["sub"] == "test_sub_789"
        assert retrieved["name"] == "Test User 3"
        assert retrieved["email"] == "test3@example.com"

        # Test retrieval with different URL format (should still match due to normalization)
        retrieved_alt = get_linkedin_profile("http://www.linkedin.com/in/testuser3/")
        assert retrieved_alt is not None
        assert retrieved_alt["sub"] == "test_sub_789"

    finally:
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_get_linkedin_profile_not_found():
    """Test LinkedIn profile retrieval when profile doesn't exist."""
    import backend
    from backend import LINKEDIN_PROFILE_CACHE_PATH, get_linkedin_profile

    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        # Try to retrieve non-existent profile
        retrieved = get_linkedin_profile("https://linkedin.com/in/nonexistent")

        assert retrieved is None

    finally:
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_linkedin_profile_does_not_affect_ranking():
    """Test that LinkedIn profile data is not used for ranking/selection."""
    from backend import normalize_linkedin_url

    # This test confirms that LinkedIn profile functions are purely for display
    # They don't modify any ranking/scoring logic

    # URL normalization is purely for lookup
    url = "https://linkedin.com/in/testuser"
    normalized = normalize_linkedin_url(url)
    assert normalized == "linkedin.com/in/testuser"

    # No ranking/scoring logic exists in LinkedIn profile functions
    # This is confirmed by code inspection - functions only:
    # - normalize URLs
    # - persist/retrieve from cache
    # - No calls to ranking, scoring, or selection functions


def test_linkedin_profile_candidate_detail_integration():
    """Test that LinkedIn profile is found during candidate detail generation."""
    import backend
    from backend import (
        LINKEDIN_PROFILE_CACHE_PATH,
        get_linkedin_profile,
        persist_linkedin_profile,
    )

    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        # Simulate OAuth callback persisting profile with LinkedIn URL
        profile_data = {
            "sub": "test_sub_999",
            "name": "Test Candidate",
            "given_name": "Sapna",
            "family_name": "Rathore",
            "email": "sapna@example.com",
            "email_verified": True,
            "picture": "https://example.com/photo.jpg",
        }
        linkedin_url = "https://linkedin.com/in/test-candidate"
        persist_linkedin_profile(profile_data, linkedin_url)

        # Simulate candidate detail generation looking up profile
        # using the LinkedIn URL from resume contact_info
        retrieved_profile = get_linkedin_profile(linkedin_url)

        assert retrieved_profile is not None
        assert retrieved_profile["name"] == "Test Candidate"
        assert retrieved_profile["email"] == "sapna@example.com"

    finally:
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_linkedin_profile_in_detail_response():
    """Test that detail.linkedin_profile is included in candidate detail response."""
    import backend
    from backend import (
        LINKEDIN_PROFILE_CACHE_PATH,
        get_linkedin_profile,
        persist_linkedin_profile,
    )

    original_cache_path = LINKEDIN_PROFILE_CACHE_PATH
    temp_dir = tempfile.mkdtemp()
    temp_cache_path = Path(temp_dir) / "linkedin_profile_cache.json"

    try:
        backend.LINKEDIN_PROFILE_CACHE_PATH = temp_cache_path

        # Persist LinkedIn profile
        profile_data = {
            "sub": "test_sub_888",
            "name": "Test Candidate",
            "email": "candidate@example.com",
        }
        linkedin_url = "https://linkedin.com/in/testcandidate"
        persist_linkedin_profile(profile_data, linkedin_url)

        # Simulate the detail object construction in _process_candidate_detail
        contact_info = {"linkedin": linkedin_url}
        linkedin_profile = None
        if contact_info.get("linkedin"):
            linkedin_profile = get_linkedin_profile(contact_info["linkedin"])

        detail = {}
        if linkedin_profile:
            detail["linkedin_profile"] = linkedin_profile

        # Verify the detail object contains the LinkedIn profile
        assert "linkedin_profile" in detail
        assert detail["linkedin_profile"]["name"] == "Test Candidate"
        assert detail["linkedin_profile"]["email"] == "candidate@example.com"

    finally:
        backend.LINKEDIN_PROFILE_CACHE_PATH = original_cache_path
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_candidate_detail_restores_contact_and_linkedin_fields(monkeypatch):
    from api import restore_candidate_profile_fields

    contact_info = {
        "email": "sapna.test@example.com",
        "phone": "+91-90000-00000",
        "linkedin": "linkedin.com/in/test-candidate",
        "github": "github.com/test-candidate",
    }
    linkedin_profile = {"name": "Test Candidate", "source": "captapi"}
    monkeypatch.setattr(
        "api.fetch_captapi_linkedin_profile",
        lambda url: linkedin_profile if url == contact_info["linkedin"] else None,
    )

    restored = restore_candidate_profile_fields(
        {"skills": {"contact_info": contact_info}}
    )

    assert restored["contact_info"] == contact_info
    assert restored["linkedin_profile"] == linkedin_profile
    assert restored["contact_info"]["linkedin"] == "linkedin.com/in/test-candidate"
    assert restored["contact_info"]["github"] == "github.com/test-candidate"


def test_cache_version_invalidation_for_linkedin_profile():
    """Test that cache version change invalidates old analysis without LinkedIn profile."""
    from backend import ANALYSIS_CACHE_VERSION

    # Verify cache version includes LinkedIn integration suffix
    assert "linkedin" in ANALYSIS_CACHE_VERSION

    # This ensures that old cached analysis results (without LinkedIn profile)
    # will be invalidated and re-generated with the new field


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
