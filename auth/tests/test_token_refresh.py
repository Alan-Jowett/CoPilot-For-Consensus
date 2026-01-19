# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for automatic token refresh functionality."""

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service with token refresh support."""
    service = MagicMock()
    service.config.service_settings.audiences = "copilot-for-consensus"
    service.config.service_settings.jwt_default_expiry = 1800  # 30 minutes
    service.config.service_settings.cookie_secure = False

    # Mock validate_token to return user claims with expiration
    def validate_token_mock(token, audience):
        if token == "valid.jwt.token":
            return {
                "sub": "github|12345",
                "email": "test@example.com",
                "name": "Test User",
                "roles": ["admin"],
                "affiliations": ["test-org"],
                "aud": audience,
                "exp": int(time.time()) + 1800,  # Expires in 30 minutes
            }
        elif token == "expiring.jwt.token":
            return {
                "sub": "github|12345",
                "email": "test@example.com",
                "name": "Test User",
                "roles": ["admin"],
                "affiliations": ["test-org"],
                "aud": audience,
                "exp": int(time.time()) + 60,  # Expires in 1 minute
            }
        else:
            raise ValueError("Invalid token")

    service.validate_token = validate_token_mock

    # Mock providers for refresh endpoint
    service.providers = {
        "github": MagicMock(),
        "google": MagicMock(),
    }

    # Mock initiate_login for refresh flow
    async def initiate_login_mock(provider, audience, prompt=None):
        auth_url = f"https://{provider}.com/authorize?prompt={prompt}&aud={audience}"
        state = "mock-state-123"
        nonce = "mock-nonce-456"
        return auth_url, state, nonce

    service.initiate_login = initiate_login_mock

    return service


@pytest.fixture
def test_client(mock_auth_service):
    """Create test client with mocked auth service."""
    import importlib

    # Patch before importing main
    with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
        # Import main module
        import main

        # Reload the module to ensure fresh state
        importlib.reload(main)

        # Set the mock auth service
        main.auth_service = mock_auth_service

        return TestClient(main.app)


def test_userinfo_includes_expiration(test_client: TestClient):
    """Test that /userinfo includes token expiration timestamp."""
    response = test_client.get(
        "/userinfo",
        headers={"Authorization": "Bearer valid.jwt.token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "exp" in data
    assert isinstance(data["exp"], int)
    assert data["exp"] > int(time.time())  # Expiration is in the future


def test_userinfo_expiration_with_cookie(test_client: TestClient):
    """Test that /userinfo includes expiration when using cookie."""
    response = test_client.get(
        "/userinfo",
        cookies={"auth_token": "valid.jwt.token"}
    )

    assert response.status_code == 200
    data = response.json()
    assert "exp" in data
    assert isinstance(data["exp"], int)


def test_refresh_endpoint_exists(test_client: TestClient):
    """Test that /refresh endpoint exists and requires authentication."""
    response = test_client.get("/refresh")
    
    # Should return 401 without a token
    assert response.status_code == 401
    assert "No token found to refresh" in response.json()["detail"]


def test_refresh_endpoint_with_valid_token(test_client: TestClient):
    """Test that /refresh redirects to OIDC provider with prompt=none."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh",
            cookies={"auth_token": "valid.jwt.token"},
            follow_redirects=False,
        )

    # Should redirect to OIDC provider
    assert response.status_code == 302
    assert "Location" in response.headers
    
    # Check that redirect URL includes prompt=none
    location = response.headers["Location"]
    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "github.com"
    assert parsed.path == "/authorize"

    query = parse_qs(parsed.query)
    assert query.get("prompt") == ["none"]


def test_refresh_endpoint_infers_provider_from_token(test_client: TestClient):
    """Test that /refresh infers provider from token's sub claim."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh",
            cookies={"auth_token": "valid.jwt.token"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["Location"]
    # Token has sub="github|12345", so should use github provider
    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "github.com"
    assert parsed.path == "/authorize"


def test_refresh_endpoint_with_explicit_provider(test_client: TestClient):
    """Test that /refresh accepts explicit provider parameter."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh?provider=google",
            cookies={"auth_token": "valid.jwt.token"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["Location"]
    # Should use explicitly specified google provider
    parsed = urlparse(location)
    assert parsed.scheme == "https"
    assert parsed.netloc == "google.com"
    assert parsed.path == "/authorize"


def test_refresh_endpoint_with_authorization_header(test_client: TestClient):
    """Test that /refresh works with Authorization header."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh",
            headers={"Authorization": "Bearer valid.jwt.token"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    assert "Location" in response.headers


def test_refresh_endpoint_preserves_audience(test_client: TestClient):
    """Test that /refresh preserves the token's audience."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh",
            cookies={"auth_token": "valid.jwt.token"},
            follow_redirects=False,
        )

    assert response.status_code == 302
    location = response.headers["Location"]
    parsed = urlparse(location)
    query = parse_qs(parsed.query)
    # Should include the original audience
    assert query.get("aud") == ["copilot-for-consensus"]


def test_refresh_endpoint_with_invalid_provider(test_client: TestClient):
    """Test that /refresh returns 400 for unconfigured provider."""
    with patch(
        "main.jwt.decode",
        return_value={"sub": "github|12345", "aud": "copilot-for-consensus"},
    ):
        response = test_client.get(
            "/refresh?provider=invalid-provider",
            cookies={"auth_token": "valid.jwt.token"},
        )

    assert response.status_code == 400
    assert "not configured" in response.json()["detail"]
