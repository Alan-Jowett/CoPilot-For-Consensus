# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for cookie-based SSO functionality."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service."""
    service = MagicMock()
    service.config.audiences = "copilot-for-consensus"
    service.config.jwt_default_expiry = 1800  # 30 minutes

    # Mock handle_callback to return a JWT token
    service.handle_callback.return_value = "mock.jwt.token"

    return service


@pytest.fixture
def test_client(mock_auth_service):
    """Create test client with mocked auth service.

    Uses importlib.reload to ensure fresh module state for each test,
    avoiding test isolation issues from module caching.
    """
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


def test_callback_sets_cookie(test_client: TestClient):
    """Test that callback endpoint sets httpOnly cookie with JWT."""
    # Make callback request
    response = test_client.get("/callback?code=test_code&state=test_state")

    assert response.status_code == 200

    # Check response body contains JWT
    data = response.json()
    assert "access_token" in data
    assert data["access_token"] == "mock.jwt.token"
    assert data["token_type"] == "Bearer"

    # Check that cookie is set
    cookies = response.cookies
    assert "auth_token" in cookies
    assert cookies["auth_token"] == "mock.jwt.token"

    # Verify cookie attributes (checking raw set-cookie header for attributes)
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "auth_token=mock.jwt.token" in set_cookie_header
    assert "HttpOnly" in set_cookie_header
    assert "samesite=lax" in set_cookie_header.lower()
    assert "Path=/" in set_cookie_header


def test_logout_clears_cookie(test_client: TestClient):
    """Test that logout endpoint clears the auth cookie."""
    # Make logout request
    response = test_client.post("/logout")

    assert response.status_code == 200

    # Check response
    data = response.json()
    assert data["message"] == "Logged out successfully"

    # Check that cookie is cleared (max_age=0 or expires in past)
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "auth_token" in set_cookie_header
    # Cookie deletion is indicated by max-age=0 or expires in past
    assert any(x in set_cookie_header.lower() for x in ["max-age=0", "expires="])


def test_callback_cookie_expiry_matches_jwt(test_client: TestClient):
    """Test that cookie max_age matches JWT expiry time."""
    response = test_client.get("/callback?code=test_code&state=test_state")

    assert response.status_code == 200

    # Check cookie max_age
    set_cookie_header = response.headers.get("set-cookie", "")
    assert "Max-Age=1800" in set_cookie_header or "max-age=1800" in set_cookie_header


def test_cookie_secure_flag_from_env(mock_auth_service):
    """Test that AUTH_COOKIE_SECURE environment variable controls secure flag."""
    import os
    from unittest.mock import patch

    # Test with AUTH_COOKIE_SECURE=true
    with patch.dict(os.environ, {"AUTH_COOKIE_SECURE": "true"}):
        with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
            import main

            # Configure mock to return cookie_secure=True
            mock_auth_service.config.cookie_secure = True
            main.auth_service = mock_auth_service
            client = TestClient(main.app)

            response = client.get("/callback?code=test_code&state=test_state")
            assert response.status_code == 200

            set_cookie_header = response.headers.get("set-cookie", "")
            # When AUTH_COOKIE_SECURE=true, secure flag should be present
            assert "Secure" in set_cookie_header or "secure" in set_cookie_header.lower()

    # Test with AUTH_COOKIE_SECURE=false (default)
    with patch.dict(os.environ, {"AUTH_COOKIE_SECURE": "false"}, clear=False):
        with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
            # Need to reload the module to pick up new env var
            import importlib
            import main
            importlib.reload(main)

            # Configure mock to return cookie_secure=False
            mock_auth_service.config.cookie_secure = False
            main.auth_service = mock_auth_service
            client = TestClient(main.app)

            response = client.get("/callback?code=test_code&state=test_state")
            assert response.status_code == 200

            set_cookie_header = response.headers.get("set-cookie", "")
            # When AUTH_COOKIE_SECURE=false, we check that either:
            # - "Secure" is not a standalone attribute (it could be in "SameSite" or other words)
            # - or the cookie doesn't have secure flag at all
            # This is a bit tricky because "Secure" could appear in other contexts
            # Split by semicolon and check if "Secure" is a standalone attribute
            cookie_attrs = [attr.strip() for attr in set_cookie_header.split(";")]
            assert "Secure" not in cookie_attrs and "secure" not in [a.lower() for a in cookie_attrs if a.lower() == "secure"]
