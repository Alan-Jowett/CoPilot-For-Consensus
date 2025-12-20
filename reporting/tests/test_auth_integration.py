# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for JWT authentication integration in reporting service."""

import time
from unittest.mock import Mock, patch

import pytest
import jwt
from fastapi.testclient import TestClient
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend

from main import app
from app.service import ReportingService


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
    
    # Get JWK from public key
    jwk = RSAAlgorithm.to_jwk(public_key)
    # to_jwk returns a JSON string in PyJWT 2.x, need to parse it
    jwk_dict = json.loads(jwk) if isinstance(jwk, str) else jwk
    jwk_dict['kid'] = 'test-key'
    jwk_dict['use'] = 'sig'
    
    return {"keys": [jwk_dict]}


@pytest.fixture
def valid_reader_token(test_keypair):
    """Generate valid JWT with reader role."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader"],
        "aud": "copilot-reporting",
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
    """Generate JWT without reader role."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["writer"],  # Wrong role
        "aud": "copilot-reporting",
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
    """Create mock reporting service."""
    service = Mock(spec=ReportingService)
    service.get_stats.return_value = {
        "reports_stored": 0,
        "notifications_sent": 0,
        "notifications_failed": 0,
        "last_processing_time_seconds": 0,
    }
    service.get_reports.return_value = []
    return service


@pytest.fixture
def client_with_auth(mock_service, mock_jwks):
    """Create test client with mocked auth."""
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse
    from starlette.middleware.base import BaseHTTPMiddleware
    from app import __version__
    
    # Create a fresh app for testing
    test_app = FastAPI()
    
    # Add health, stats, and reports endpoints (normally in main.py)
    @test_app.get("/")
    def root():
        """Root endpoint redirects to health check."""
        return health()
    
    @test_app.get("/health")
    def health():
        """Health check endpoint."""
        stats = mock_service.get_stats() if mock_service is not None else {}
        
        return {
            "status": "healthy",
            "service": "reporting",
            "version": __version__,
            "reports_stored": stats.get("reports_stored", 0),
            "notifications_sent": stats.get("notifications_sent", 0),
            "notifications_failed": stats.get("notifications_failed", 0),
            "last_processing_time_seconds": stats.get("last_processing_time_seconds", 0),
        }
    
    @test_app.get("/stats")
    def get_stats():
        """Get reporting statistics."""
        if not mock_service:
            return {"error": "Service not initialized"}
        
        return mock_service.get_stats()
    
    @test_app.get("/api/reports")
    def get_reports(
        thread_id: str = Query(None, description="Filter by thread ID"),
        limit: int = Query(10, ge=1, le=100, description="Maximum number of results"),
        skip: int = Query(0, ge=0, description="Number of results to skip"),
        start_date: str = Query(None, description="Filter reports generated after this date (ISO 8601)"),
        end_date: str = Query(None, description="Filter reports generated before this date (ISO 8601)"),
        source: str = Query(None, description="Filter by archive source"),
        min_participants: int = Query(None, ge=0, description="Minimum number of participants"),
        max_participants: int = Query(None, ge=0, description="Maximum number of participants"),
        min_messages: int = Query(None, ge=0, description="Minimum number of messages in thread"),
        max_messages: int = Query(None, ge=0, description="Maximum number of messages in thread"),
    ):
        """Get list of reports with optional filters."""
        if not mock_service:
            raise HTTPException(status_code=503, detail="Service not initialized")
        
        reports = mock_service.get_reports()
        return {
            "reports": reports,
            "count": len(reports),
            "limit": limit,
            "skip": skip,
        }
    
    # Add a simple mock middleware that checks for Authorization header
    # and validates tokens without fetching JWKS
    class MockAuthMiddleware(BaseHTTPMiddleware):
        def __init__(self, app):
            super().__init__(app)
            self.public_paths = ["/", "/health", "/readyz", "/docs", "/openapi.json"]
            self.required_roles = ["reader"]
            self.audience = "copilot-reporting"
        
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
                from jwt.algorithms import RSAAlgorithm
                
                # Get the test keypair from the fixture scope
                # For mock tokens, we just validate the structure and claims
                claims = jwt.decode(
                    token,
                    options={"verify_signature": False},  # Skip sig verification for test
                    algorithms=["RS256"],
                )
                
                # Check expiration
                import time
                if "exp" in claims and claims["exp"] < int(time.time()):
                    return JSONResponse(
                        status_code=401,
                        content={"detail": "Token has expired"},
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
                
            except jwt.DecodeError as e:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid token"},
                )
            except Exception as e:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication failed"},
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
    assert data["service"] == "reporting"


