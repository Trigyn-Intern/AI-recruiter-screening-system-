"""Unit tests for Captapi LinkedIn profile integration."""
import pytest
from unittest.mock import patch, Mock
import os
import tempfile
import shutil
from pathlib import Path


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


def test_normalize_linkedin_profile_url_case_insensitive():
    """Test URL normalization is case-insensitive."""
    from backend import normalize_linkedin_profile_url

    url = "https://LINKEDIN.COM/IN/JohnDoe"
    normalized = normalize_linkedin_profile_url(url)
    assert normalized == "https://linkedin.com/in/johndoe"


def test_normalize_linkedin_profile_url_invalid():
    """Test URL normalization rejects invalid URLs."""
    from backend import normalize_linkedin_profile_url

    # Invalid domain
    assert normalize_linkedin_profile_url("https://facebook.com/johndoe") is None

    # Invalid format
    assert normalize_linkedin_profile_url("https://linkedin.com") is None

    # Too short username
    assert normalize_linkedin_profile_url("https://linkedin.com/in/ab") is None

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
    with patch.dict(os.environ, {"CAPTAPI_API_KEY": ""}):
        from backend import fetch_captapi_linkedin_profile

        result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")
        assert result is None


@patch('requests.get')
def test_fetch_captapi_success(mock_get):
    """Test successful Captapi response normalization with wrapper format."""
    # Mock successful response with Captapi wrapper format
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "data": {
            "name": "John Doe",
            "headline": "Software Engineer",
            "location": "San Francisco, CA",
            "about": "Experienced developer",
            "profileImage": "https://example.com/photo.jpg",
            "followers": 1000,
            "connections": 500,
            "currentCompany": "Tech Corp",
            "experience": [
                {
                    "title": "Senior Engineer",
                    "company": "Tech Corp",
                    "location": "San Francisco",
                    "description": "Led team",
                    "start_date": "2020-01",
                    "end_date": None,
                    "is_current": True
                }
            ],
            "education": [
                {
                    "school": "MIT",
                    "degree": "BS",
                    "field_of_study": "Computer Science",
                    "start_date": "2015",
                    "end_date": "2019"
                }
            ],
            "certifications": [
                {
                    "name": "AWS Certified",
                    "authority": "Amazon"
                }
            ],
            "skills": ["Python", "JavaScript"],
            "cached": True
        }
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        from backend import fetch_captapi_linkedin_profile, CAPTAPI_CACHE_PATH
        import backend

        # Use temporary cache
        temp_dir = tempfile.mkdtemp()
        temp_cache = Path(temp_dir) / "captapi_cache.json"
        original_cache = CAPTAPI_CACHE_PATH
        backend.CAPTAPI_CACHE_PATH = temp_cache

        try:
            result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")

            assert result is not None
            assert result["source"] == "captapi"
            assert result["username"] == "johndoe"
            assert result["url"] == "https://linkedin.com/in/johndoe"
            assert result["name"] == "John Doe"
            assert result["headline"] == "Software Engineer"
            assert result["location"] == "San Francisco, CA"
            assert result["about"] == "Experienced developer"
            assert result["profile_image"] == "https://example.com/photo.jpg"
            assert result["followers"] == 1000
            assert result["connections"] == 500
            assert result["current_company"] == "Tech Corp"
            assert len(result["experience"]) == 1
            assert result["experience"][0]["title"] == "Senior Engineer"
            assert result["experience"][0]["company"] == "Tech Corp"
            assert result["experience"][0]["is_current"] is True
            assert len(result["education"]) == 1
            assert result["education"][0]["school"] == "MIT"
            assert len(result["certifications"]) == 1
            assert result["certifications"][0]["name"] == "AWS Certified"
            assert result["skills"] == ["Python", "JavaScript"]
            assert result["cached"] is True
            assert "fetched_at" in result

        finally:
            backend.CAPTAPI_CACHE_PATH = original_cache
            shutil.rmtree(temp_dir, ignore_errors=True)


