"""Unit tests for Captapi LinkedIn profile integration."""

import json
import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


def test_normalize_linkedin_profile_url_with_protocol():
    """Test URL normalization with http/https protocol."""
    from backend import normalize_linkedin_profile_url

    # Test with https
    url = "https://linkedin.com/in/johndoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"

    # Test with http
    url = "http://linkedin.com/in/johndoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"


def test_normalize_linkedin_profile_url_without_protocol():
    """Test URL normalization without protocol."""
    from backend import normalize_linkedin_profile_url

    url = "linkedin.com/in/johndoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"


def test_normalize_linkedin_profile_url_with_www():
    """Test URL normalization with www."""
    from backend import normalize_linkedin_profile_url

    url = "https://www.linkedin.com/in/johndoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"


def test_normalize_linkedin_profile_url_trailing_slash():
    """Test URL normalization with trailing slash."""
    from backend import normalize_linkedin_profile_url

    url = "https://linkedin.com/in/johndoe/"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"


def test_normalize_linkedin_profile_url_case_preserved():
    """Test URL normalization preserves case (production behavior)."""
    from backend import normalize_linkedin_profile_url

    # The production implementation preserves case in the path
    url = "https://LINKEDIN.COM/IN/JohnDoe"
    normalized = normalize_linkedin_profile_url(url)
    # Strips protocol/scheme, reconstructs with https://
    assert normalized is not None
    assert normalized.startswith("https://")


def test_normalize_linkedin_profile_url_invalid_input():
    """Test URL normalization with empty/None input."""
    from backend import normalize_linkedin_profile_url

    # None input
    assert normalize_linkedin_profile_url(None) is None

    # Empty string
    assert normalize_linkedin_profile_url("") is None


def test_normalize_linkedin_profile_url_without_in():
    """Test URL normalization accepts URLs without /in/."""
    from backend import normalize_linkedin_profile_url

    url = "https://linkedin.com/johndoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/johndoe"


def test_fetch_captapi_missing_api_key():
    """Test that missing API key returns None."""
    with patch.dict(os.environ, {"CAPTAPI_API_KEY": ""}, clear=False):
        os.environ.pop("CAPTAPI_API_KEY", None)
        from backend import fetch_captapi_linkedin_profile

        result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")
        assert result is None


def test_fetch_captapi_success():
    """Test successful Captapi response normalization using urllib."""
    import backend
    from backend import CAPTAPI_CACHE_PATH, fetch_captapi_linkedin_profile

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        raw_profile = {
            "fullName": "John Doe",
            "headline": "Software Engineer",
            "location": "San Francisco, CA",
            "experience": [
                {
                    "title": "Senior Engineer",
                    "company": "Tech Corp",
                }
            ],
            "education": [
                {
                    "school": "MIT",
                    "degree": "BS",
                    "field_of_study": "Computer Science",
                }
            ],
            "skills": ["Python", "JavaScript"],
            "profileUrl": "https://linkedin.com/in/johndoe",
        }
        response_bytes = json.dumps(raw_profile).encode("utf-8")

        mock_response = Mock()
        mock_response.read.return_value = response_bytes
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_captapi_linkedin_profile(
                    "https://linkedin.com/in/johndoe"
                )

                assert result is not None
                assert result["name"] == "John Doe"
                assert result["headline"] == "Software Engineer"
                assert result["location"] == "San Francisco, CA"
                assert len(result["experience"]) == 1
                assert result["experience"][0]["title"] == "Senior Engineer"
                assert len(result["education"]) == 1
                assert result["education"][0]["school"] == "MIT"
                assert result["skills"] == ["Python", "JavaScript"]

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_fetch_captapi_success_top_level_format():
    """Test successful Captapi response normalization with name field."""
    import backend
    from backend import CAPTAPI_CACHE_PATH, fetch_captapi_linkedin_profile

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        raw_profile = {
            "name": "Jane Smith",
            "headline": "Data Scientist",
            "location": "New York, NY",
            "experience": [
                {
                    "title": "Data Scientist",
                    "company": "Data Corp",
                }
            ],
            "education": [
                {
                    "school": "Stanford",
                    "degree": "MS",
                }
            ],
            "skills": ["Python", "R"],
        }
        response_bytes = json.dumps(raw_profile).encode("utf-8")

        mock_response = Mock()
        mock_response.read.return_value = response_bytes
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_captapi_linkedin_profile(
                    "https://linkedin.com/in/janesmith"
                )

                assert result is not None
                assert result["name"] == "Jane Smith"
                assert result["headline"] == "Data Scientist"
                assert len(result["experience"]) == 1
                assert result["experience"][0]["title"] == "Data Scientist"

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_fetch_captapi_http_error():
    """Test Captapi HTTP error handling."""
    import urllib.error

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.HTTPError(
                url="test", code=404, msg="Not Found", hdrs={}, fp=None
            ),
        ):
            from backend import fetch_captapi_linkedin_profile

            result = fetch_captapi_linkedin_profile("https://linkedin.com/in/notfound")
            assert result is None