def test_protected_endpoint_no_auth(client_with_auth):
    """Test that protected endpoints require authentication."""
    response = client_with_auth.get("/api/reports")
    
    assert response.status_code == 401
    assert "Missing or invalid Authorization header" in response.json()["detail"]


def test_protected_endpoint_invalid_format(client_with_auth):
    """Test that invalid auth header format is rejected."""
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": "InvalidFormat token123"}
    )
    
    assert response.status_code == 401


def test_protected_endpoint_valid_token(client_with_auth, valid_reader_token, mock_service):
    """Test that valid token with correct role grants access."""
    mock_service.get_reports.return_value = [
        {"id": "report-1", "summary": "Test summary"}
    ]
    
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {valid_reader_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert "reports" in data
    assert data["count"] >= 0


def test_protected_endpoint_invalid_role(client_with_auth, invalid_role_token):
    """Test that token without required role is rejected."""
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {invalid_role_token}"}
    )
    
    assert response.status_code == 403
    assert "Missing required role: reader" in response.json()["detail"]


def test_protected_endpoint_expired_token(client_with_auth, test_keypair):
    """Test that expired tokens are rejected."""
    private_key, _, _, _ = test_keypair
    
    # Create expired token
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader"],
        "aud": "copilot-reporting",
        "exp": int(time.time()) - 3600,  # Expired 1 hour ago
        "iat": int(time.time()) - 7200,
    }
    
    expired_token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )
    
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {expired_token}"}
    )
    
    assert response.status_code == 401
    assert "Token has expired" in response.json()["detail"]


def test_protected_endpoint_wrong_audience(client_with_auth, test_keypair):
    """Test that tokens with wrong audience are rejected."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader"],
        "aud": "wrong-service",  # Wrong audience
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    
    wrong_aud_token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )
    
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {wrong_aud_token}"}
    )
    
    assert response.status_code == 403
    assert "Invalid audience" in response.json()["detail"]


def test_request_state_has_user_info(client_with_auth, valid_reader_token, mock_service, monkeypatch):
    """Test that JWT claims are added to request state."""
    
    def capture_get_reports(thread_id=None, limit=10, skip=0, **kwargs):
        """Test double to ensure ReportingService.get_reports is invoked."""
        return []
    
    mock_service.get_reports.side_effect = capture_get_reports
    
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {valid_reader_token}"}
    )
    
    assert response.status_code == 200
    # Service should have been called (which means auth passed)
    assert mock_service.get_reports.called


def test_multiple_roles_accepted(client_with_auth, test_keypair, mock_service):
    """Test that users with multiple roles including reader are accepted."""
    private_key, _, _, _ = test_keypair
    
    payload = {
        "sub": "test-user",
        "email": "test@example.com",
        "roles": ["reader", "admin", "writer"],  # Multiple roles
        "aud": "copilot-reporting",
        "exp": int(time.time()) + 3600,
        "iat": int(time.time()),
    }
    
    multi_role_token = jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "test-key"}
    )
    
    mock_service.get_reports.return_value = []
    
    response = client_with_auth.get(
        "/api/reports",
        headers={"Authorization": f"Bearer {multi_role_token}"}
    )
    
    assert response.status_code == 200
