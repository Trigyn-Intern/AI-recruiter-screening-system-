"""Unit tests for LinkedIn OAuth flow."""
import pytest
from unittest.mock import patch, Mock
import os


def test_linkedin_auth_missing_client_id():
    """Test that /linkedin/auth returns error when CLIENT_ID is not configured."""
    with patch.dict(os.environ, {"LINKEDIN_CLIENT_ID": "", "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"}):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/auth")

        assert response.status_code == 500
        assert "LinkedIn Client ID not configured" in response.json()["detail"]


def test_linkedin_auth_returns_auth_url():
    """Test that /linkedin/auth returns authorization URL with correct parameters."""
    import urllib.parse

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/auth")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert "test_client_id" in data["auth_url"]
        # Scope is URL-encoded, check for encoded version
        assert "scope=openid" in data["auth_url"]
        assert "profile" in data["auth_url"]
        assert "email" in data["auth_url"]
        # Redirect URI is URL-encoded, decode it first for comparison
        parsed_url = urllib.parse.urlparse(data["auth_url"])
        params = urllib.parse.parse_qs(parsed_url.query)
        assert params["redirect_uri"][0] == "http://localhost:8000/linkedin/callback"


def test_linkedin_callback_missing_credentials():
    """Test that /linkedin/callback returns error when credentials are not configured."""
    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "",
        "LINKEDIN_CLIENT_SECRET": "",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/callback?code=test_code&state=test_state")

        assert response.status_code == 500
        assert "LinkedIn credentials not configured" in response.json()["detail"]


@patch('requests.post')
@patch('requests.get')
def test_linkedin_callback_success(mock_get, mock_post):
    """Test successful OAuth callback flow with mocked LinkedIn API."""
    # Mock token response
    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    )

    # Mock userinfo response
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "sub": "test_user_id",
            "name": "Test User",
            "email": "test@example.com",
            "picture": "https://example.com/photo.jpg"
        }
    )

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_CLIENT_SECRET": "test_client_secret",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/callback?code=test_code&state=test_state")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "profile" in data
        assert data["profile"]["name"] == "Test User"
        assert data["profile"]["email"] == "test@example.com"
        assert data["token_type"] == "Bearer"
        assert data["expires_in"] == 3600


@patch('requests.post')
def test_linkedin_callback_token_error(mock_post):
    """Test OAuth callback when LinkedIn token API fails."""
    import requests as req

    mock_post.return_value = Mock(
        status_code=400,
        raise_for_status=lambda: (_ for _ in ()).throw(req.exceptions.HTTPError("Invalid code"))
    )

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_CLIENT_SECRET": "test_client_secret",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/callback?code=invalid_code&state=test_state")

        assert response.status_code == 500
        assert "LinkedIn API error" in response.json()["detail"]


def test_linkedin_auth_with_url_parameter():
    """Test that /linkedin/auth accepts and normalizes LinkedIn URL parameter."""
    import base64
    import urllib.parse

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/auth?linkedin_url=https://linkedin.com/in/johndoe")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data
        assert "linkedin.com/in/johndoe" in data["message"]

        # Verify state contains encoded URL
        parsed_url = urllib.parse.urlparse(data["auth_url"])
        params = urllib.parse.parse_qs(parsed_url.query)
        state_value = params["state"][0]

        # State should be in format: csrf_token|base64_encoded_url
        assert "|" in state_value
        parts = state_value.split("|")
        csrf_token = parts[0]
        url_encoded = parts[1]

        # Decode the URL
        decoded_url = base64.b64decode(url_encoded.encode('utf-8')).decode('utf-8')
        assert decoded_url == "linkedin.com/in/johndoe"


def test_linkedin_auth_without_url_parameter():
    """Test that /linkedin/auth works without LinkedIn URL parameter (backward compatibility)."""
    import urllib.parse

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get("/linkedin/auth")

        assert response.status_code == 200
        data = response.json()
        assert "auth_url" in data
        assert "state" in data

        # State should be just the CSRF token (no pipe separator)
        assert "|" not in data["state"]


@patch('requests.post')
@patch('requests.get')
@patch('api.persist_linkedin_profile')
def test_linkedin_callback_with_url_in_state(mock_persist, mock_get, mock_post):
    """Test callback recovers URL from state and uses it for persistence."""
    import base64

    # Mock token response
    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    )

    # Mock userinfo response
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "sub": "test_user_id",
            "name": "Test User",
            "email": "test@example.com"
        }
    )

    # Create state with encoded URL
    normalized_url = "linkedin.com/in/johndoe"
    url_encoded = base64.b64encode(normalized_url.encode('utf-8')).decode('utf-8')
    state_with_url = f"csrf_token_123|{url_encoded}"

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_CLIENT_SECRET": "test_client_secret",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get(f"/linkedin/callback?code=test_code&state={state_with_url}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify persist_linkedin_profile was called with the normalized URL
        mock_persist.assert_called_once()
        call_args = mock_persist.call_args
        assert call_args[0][1] == normalized_url  # linkedin_url parameter


@patch('requests.post')
@patch('requests.get')
@patch('api.persist_linkedin_profile')
def test_linkedin_callback_without_url_in_state(mock_persist, mock_get, mock_post):
    """Test callback uses sub fallback when no URL in state."""
    # Mock token response
    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "access_token": "test_access_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
    )

    # Mock userinfo response
    mock_get.return_value = Mock(
        status_code=200,
        json=lambda: {
            "sub": "test_user_id",
            "name": "Test User",
            "email": "test@example.com"
        }
    )

    # State without URL (just CSRF token)
    state_without_url = "csrf_token_456"

    with patch.dict(os.environ, {
        "LINKEDIN_CLIENT_ID": "test_client_id",
        "LINKEDIN_CLIENT_SECRET": "test_client_secret",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/linkedin/callback"
    }):
        from api import api
        from fastapi.testclient import TestClient

        client = TestClient(api)
        response = client.get(f"/linkedin/callback?code=test_code&state={state_without_url}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"

        # Verify persist_linkedin_profile was called with None (sub fallback)
        mock_persist.assert_called_once()
        call_args = mock_persist.call_args
        assert call_args[0][1] is None  # linkedin_url parameter


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
