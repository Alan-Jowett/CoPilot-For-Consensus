# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for /userinfo endpoint with cookie support."""

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
    service.config.service_settings.audiences = "copilot-for-consensus"

    # Mock validate_token to return user claims
    def validate_token_mock(token, audience):
        if token == "valid.jwt.token":
            return {
                "sub": "test-user-123",
                "email": "test@example.com",
                "name": "Test User",
                "roles": ["admin"],
                "affiliations": ["test-org"],
                "aud": audience,
            }
        else:
            raise ValueError("Invalid token")

    service.validate_token = validate_token_mock

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


def test_userinfo_with_authorization_header(test_client: TestClient):
    """Test that /userinfo works with Authorization header."""
    response = test_client.get("/userinfo", headers={"Authorization": "Bearer valid.jwt.token"})

    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "test-user-123"
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["roles"] == ["admin"]
    assert data["affiliations"] == ["test-org"]
    assert data["aud"] == "copilot-for-consensus"


def test_userinfo_with_cookie(test_client: TestClient):
    """Test that /userinfo works with auth_token cookie."""
    response = test_client.get("/userinfo", cookies={"auth_token": "valid.jwt.token"})

    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "test-user-123"
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert data["roles"] == ["admin"]


def test_userinfo_prefers_authorization_header_over_cookie(test_client: TestClient):
    """Test that Authorization header takes precedence over cookie."""
    response = test_client.get(
        "/userinfo", headers={"Authorization": "Bearer valid.jwt.token"}, cookies={"auth_token": "different.token"}
    )

    # Should use the header token (valid.jwt.token)
    assert response.status_code == 200
    data = response.json()
    assert data["sub"] == "test-user-123"


def test_userinfo_without_token(test_client: TestClient):
    """Test that /userinfo returns 401 without token."""
    response = test_client.get("/userinfo")

    assert response.status_code == 401
    assert "Missing authentication token" in response.json()["detail"]


def test_userinfo_with_invalid_token_in_cookie(test_client: TestClient):
    """Test that /userinfo returns 401 with invalid cookie token."""
    response = test_client.get("/userinfo", cookies={"auth_token": "invalid.token"})

    assert response.status_code == 401


def test_userinfo_with_invalid_token_in_header(test_client: TestClient):
    """Test that /userinfo returns 401 with invalid header token."""
    response = test_client.get("/userinfo", headers={"Authorization": "Bearer invalid.token"})

    assert response.status_code == 401
