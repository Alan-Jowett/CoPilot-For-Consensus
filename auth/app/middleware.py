# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""FastAPI middleware for JWT authentication.

This module provides middleware for validating JWT tokens in FastAPI applications,
enforcing audience and role-based access control.
"""

import os
from typing import Callable, List, Optional

import httpx
import jwt
from fastapi import HTTPException, Request, Response, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from copilot_logging import create_logger

logger = create_logger(logger_type="stdout", level="INFO", name="auth.middleware")


class JWTMiddleware(BaseHTTPMiddleware):
    """Middleware for JWT token validation.
    
    Validates JWTs on all requests except public endpoints.
    Enforces audience and optionally role-based access control.
    
    Attributes:
        auth_service_url: URL of auth service for JWKS retrieval
        audience: Expected audience for JWTs
        required_roles: Optional list of required roles
        public_paths: List of paths that don't require authentication
        jwks: Cached JSON Web Key Set
    """
    
    def __init__(
        self,
        app,
        auth_service_url: str,
        audience: str,
        required_roles: Optional[List[str]] = None,
        public_paths: Optional[List[str]] = None,
    ):
        """Initialize JWT middleware.
        
        Args:
            app: FastAPI application
            auth_service_url: URL of auth service (e.g., http://auth:8090)
            audience: Expected audience claim
            required_roles: Optional list of required roles
            public_paths: List of paths that don't require auth
        """
        super().__init__(app)
        self.auth_service_url = auth_service_url.rstrip("/")
        self.audience = audience
        self.required_roles = required_roles or []
        self.public_paths = public_paths or ["/health", "/readyz", "/docs", "/openapi.json"]
        
        # JWKS cache
        self.jwks: Optional[dict] = None
        self._fetch_jwks()
    
    def _fetch_jwks(self) -> None:
        """Fetch JWKS from auth service."""
        try:
            response = httpx.get(f"{self.auth_service_url}/keys", timeout=10.0)
            response.raise_for_status()
            self.jwks = response.json()
            logger.info(f"Fetched JWKS from {self.auth_service_url}/keys")
        
        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            self.jwks = {"keys": []}
    
    def _get_public_key(self, token_header: dict) -> Optional[str]:
        """Get public key for token validation.
        
        Args:
            token_header: Decoded JWT header with kid
        
        Returns:
            Public key in PEM format or None
        """
        if not self.jwks or "keys" not in self.jwks:
            self._fetch_jwks()
        
        kid = token_header.get("kid")
        if not kid:
            logger.warning("JWT missing kid in header")
            return None
        
        # Find matching key in JWKS
        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                # Convert JWK to PEM (simplified, use PyJWT's built-in for production)
                return key
        
        logger.warning(f"No matching key found for kid: {kid}")
        return None
    
    def _validate_token(self, token: str) -> dict:
        """Validate JWT token.
        
        Args:
            token: JWT token string
        
        Returns:
            Decoded token claims
        
        Raises:
            HTTPException: If token is invalid
        """
        try:
            # Decode header to get kid
            unverified_header = jwt.get_unverified_header(token)
            
            # Get public key
            jwk = self._get_public_key(unverified_header)
            if not jwk:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to find matching public key"
                )
            
            # Decode and validate token
            # Note: For production, use PyJWT's built-in JWK support
            # This is simplified for MVP
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(jwk)
            
            claims = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                audience=self.audience,
                options={"verify_exp": True}
            )
            
            return claims
        
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidAudienceError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid audience. Expected: {self.audience}"
            )
        except jwt.InvalidTokenError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )
    
    def _check_roles(self, claims: dict) -> None:
        """Check if user has required roles.
        
        Args:
            claims: JWT claims
        
        Raises:
            HTTPException: If user lacks required roles
        """
        if not self.required_roles:
            return
        
        user_roles = claims.get("roles", [])
        
        for required_role in self.required_roles:
            if required_role not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required role: {required_role}"
                )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and validate JWT.
        
        Args:
            request: Incoming request
            call_next: Next middleware/handler
        
        Returns:
            Response from handler
        """
        # Skip authentication for public paths
        if request.url.path in self.public_paths:
            return await call_next(request)
        
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing or invalid Authorization header",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Extract token
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate token
        try:
            claims = self._validate_token(token)
            
            # Check roles
            self._check_roles(claims)
            
            # Add claims to request state for downstream handlers
            request.state.user_claims = claims
            request.state.user_id = claims.get("sub")
            request.state.user_email = claims.get("email")
            request.state.user_roles = claims.get("roles", [])
            
            # Call next handler
            response = await call_next(request)
            return response
        
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Unexpected error during token validation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error"
            )


def create_jwt_middleware(
    auth_service_url: Optional[str] = None,
    audience: Optional[str] = None,
    required_roles: Optional[List[str]] = None,
    public_paths: Optional[List[str]] = None,
) -> type[JWTMiddleware]:
    """Factory function to create JWT middleware with configuration.
    
    Args:
        auth_service_url: URL of auth service (default: from AUTH_SERVICE_URL env)
        audience: Expected audience (default: from SERVICE_NAME env)
        required_roles: Optional list of required roles
        public_paths: List of paths that don't require auth
    
    Returns:
        Configured JWTMiddleware class
    
    Example:
        >>> from fastapi import FastAPI
        >>> app = FastAPI()
        >>> middleware = create_jwt_middleware(
        ...     auth_service_url="http://auth:8090",
        ...     audience="my-service"
        ... )
        >>> app.add_middleware(middleware)
    """
    # Get defaults from environment
    auth_url = auth_service_url or os.getenv("AUTH_SERVICE_URL", "http://auth:8090")
    aud = audience or os.getenv("SERVICE_NAME", "copilot-service")
    
    # Create configured middleware class
    class ConfiguredJWTMiddleware(JWTMiddleware):
        def __init__(self, app):
            super().__init__(
                app=app,
                auth_service_url=auth_url,
                audience=aud,
                required_roles=required_roles,
                public_paths=public_paths,
            )
    
    return ConfiguredJWTMiddleware