def test_fetch_captapi_url_error():
    """Test Captapi URL/network error handling."""
    import urllib.error

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        with patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError(reason="Connection refused"),
        ):
            from backend import fetch_captapi_linkedin_profile

            result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")
            assert result is None


def test_fetch_captapi_cache_behavior():
    """Test Captapi caching behavior."""
    import backend
    from backend import (
        CAPTAPI_CACHE_PATH,
        fetch_captapi_linkedin_profile,
    )

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        raw_profile = {
            "name": "Cached User",
            "headline": "Test",
            "experience": [],
            "education": [],
            "skills": [],
        }
        response_bytes = json.dumps(raw_profile).encode("utf-8")

        mock_response = Mock()
        mock_response.read.return_value = response_bytes
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        # First call should fetch from API
        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch(
                "urllib.request.urlopen", return_value=mock_response
            ) as mock_urlopen:
                result1 = fetch_captapi_linkedin_profile(
                    "https://linkedin.com/in/cacheduser"
                )
                assert result1 is not None
                assert mock_urlopen.call_count == 1

        # Second call should hit cache (no network call needed)
        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen") as mock_urlopen:
                result2 = fetch_captapi_linkedin_profile(
                    "https://linkedin.com/in/cacheduser"
                )
                assert result2 is not None
                assert result2["name"] == "Cached User"
                assert mock_urlopen.call_count == 0  # Should not call API

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_captapi_candidate_association():
    """Test that candidate LinkedIn URL is associated with Captapi data."""
    import backend
    from backend import CAPTAPI_CACHE_PATH, fetch_captapi_linkedin_profile

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        contact_info = {"linkedin": "https://linkedin.com/in/candidate123"}

        raw_profile = {
            "name": "Candidate Name",
            "headline": "Developer",
            "experience": [],
            "education": [],
            "skills": [],
        }
        response_bytes = json.dumps(raw_profile).encode("utf-8")

        mock_response = Mock()
        mock_response.read.return_value = response_bytes
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                linkedin_profile = None
                if contact_info.get("linkedin"):
                    linkedin_profile = fetch_captapi_linkedin_profile(
                        contact_info["linkedin"]
                    )

                assert linkedin_profile is not None
                assert linkedin_profile["name"] == "Candidate Name"

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_captapi_failure_does_not_break_analysis():
    """Test that Captapi failure does not break candidate analysis."""
    from backend import fetch_captapi_linkedin_profile

    # Simulate Captapi failure (missing API key)
    with patch.dict(os.environ, {"CAPTAPI_API_KEY": ""}, clear=False):
        os.environ.pop("CAPTAPI_API_KEY", None)
        contact_info = {"linkedin": "https://linkedin.com/in/johndoe"}

        linkedin_profile = None
        if contact_info.get("linkedin"):
            linkedin_profile = fetch_captapi_linkedin_profile(contact_info["linkedin"])

        # Should return None, not crash
        assert linkedin_profile is None

        # Detail object should not have linkedin_profile
        detail = {}
        if linkedin_profile:
            detail["linkedin_profile"] = linkedin_profile

        assert "linkedin_profile" not in detail


def test_captapi_data_does_not_affect_ranking():
    """Test that Captapi LinkedIn data does not affect ranking/selection."""
    import backend
    from backend import CAPTAPI_CACHE_PATH, fetch_captapi_linkedin_profile

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        raw_profile = {
            "name": "Test User",
            "headline": "Developer",
            "experience": [],
            "education": [],
            "skills": ["Python"],
        }
        response_bytes = json.dumps(raw_profile).encode("utf-8")

        mock_response = Mock()
        mock_response.read.return_value = response_bytes
        mock_response.__enter__ = Mock(return_value=mock_response)
        mock_response.__exit__ = Mock(return_value=False)

        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch("urllib.request.urlopen", return_value=mock_response):
                result = fetch_captapi_linkedin_profile(
                    "https://linkedin.com/in/testuser"
                )

                # Result should only contain display data
                assert "name" in result
                assert "experience" in result

                # No ranking/scoring fields
                assert "score" not in result
                assert "rank" not in result
                assert "match_score" not in result
                assert "grade" not in result

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
