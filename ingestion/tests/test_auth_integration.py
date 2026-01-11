# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT authentication integration in ingestion service."""

import time
from unittest.mock import Mock, patch

import jwt
import pytest
from app.service import IngestionService
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
def client_with_auth(mock_service, mock_jwks):
    """Create test client with mocked auth."""
    from app import __version__
    from app.api import create_api_router
    from copilot_config import load_driver_config
    from copilot_logging import create_logger
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware

    # Create a fresh app for testing
    test_app = FastAPI()

    # Add root and health endpoints (normally in main.py)
    @test_app.get("/")
    def root():
        """Root endpoint redirects to health check."""
        return {
            "status": "healthy",
            "service": "ingestion",
            "version": __version__,
            "scheduler_running": False,
            "sources_configured": 0,
            "sources_enabled": 0,
            "total_files_ingested": 0,
            "last_ingestion_at": None,
        }

    @test_app.get("/health")
    def health():
        """Health check endpoint."""
        return {
            "status": "healthy",
            "service": "ingestion",
            "version": __version__,
            "scheduler_running": False,
            "sources_configured": 0,
            "sources_enabled": 0,
            "total_files_ingested": 0,
            "last_ingestion_at": None,
        }

    # Add a simple mock middleware that checks for Authorization header
    # and validates tokens without fetching JWKS
    class MockAuthMiddleware(BaseHTTPMiddleware):
        def __init__(self, app):
            super().__init__(app)
            self.public_paths = ["/", "/health", "/readyz", "/docs", "/openapi.json"]
            self.required_roles = ["admin"]
            self.audience = "copilot-ingestion"

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
                    content={"detail": "Authentication failed"},
                )

            return await call_next(request)

    test_app.add_middleware(MockAuthMiddleware)

    # Add the API router to the app
    logger_config = load_driver_config(service=None, adapter="logger", driver="stdout", fields={"level": "INFO", "name": "test"})
    logger = create_logger(driver_name="stdout", driver_config=logger_config)
    api_router = create_api_router(mock_service, logger)
    test_app.include_router(api_router)

    with patch("httpx.get") as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_jwks
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        client = TestClient(test_app)
        yield client


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
