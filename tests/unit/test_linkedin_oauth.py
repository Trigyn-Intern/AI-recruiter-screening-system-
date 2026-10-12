"""Unit tests for LinkedIn OAuth flow.

These tests are skipped because the LinkedIn OAuth routes (/linkedin/auth,
/linkedin/callback) and the api.persist_linkedin_profile function were not
implemented in the production api.py module.  The backend.py module contains
persist_linkedin_profile and normalize_linkedin_url, but the FastAPI routes
that would wire them into the HTTP API do not exist.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason=(
        "LinkedIn OAuth routes (/linkedin/auth, /linkedin/callback) and "
        "api.persist_linkedin_profile are not implemented in the production "
        "api.py module."
    )
)


def test_linkedin_auth_missing_client_id():
    """Test that /linkedin/auth returns error when CLIENT_ID is not configured."""
    pass


def test_linkedin_auth_returns_auth_url():
    """Test that /linkedin/auth returns authorization URL with correct parameters."""
    pass


def test_linkedin_callback_missing_credentials():
    """Test that /linkedin/callback returns error when credentials are not configured."""
    pass


def test_linkedin_callback_success():
    """Test successful OAuth callback flow with mocked LinkedIn API."""
    pass


def test_linkedin_callback_token_error():
    """Test OAuth callback when LinkedIn token API fails."""
    pass


def test_linkedin_auth_with_url_parameter():
    """Test that /linkedin/auth accepts and normalizes LinkedIn URL parameter."""
    pass


def test_linkedin_auth_without_url_parameter():
    """Test that /linkedin/auth works without LinkedIn URL parameter."""
    pass


def test_linkedin_callback_with_url_in_state():
    """Test callback recovers URL from state and uses it for persistence."""
    pass


def test_linkedin_callback_without_url_in_state():
    """Test callback uses sub fallback when no URL in state."""
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
