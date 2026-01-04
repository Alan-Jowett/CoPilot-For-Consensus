# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""FastAPI middleware for JWT authentication.

This module provides middleware for validating JWT tokens in FastAPI applications,
enforcing audience and role-based access control.

Usage:
    from copilot_auth import JWTMiddleware, create_jwt_middleware
    from fastapi import FastAPI

    app = FastAPI()

    # Option 1: Use factory function
    middleware = create_jwt_middleware(
        auth_service_url="http://auth:8090",
        audience="my-service",
        required_roles=["reader"]
    )
    app.add_middleware(middleware)

    # Option 2: Direct instantiation
    app.add_middleware(
        JWTMiddleware,
        auth_service_url="http://auth:8090",
        audience="my-service",
        required_roles=["reader"]
    )
"""

import os
import time
import traceback
from collections.abc import Callable
from typing import Any, cast

import httpx
import jwt
from copilot_logging import create_logger  # type: ignore[import-not-found]
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = create_logger(logger_type="stdout", level="INFO", name="copilot_auth.middleware")


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
        app: Any,
        auth_service_url: str,
        audience: str,
        required_roles: list[str] | None = None,
        public_paths: list[str] | None = None,
        jwks_cache_ttl: int = 3600,
        jwks_fetch_retries: int = 5,
        jwks_fetch_retry_delay: float = 1.0,
    ):
        """Initialize JWT middleware.

        Args:
            app: FastAPI application
            auth_service_url: URL of auth service (e.g., http://auth:8090)
            audience: Expected audience claim
            required_roles: Optional list of required roles
            public_paths: List of paths that don't require auth
            jwks_cache_ttl: JWKS cache TTL in seconds (default: 3600 = 1 hour)
            jwks_fetch_retries: Number of retries for initial JWKS fetch (default: 5)
            jwks_fetch_retry_delay: Initial delay between retries in seconds (default: 1.0)
        """
        super().__init__(app)
        self.auth_service_url = auth_service_url.rstrip("/")
        self.audience = audience
        self.required_roles = required_roles or []
        self.public_paths = public_paths or ["/health", "/readyz", "/docs", "/openapi.json"]
        self.jwks_cache_ttl = jwks_cache_ttl
        self.jwks_fetch_retries = jwks_fetch_retries
        self.jwks_fetch_retry_delay = jwks_fetch_retry_delay

        # JWKS cache with timestamp
        self.jwks: dict[str, Any] | None = None
        self.jwks_last_fetched: float = 0
        self._fetch_jwks_with_retry()

    def _fetch_jwks_with_retry(self) -> None:
        """Fetch JWKS from auth service with retry logic on startup.

        This method implements exponential backoff for the initial JWKS fetch
        to handle cases where the auth service is not yet ready during startup.
        """
        delay = self.jwks_fetch_retry_delay
        last_error = None

        for attempt in range(1, self.jwks_fetch_retries + 1):
            try:
                response = httpx.get(f"{self.auth_service_url}/keys", timeout=10.0)
                response.raise_for_status()
                jwks = response.json()
                self.jwks = jwks
                self.jwks_last_fetched = time.time()
                logger.info(
                    f"Successfully fetched JWKS from {self.auth_service_url}/keys "
                    f"({len(jwks.get('keys', []))} keys) on attempt {attempt}/{self.jwks_fetch_retries}"
                )
                return
            except (httpx.TimeoutException, httpx.ConnectError, httpx.ConnectTimeout) as e:
                last_error = e
                error_type = type(e).__name__
                if attempt < self.jwks_fetch_retries:
                    logger.warning(
                        f"JWKS fetch attempt {attempt}/{self.jwks_fetch_retries} failed: "
                        f"{error_type} - {e}. Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    logger.error(
                        f"JWKS fetch failed after {self.jwks_fetch_retries} attempts: "
                        f"{error_type} - {e}"
                    )
            except httpx.HTTPStatusError as e:
                last_error = e
                # For 503 Service Unavailable, retry; for other errors, fail immediately
                if e.response.status_code == 503:
                    if attempt < self.jwks_fetch_retries:
                        logger.warning(
                            f"Auth service unavailable (503) on attempt {attempt}/{self.jwks_fetch_retries}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay *= 2
                    else:
                        logger.error(
                            f"Auth service unavailable (503) after {self.jwks_fetch_retries} attempts"
                        )
                else:
                    logger.error(
                        f"JWKS fetch failed with HTTP {e.response.status_code}: {e}. "
                        f"Not retrying for this error type."
                    )
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error fetching JWKS: {type(e).__name__} - {e}")
                break

        # If we reach here, all retries failed - initialize with empty JWKS
        logger.error(
            f"Failed to fetch JWKS after {self.jwks_fetch_retries} attempts. "
            f"Authentication will fail until JWKS is available. Last error: {last_error}"
        )
        self.jwks = {"keys": []}

    def _fetch_jwks(self, force: bool = False) -> None:
        """Fetch JWKS from auth service with caching.

        Args:
            force: Force refresh even if cache is valid
        """
        # Check if cache is still valid
        if not force and self.jwks is not None:
            cache_age = time.time() - self.jwks_last_fetched
            if cache_age < self.jwks_cache_ttl:
                logger.debug(f"JWKS cache valid (age: {cache_age:.0f}s, TTL: {self.jwks_cache_ttl}s)")
                return

        try:
            response = httpx.get(f"{self.auth_service_url}/keys", timeout=10.0)
            response.raise_for_status()
            jwks = response.json()
            self.jwks = jwks
            self.jwks_last_fetched = time.time()
            logger.info(f"Fetched JWKS from {self.auth_service_url}/keys ({len(jwks.get('keys', []))} keys)")

        except Exception as e:
            logger.error(f"Failed to fetch JWKS: {e}")
            # Only reset on first fetch, keep stale cache on refresh failures
            if self.jwks is None:
                self.jwks = {"keys": []}

    def _get_public_key(self, token_header: dict[str, Any]) -> Any:
        """Get public key for token validation.

        Args:
            token_header: Decoded JWT header with kid

        Returns:
            Public key in PEM format or None
        """
        # Refresh cache if stale (periodic refresh for key rotation)
        self._fetch_jwks()

        if not self.jwks or "keys" not in self.jwks:
            logger.warning("JWKS cache empty or invalid")
            return None

        kid = token_header.get("kid")
        if not kid:
            logger.warning("JWT missing kid in header")
            return None

        # Find matching key in JWKS
        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                return key

        # Key not found - force refresh and retry once
        logger.warning(f"No matching key found for kid: {kid}, forcing JWKS refresh")
        self._fetch_jwks(force=True)

        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                logger.info(f"Found key {kid} after forced refresh")
                return key

        logger.error(f"Key {kid} not found even after forced refresh")
        return None

    def _validate_token(self, token: str) -> dict[Any, Any]:
        """Validate JWT token.

        Args:
            token: JWT token string

        Returns:
            Decoded token claims

        Raises:
            HTTPException: If token is invalid
        """
        try:
            logger.debug(
                "Validating JWT token",
                token_length=len(token),
                expected_audience=self.audience,
            )

            # Decode header to get kid
            unverified_header = jwt.get_unverified_header(token)
            logger.debug(
                "JWT header decoded",
                alg=unverified_header.get("alg"),
                kid=unverified_header.get("kid"),
                typ=unverified_header.get("typ"),
            )

            # Get public key
            jwk = self._get_public_key(unverified_header)
            if not jwk:
                logger.error(
                    "Failed to find public key for token",
                    kid=unverified_header.get("kid"),
                )
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Unable to find matching public key"
                )

            logger.debug("Public key found for token validation")

            # Decode and validate token
            # Note: For production, use PyJWT's built-in JWK support
            # This is simplified for MVP
            from jwt.algorithms import RSAAlgorithm
            public_key = RSAAlgorithm.from_jwk(jwk)

            claims = jwt.decode(
                token,
                public_key,  # type: ignore[arg-type]
                algorithms=["RS256"],
                audience=self.audience,
                options={"verify_exp": True}
            )

            logger.info(
                "Token validated successfully",
                sub=claims.get("sub"),
                email=claims.get("email"),
                roles=claims.get("roles", []),
                aud=claims.get("aud"),
                exp_timestamp=claims.get("exp"),
            )

            return claims  # type: ignore[no-any-return]

        except jwt.ExpiredSignatureError as e:
            logger.warning("Token has expired", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.InvalidAudienceError as e:
            logger.warning(
                "Invalid token audience",
                expected=self.audience,
                error=str(e),
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid audience. Expected: {self.audience}"
            )
        except jwt.InvalidTokenError as e:
            logger.warning("Invalid token format or signature", error=str(e), exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token: {str(e)}"
            )

    def _check_roles(self, claims: dict[str, Any]) -> None:
        """Check if user has required roles.

        Args:
            claims: JWT claims

        Raises:
            HTTPException: If user lacks required roles
        """
        if not self.required_roles:
            logger.debug("No required roles configured, skipping role check")
            return

        user_roles = claims.get("roles", [])
        logger.debug(
            "Checking user roles",
            user_roles=user_roles,
            required_roles=self.required_roles,
        )

        for required_role in self.required_roles:
            if required_role not in user_roles:
                logger.warning(
                    "User missing required role",
                    required_role=required_role,
                    user_roles=user_roles,
                    sub=claims.get("sub"),
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required role: {required_role}"
                )

        logger.debug("User has all required roles", user_roles=user_roles)

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        """Process request and validate JWT.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response from handler
        """
        logger.debug(
            "Incoming request",
            method=request.method,
            path=request.url.path,
            has_auth_header="Authorization" in request.headers,
        )

        # Skip authentication for public paths
        if request.url.path in self.public_paths:
            logger.debug("Public path, skipping authentication", path=request.url.path)
            return await call_next(request)  # type: ignore[no-any-return]

        # Extract token from Authorization header or cookie
        token = None
        auth_source = None

        # Try Authorization header first
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]  # Remove "Bearer " prefix
            auth_source = "header"
            logger.debug(
                "Bearer token extracted from Authorization header",
                path=request.url.path,
                token_length=len(token),
            )

        # Fall back to cookie if no Authorization header
        if not token:
            # Check for auth_token cookie (httpOnly cookie used by UI)
            cookie_token = request.cookies.get("auth_token")
            if cookie_token:
                token = cookie_token
                auth_source = "cookie"
                logger.debug(
                    "Token extracted from auth_token cookie",
                    path=request.url.path,
                    token_length=len(token),
                )

        # If no token found in either location, return 401
        if not token:
            logger.warning(
                "Missing authentication: no Authorization header or auth_token cookie",
                path=request.url.path,
                method=request.method,
                has_auth_header=auth_header is not None,
                has_auth_cookie="auth_token" in request.cookies,
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing authentication credentials"},
                headers={"WWW-Authenticate": "Bearer"},
            )

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

            logger.info(
                "Request authenticated and authorized",
                path=request.url.path,
                method=request.method,
                user_id=request.state.user_id,
                user_roles=request.state.user_roles,
                auth_source=auth_source,
            )

            # Call next handler
            response = await call_next(request)
            return response  # type: ignore[no-any-return]

        except HTTPException as e:
            logger.warning(
                "Authentication/authorization failed",
                path=request.url.path,
                method=request.method,
                status_code=e.status_code,
                detail=e.detail,
            )
            # Convert HTTPException to JSONResponse
            return JSONResponse(
                status_code=e.status_code,
                content={"detail": e.detail},
                headers=e.headers or {},
            )
        except httpx.HTTPError as e:
            # Network/connection errors to auth service
            logger.error(
                f"Auth service communication error: {type(e).__name__}: {e}",
                extra={"error_type": type(e).__name__, "auth_service_url": self.auth_service_url}
            )
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Authentication service unavailable"}
            )
        except (jwt.DecodeError, ValueError) as e:
            # Token parsing/decoding errors
            logger.warning(
                f"Token parsing error: {type(e).__name__}: {e}",
                extra={"error_type": type(e).__name__}
            )
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Malformed token"}
            )
        except Exception as e:
            # Unexpected errors - log full details for debugging
            logger.error(
                f"Unexpected error during token validation: {type(e).__name__}: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Authentication error"}
            )


def create_jwt_middleware(
    auth_service_url: str | None = None,
    audience: str | None = None,
    required_roles: list[str] | None = None,
    public_paths: list[str] | None = None,
) -> type[JWTMiddleware]:
    """Factory function to create JWT middleware with configuration.

    Args:
        auth_service_url: URL of auth service (default: from AUTH_SERVICE_URL env)
        audience: Expected audience (default: from SERVICE_AUDIENCE env,
            or SERVICE_NAME for backward compatibility, or 'copilot-for-consensus')
        required_roles: Optional list of required roles
        public_paths: List of paths that don't require auth

    Returns:
        Configured JWTMiddleware class

    Example:
        >>> from fastapi import FastAPI
        >>> from copilot_auth import create_jwt_middleware
        >>>
        >>> app = FastAPI()
        >>> middleware = create_jwt_middleware(
        ...     auth_service_url="http://auth:8090",
        ...     audience="orchestrator"
        ... )
        >>> app.add_middleware(middleware)
    """
    # Get defaults from environment - these will always be strings due to defaults
    auth_url = cast(str, auth_service_url or os.getenv("AUTH_SERVICE_URL", "http://auth:8090"))
    aud = cast(str, audience or os.getenv("SERVICE_AUDIENCE", os.getenv("SERVICE_NAME", "copilot-for-consensus")))

    # Create configured middleware class
    class ConfiguredJWTMiddleware(JWTMiddleware):
        def __init__(self, app: Any) -> None:
            super().__init__(
                app=app,
                auth_service_url=auth_url,
                audience=aud,
                required_roles=required_roles,
                public_paths=public_paths,
            )

    return ConfiguredJWTMiddleware
