"""
Unit tests for GitHub public evidence fetching and caching.

Tests use mocked GitHub API responses to avoid dependency on live GitHub availability.
"""

import json
from unittest.mock import Mock, patch

import pytest

from backend import (
    GITHUB_EVIDENCE_CACHE_VERSION,
    extract_github_username,
    fetch_github_public_data,
    get_github_cache_key,
    get_github_evidence,
    normalize_github_url,
)


def test_normalize_github_url_basic():
    """Test basic GitHub URL normalization."""
    test_cases = [
        ("github.com/johndoe", "https://github.com/johndoe"),
        ("https://github.com/johndoe", "https://github.com/johndoe"),
        ("  github.com/johndoe  ", "https://github.com/johndoe"),
        ("github.com/johndoe/", "https://github.com/johndoe"),
        ("https://github.com/johndoe/", "https://github.com/johndoe"),
    ]

    for input_url, expected in test_cases:
        result = normalize_github_url(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"


def test_normalize_github_url_with_repo():
    """Test GitHub URL normalization with repository."""
    test_cases = [
        ("github.com/johndoe/myproject", "https://github.com/johndoe/myproject"),
        (
            "https://github.com/johndoe/myproject",
            "https://github.com/johndoe/myproject",
        ),
    ]

    for input_url, expected in test_cases:
        result = normalize_github_url(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"


def test_normalize_github_url_invalid():
    """Test that invalid URLs return None."""
    test_cases = [
        None,
        "",
        "not a url",
        "https://example.com/johndoe",
        "linkedin.com/in/johndoe",
    ]

    for input_url in test_cases:
        result = normalize_github_url(input_url)
        assert result is None, f"Expected None for {input_url}, got {result}"


def test_extract_github_username():
    """Test GitHub username extraction."""
    test_cases = [
        ("https://github.com/johndoe", "johndoe"),
        ("https://github.com/johndoe/myproject", "johndoe"),
        ("github.com/johndoe", "johndoe"),
        ("github.com/johndoe/myproject", "johndoe"),
    ]

    for input_url, expected in test_cases:
        result = extract_github_username(input_url)
        assert (
            result == expected
        ), f"Failed for {input_url}: got {result}, expected {expected}"


def test_extract_github_username_invalid():
    """Test username extraction from invalid URLs."""
    test_cases = [
        None,
        "",
        "https://example.com/johndoe",
        "linkedin.com/in/johndoe",
    ]

    for input_url in test_cases:
        result = extract_github_username(input_url)
        assert result is None, f"Expected None for {input_url}, got {result}"


@patch("backend.urllib.request.urlopen")
def test_fetch_github_public_data_success(mock_urlopen):
    """Test successful GitHub profile fetch with minimal mocking."""
    # Mock GitHub API response for profile
    mock_response = Mock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(
        {
            "login": "johndoe",
            "name": "John Doe",
            "bio": "Software Engineer",
            "location": "San Francisco",
            "public_repos": 10,
            "followers": 100,
            "following": 50,
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z",
            "avatar_url": "https://example.com/avatar.png",
            "html_url": "https://github.com/johndoe",
        }
    ).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_github_public_data("https://github.com/johndoe")

    assert result["source"] == "github"
    assert result["status"] == "available"
    assert result["profile"]["username"] == "johndoe"
    assert result["profile"]["name"] == "John Doe"
    # Repositories may be empty if the fetch fails, but profile should be present
    assert "repositories" in result


@patch("backend.urllib.request.urlopen")
def test_fetch_github_public_data_404(mock_urlopen):
    """Test GitHub 404 (profile not found)."""
    mock_response = Mock()
    mock_response.status = 404
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_github_public_data("https://github.com/nonexistent")

    assert result["source"] == "github"
    assert result["status"] == "unavailable"
    assert "404" in result["error"]


@patch("backend.urllib.request.urlopen")
def test_fetch_github_public_data_403(mock_urlopen):
    """Test GitHub 403 (private profile)."""
    mock_response = Mock()
    mock_response.status = 403
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_github_public_data("https://github.com/privateuser")

    assert result["source"] == "github"
    assert result["status"] == "unavailable"
    assert "403" in result["error"]


@patch("backend.urllib.request.urlopen")
def test_fetch_github_public_data_429(mock_urlopen):
    """Test GitHub 429 (rate limit)."""
    mock_response = Mock()
    mock_response.status = 429
    mock_urlopen.return_value.__enter__.return_value = mock_response

    result = fetch_github_public_data("https://github.com/johndoe")

    assert result["source"] == "github"
    assert result["status"] == "unavailable"
    assert "429" in result["error"]


@patch("backend.urllib.request.urlopen")
def test_fetch_github_public_data_network_error(mock_urlopen):
    """Test network error handling."""
    import urllib.error

    mock_urlopen.side_effect = urllib.error.URLError("Network error")

    result = fetch_github_public_data("https://github.com/johndoe")

    assert result["source"] == "github"
    assert result["status"] == "error"
    assert "Network error" in result["error"]


def test_get_github_cache_key():
    """Test cache key generation."""
    url1 = "https://github.com/johndoe"
    url2 = "github.com/johndoe"
    url3 = "https://github.com/johndoe/"

    key1 = get_github_cache_key(url1)
    key2 = get_github_cache_key(url2)
    key3 = get_github_cache_key(url3)

    # All should produce the same cache key
    assert key1 == key2 == key3

    # Invalid URL should return None
    assert get_github_cache_key("invalid url") is None
    assert get_github_cache_key(None) is None


@patch("backend.get_github_cache_key")
@patch("backend.write_json_file")
@patch("backend.read_json_file")
def test_get_github_evidence_cache_hit(mock_read_json, mock_write_json, mock_cache_key):
    """Test cache hit scenario."""
    cache_key = "test_cache_key"

    # Mock cache key to return our test key
    mock_cache_key.return_value = cache_key

    # Mock cache with valid cached data
    mock_read_json.return_value = {
        cache_key: {
            "source": "github",
            "status": "available",
            "cache_version": GITHUB_EVIDENCE_CACHE_VERSION,
            "fetched_at": "2024-01-01T00:00:00Z",
            "profile": {"username": "johndoe"},
            "repositories": [],
        }
    }

    result = get_github_evidence("https://github.com/johndoe")

    assert result["source"] == "github"
    assert result["status"] == "available"
    assert result["profile"]["username"] == "johndoe"
    assert result["cache_version"] == GITHUB_EVIDENCE_CACHE_VERSION

    # Should not call write_json_file on cache hit
    mock_write_json.assert_not_called()


@patch("backend.write_json_file")
@patch("backend.read_json_file")
@patch("backend.fetch_github_public_data")
def test_get_github_evidence_cache_miss(mock_fetch, mock_read_json, mock_write_json):
    """Test cache miss and data fetch."""
    # Mock empty cache
    mock_read_json.return_value = {}

    # Mock fetch result
    mock_fetch.return_value = {
        "source": "github",
        "status": "available",
        "profile": {"username": "janedoe"},
        "repositories": [],
        "github_url": "https://github.com/janedoe",
    }

    result = get_github_evidence("https://github.com/janedoe")

    assert result["source"] == "github"
    assert result["status"] == "available"
    assert result["profile"]["username"] == "janedoe"
    assert result["cache_version"] == GITHUB_EVIDENCE_CACHE_VERSION
    assert "fetched_at" in result

    # Should write to cache
    mock_write_json.assert_called_once()


@patch("backend.write_json_file")
@patch("backend.read_json_file")
def test_get_github_evidence_stale_cache(mock_read_json, mock_write_json):
    """Test stale cache (version mismatch)."""
    cache_key = "test_cache_key_3"

    # Mock cache with old version
    mock_read_json.return_value = {
        cache_key: {
            "source": "github",
            "status": "available",
            "cache_version": "v0",  # Old version
            "profile": {"username": "olddoe"},
            "repositories": [],
        }
    }

    with patch("backend.fetch_github_public_data") as mock_fetch:
        mock_fetch.return_value = {
            "source": "github",
            "status": "available",
            "profile": {"username": "newdoe"},
            "repositories": [],
            "github_url": "https://github.com/newdoe",
        }

        result = get_github_evidence("https://github.com/newdoe")

        assert result["profile"]["username"] == "newdoe"
        assert result["cache_version"] == GITHUB_EVIDENCE_CACHE_VERSION


@patch("backend.write_json_file")
@patch("backend.read_json_file")
def test_get_github_evidence_force_refresh(mock_read_json, mock_write_json):
    """Test force refresh bypasses cache."""
    cache_key = "test_cache_key_4"

    # Mock cache with valid data
    mock_read_json.return_value = {
        cache_key: {
            "source": "github",
            "status": "available",
            "cache_version": GITHUB_EVIDENCE_CACHE_VERSION,
            "profile": {"username": "cacheduser"},
            "repositories": [],
        }
    }

    with patch("backend.fetch_github_public_data") as mock_fetch:
        mock_fetch.return_value = {
            "source": "github",
            "status": "available",
            "profile": {"username": "freshuser"},
            "repositories": [],
            "github_url": "https://github.com/freshuser",
        }

        result = get_github_evidence("https://github.com/freshuser", force_refresh=True)

        assert result["profile"]["username"] == "freshuser"
        assert result["cache_version"] == GITHUB_EVIDENCE_CACHE_VERSION


@patch("backend.write_json_file")
@patch("backend.read_json_file")
def test_get_github_evidence_invalid_url(mock_read_json, mock_write_json):
    """Test with invalid GitHub URL."""
    mock_read_json.return_value = {}

    result = get_github_evidence("invalid url")

    assert result["source"] == "github"
    assert result["status"] == "unverifiable"
    assert "Invalid GitHub URL" in result["error"]

    # Should not write to cache for invalid URL
    mock_write_json.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
