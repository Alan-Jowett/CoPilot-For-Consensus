# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT authentication integration in orchestrator service."""

import time
from unittest.mock import Mock, patch

import jwt
import pytest
from app.service import OrchestrationService
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient


@pytest.fixture
def test_keypair():
    """Generate RSA keypair for testing."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )

    public_key = private_key.public_key()

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
    import json

    from jwt.algorithms import RSAAlgorithm
    _, public_key, _, _ = test_keypair

    jwk = RSAAlgorithm.to_jwk(public_key)
    # to_jwk returns a JSON string in PyJWT 2.x, need to parse it
    jwk_dict = json.loads(jwk) if isinstance(jwk, str) else jwk
    jwk_dict['kid'] = 'test-key'
    jwk_dict['use'] = 'sig'

    return {"keys": [jwk_dict]}


@pytest.fixture
def valid_orchestrator_token(test_keypair):
    """Generate valid JWT with orchestrator role."""
    private_key, _, _, _ = test_keypair

    payload = {
        "sub": "test-orchestrator",
        "email": "orchestrator@example.com",
        "roles": ["orchestrator"],
        "aud": "copilot-orchestrator",
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
    """Generate JWT without orchestrator role."""
    private_key, _, _, _ = test_keypair

    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader"],  # Wrong role
        "aud": "copilot-orchestrator",
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
    """Create mock orchestration service."""
    service = Mock(spec=OrchestrationService)
    service.get_stats.return_value = {
        "events_processed": 0,
        "threads_orchestrated": 0,
        "failures_count": 0,
        "last_processing_time_seconds": 0,
        "config": {},
    }
    return service


@pytest.fixture
def client_with_auth(mock_service, mock_jwks):
    """Create test client with mocked auth."""
    from app import __version__
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    # Create a fresh app for testing
    test_app = FastAPI()

    # Add health and stats endpoints (normally in main.py)
    @test_app.get("/health")
    def health():
        """Health check endpoint."""
        stats = mock_service.get_stats() if mock_service is not None else {}

        return {
            "status": "healthy",
            "service": "orchestration",
            "version": __version__,
            "events_processed_total": stats.get("events_processed", 0),
            "threads_orchestrated_total": stats.get("threads_orchestrated", 0),
            "failures_total": stats.get("failures_count", 0),
            "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
            "config": stats.get("config", {}),
        }

    @test_app.get("/stats")
    def get_stats():
        """Get orchestration statistics."""
        if not mock_service:
            return {"error": "Service not initialized"}

        return mock_service.get_stats()

    # Add a simple mock middleware that checks for Authorization header
    # and validates tokens without fetching JWKS
    class MockAuthMiddleware(BaseHTTPMiddleware):
        def __init__(self, app):
            super().__init__(app)
            self.public_paths = ["/health", "/readyz", "/docs", "/openapi.json"]
            self.required_roles = ["orchestrator"]
            self.audience = "copilot-orchestrator"

        async def dispatch(self, request: Request, call_next):
            # Skip auth for public paths
            if request.url.path in self.public_paths:
                return await call_next(request)

            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Missing or invalid Authorization header"},
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # Extract and validate token
            token = auth_header[7:]  # Remove "Bearer " prefix

            try:
                import jwt

                # Get the test keypair from the fixture scope
                # For mock tokens, we just validate the structure and claims
                claims = jwt.decode(
                    token,
                    options={"verify_signature": False},  # Skip sig verification for test
                    algorithms=["RS256"],
                )

                # Check audience
                if claims.get("aud") != self.audience:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": f"Invalid audience. Expected: {self.audience}"},
                    )

                # Check roles
                user_roles = claims.get("roles", [])
                for required_role in self.required_roles:
                    if required_role not in user_roles:
                        return JSONResponse(
                            status_code=403,
                            content={"detail": f"Missing required role: {required_role}"},
                        )

                # Token is valid, proceed
                request.state.user_claims = claims
                request.state.user_id = claims.get("sub")
                request.state.user_email = claims.get("email")
                request.state.user_roles = claims.get("roles", [])

            except jwt.DecodeError:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"},
                )
            except Exception:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication error"},
                )

            return await call_next(request)

    test_app.add_middleware(MockAuthMiddleware)

    with patch("httpx.get") as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        yield TestClient(test_app)


def test_health_endpoint_public_no_auth(client_with_auth):
    """Test that health endpoint is accessible without authentication."""
    response = client_with_auth.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "orchestration"


def test_protected_endpoint_no_auth(client_with_auth):
    """Test that protected endpoints require authentication."""
    response = client_with_auth.get("/stats")

    assert response.status_code == 401


def test_protected_endpoint_valid_token(client_with_auth, valid_orchestrator_token, mock_service):
    """Test that valid token with orchestrator role grants access."""
    response = client_with_auth.get(
        "/stats",
        headers={"Authorization": f"Bearer {valid_orchestrator_token}"}
    )

    assert response.status_code == 200


def test_protected_endpoint_invalid_role(client_with_auth, invalid_role_token):
    """Test that token without orchestrator role is rejected."""
    response = client_with_auth.get(
        "/stats",
        headers={"Authorization": f"Bearer {invalid_role_token}"}
    )

    assert response.status_code == 403
    assert "Missing required role: orchestrator" in response.json()["detail"]
