# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for public key endpoints."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture
def mock_auth_service():
    """Create a mock auth service with JWT manager."""
    service = MagicMock()
    service.config.service_settings.audiences = "copilot-for-consensus"

    # Mock JWT manager with public key
    jwt_manager = MagicMock()
    jwt_manager.get_public_key_pem.return_value = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z6Wr1nN3dkp1pL5JHQN
-----END PUBLIC KEY-----"""
    jwt_manager.get_jwks.return_value = {"keys": [{"kty": "RSA", "use": "sig", "kid": "default", "alg": "RS256"}]}
    service.jwt_manager = jwt_manager

    # main.py calls auth_service.get_jwks()
    service.get_jwks.return_value = jwt_manager.get_jwks.return_value

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


def test_public_key_endpoint(test_client: TestClient):
    """Test that public key endpoint returns valid PEM data."""
    response = test_client.get("/.well-known/public_key.pem")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-pem-file"

    # Check that response contains PEM markers
    content = response.text
    assert "-----BEGIN PUBLIC KEY-----" in content
    assert "-----END PUBLIC KEY-----" in content


def test_jwks_endpoint(test_client: TestClient):
    """Test that JWKS endpoint returns valid JWK format."""
    response = test_client.get("/.well-known/jwks.json")
    assert response.status_code == 200

    data = response.json()
    assert "keys" in data
    assert isinstance(data["keys"], list)

    # If using RS256, should have at least one key
    if len(data["keys"]) > 0:
        key = data["keys"][0]
        assert "kty" in key
        assert "use" in key
        assert "kid" in key
        assert "alg" in key


def test_keys_endpoint(test_client: TestClient):
    """Test that /keys endpoint returns same data as /.well-known/jwks.json."""
    response_keys = test_client.get("/keys")
    response_wellknown = test_client.get("/.well-known/jwks.json")

    assert response_keys.status_code == 200
    assert response_wellknown.status_code == 200

    # Both endpoints should return the same data
    assert response_keys.json() == response_wellknown.json()
