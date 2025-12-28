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
    """Create test client with mocked auth service."""
    # Patch before importing main
    with patch("sys.path", [str(Path(__file__).parent.parent)] + sys.path):
        # Import main module
        import main

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
    assert "SameSite=lax" in set_cookie_header.lower()
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
