# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT authentication integration in ingestion service."""

import time
from unittest.mock import Mock, patch

import pytest
import jwt
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from main import app
from app.service import IngestionService


@pytest.fixture
def test_keypair():
    """Generate RSA keypair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    public_key = private_key.public_key()
    
    # Serialize keys
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return private_key, public_key, private_pem, public_pem


@pytest.fixture
def mock_jwks(test_keypair):
    """Create mock JWKS response."""
    from jwt.algorithms import RSAAlgorithm
    _, public_key, _, _ = test_keypair
    
    jwk = RSAAlgorithm.to_jwk(public_key)
    jwk_dict = jwt.api_jwk.PyJWK(jwk).key
    jwk_dict['kid'] = 'test-key'
    jwk_dict['use'] = 'sig'
    
    return {"keys": [jwk_dict]}


@pytest.fixture
def valid_admin_token(test_keypair):
    """Generate valid JWT with admin role."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-admin",
        "email": "admin@example.com",
        "roles": ["admin"],
        "aud": "copilot-ingestion",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )
    
    return token


@pytest.fixture
def invalid_role_token(test_keypair):
    """Generate JWT without admin role."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader"],  # Wrong role
        "aud": "copilot-ingestion",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    
    token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )
    
    return token


@pytest.fixture
def mock_service():
    """Create mock ingestion service."""
    service = Mock(spec=IngestionService)
    service.get_stats.return_value = {
        "sources_configured": 0,
        "sources_enabled": 0,
        "total_files_ingested": 0,
        "last_ingestion_at": None,
    }
    service.list_sources.return_value = []
    return service


@pytest.fixture
def client_with_auth(mock_service, mock_jwks, monkeypatch):
    """Create test client with mocked auth."""
    import main
    monkeypatch.setattr(main, "ingestion_service", mock_service)
    
    with patch("httpx.get") as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response
        
        yield TestClient(app)


def test_health_endpoint_public_no_auth(client_with_auth):
    """Test that health endpoint is accessible without authentication."""
    response = client_with_auth.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "ingestion"


def test_root_endpoint_public_no_auth(client_with_auth):
    """Test that root endpoint (redirects to health) is accessible without authentication."""
    response = client_with_auth.get("/")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_protected_api_no_auth(client_with_auth):
    """Test that API endpoints require authentication."""
    response = client_with_auth.get("/api/sources")
    
    assert response.status_code == 401


def test_protected_api_valid_admin_token(client_with_auth, valid_admin_token, mock_service):
    """Test that valid admin token grants access to source management."""
    mock_service.list_sources.return_value = [
        {"name": "test-source", "enabled": True}
    ]
    
    response = client_with_auth.get(
        "/api/sources",
        headers={"Authorization": f"Bearer {valid_admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "sources" in data


def test_protected_api_invalid_role(client_with_auth, invalid_role_token):
    """Test that non-admin users cannot access source management."""
    response = client_with_auth.get(
        "/api/sources",
        headers={"Authorization": f"Bearer {invalid_role_token}"}
    )
    
    assert response.status_code == 403
    assert "Missing required role: admin" in response.json()["detail"]


def test_stats_endpoint_requires_auth(client_with_auth, valid_admin_token, mock_service):
    """Test that stats endpoint requires authentication."""
    # Without auth
    response = client_with_auth.get("/stats")
    assert response.status_code == 401
    
    # With valid admin token
    response = client_with_auth.get(
        "/stats",
        headers={"Authorization": f"Bearer {valid_admin_token}"}
    )
    assert response.status_code == 200