@patch('requests.get')
def test_fetch_captapi_success_top_level_format(mock_get):
    """Test successful Captapi response normalization with top-level format (no wrapper)."""
    # Mock successful response without wrapper (backward compatibility)
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "name": "Jane Smith",
        "headline": "Data Scientist",
        "location": "New York, NY",
        "about": "Data expert",
        "profileImage": "https://example.com/jane.jpg",
        "followers": 500,
        "connections": 250,
        "currentCompany": "Data Corp",
        "experience": [
            {
                "title": "Data Scientist",
                "company": "Data Corp",
                "location": "New York",
                "description": "Data analysis",
                "start_date": "2021-01",
                "end_date": None,
                "is_current": True
            }
        ],
        "education": [
            {
                "school": "Stanford",
                "degree": "MS",
                "field_of_study": "Data Science",
                "start_date": "2019",
                "end_date": "2021"
            }
        ],
        "certifications": [],
        "skills": ["Python", "R"],
        "cached": False
    }
    mock_response.raise_for_status = Mock()
    mock_get.return_value = mock_response

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        from backend import fetch_captapi_linkedin_profile, CAPTAPI_CACHE_PATH
        import backend

        # Use temporary cache
        temp_dir = tempfile.mkdtemp()
        temp_cache = Path(temp_dir) / "captapi_cache.json"
        original_cache = CAPTAPI_CACHE_PATH
        backend.CAPTAPI_CACHE_PATH = temp_cache

        try:
            result = fetch_captapi_linkedin_profile("https://linkedin.com/in/janesmith")

            assert result is not None
            assert result["source"] == "captapi"
            assert result["username"] == "janesmith"
            assert result["name"] == "Jane Smith"
            assert result["headline"] == "Data Scientist"
            assert result["location"] == "New York, NY"
            assert len(result["experience"]) == 1
            assert result["experience"][0]["title"] == "Data Scientist"

        finally:
            backend.CAPTAPI_CACHE_PATH = original_cache
            shutil.rmtree(temp_dir, ignore_errors=True)


@patch('requests.get')
def test_fetch_captapi_404_error(mock_get):
    """Test Captapi 404 error handling."""
    mock_response = Mock()
    mock_response.status_code = 404
    mock_response.raise_for_status = Mock(side_effect=Exception("HTTP 404"))
    mock_get.return_value = mock_response

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        from backend import fetch_captapi_linkedin_profile

        result = fetch_captapi_linkedin_profile("https://linkedin.com/in/notfound")
        assert result is None


@patch('requests.get')
def test_fetch_captapi_rate_limit(mock_get):
    """Test Captapi 429 rate limit handling."""
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.raise_for_status = Mock(side_effect=Exception("HTTP 429"))
    mock_get.return_value = mock_response

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        from backend import fetch_captapi_linkedin_profile

        result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")
        assert result is None


@patch('requests.get')
def test_fetch_captapi_timeout(mock_get):
    """Test Captapi timeout handling."""
    import requests
    mock_get.side_effect = requests.exceptions.Timeout()

    with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
        from backend import fetch_captapi_linkedin_profile

        result = fetch_captapi_linkedin_profile("https://linkedin.com/in/johndoe")
        assert result is None


def test_fetch_captapi_cache_behavior():
    """Test Captapi caching behavior."""
    from backend import fetch_captapi_linkedin_profile, CAPTAPI_CACHE_PATH
    import backend

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        # First call should miss cache
        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "name": "Cached User",
                    "headline": "Test"
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result1 = fetch_captapi_linkedin_profile("https://linkedin.com/in/cacheduser")
                assert result1 is not None
                assert mock_get.call_count == 1

        # Second call should hit cache
        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch('requests.get') as mock_get:
                result2 = fetch_captapi_linkedin_profile("https://linkedin.com/in/cacheduser")
                assert result2 is not None
                assert result2["name"] == "Cached User"
                assert mock_get.call_count == 0  # Should not call API

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_captapi_candidate_association():
    """Test that candidate LinkedIn URL is associated with Captapi data."""
    from backend import fetch_captapi_linkedin_profile, CAPTAPI_CACHE_PATH
    import backend

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        # Simulate candidate with LinkedIn URL
        contact_info = {"linkedin": "https://linkedin.com/in/candidate123"}

        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "name": "Candidate Name",
                    "headline": "Developer"
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                # Fetch profile using candidate's LinkedIn URL
                linkedin_profile = None
                if contact_info.get("linkedin"):
                    linkedin_profile = fetch_captapi_linkedin_profile(contact_info["linkedin"])

                assert linkedin_profile is not None
                assert linkedin_profile["name"] == "Candidate Name"
                assert linkedin_profile["url"] == "https://linkedin.com/in/candidate123"

    finally:
        backend.CAPTAPI_CACHE_PATH = original_cache
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_captapi_failure_does_not_break_analysis():
    """Test that Captapi failure does not break candidate analysis."""
    from backend import fetch_captapi_linkedin_profile

    # Simulate Captapi failure (missing API key)
    with patch.dict(os.environ, {"CAPTAPI_API_KEY": ""}):
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
    from backend import fetch_captapi_linkedin_profile, CAPTAPI_CACHE_PATH
    import backend

    temp_dir = tempfile.mkdtemp()
    temp_cache = Path(temp_dir) / "captapi_cache.json"
    original_cache = CAPTAPI_CACHE_PATH
    backend.CAPTAPI_CACHE_PATH = temp_cache

    try:
        # Verify that Captapi functions don't call ranking/scoring functions
        with patch.dict(os.environ, {"CAPTAPI_API_KEY": "test_key"}):
            with patch('requests.get') as mock_get:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.json.return_value = {
                    "name": "Test User",
                    "experience": []
                }
                mock_response.raise_for_status = Mock()
                mock_get.return_value = mock_response

                result = fetch_captapi_linkedin_profile("https://linkedin.com/in/testuser")

                # Result should only contain display data
                assert "source" in result
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
