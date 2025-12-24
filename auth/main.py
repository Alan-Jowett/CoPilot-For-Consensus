# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Authentication Service: OIDC authentication with local JWT token minting.

This service provides:
- OIDC login via multiple providers (GitHub, Google, Microsoft)
- Local JWT token minting with custom claims
- JWT validation and JWKS endpoint
- User info retrieval
"""

import os
import sys
from contextlib import asynccontextmanager
from enum import Enum
from typing import Any

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))


import uvicorn
from app import SUPPORTED_PROVIDERS, __version__
from app.config import load_auth_config
from app.service import AuthService
from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_metrics import create_metrics_collector
from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="auth")

# Configure metrics
metrics = create_metrics_collector(service_name="auth")

# Global service instance
auth_service: AuthService | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage service lifecycle."""
    global auth_service

    # Startup
    logger.info("Starting Authentication Service...")
    config = load_auth_config()
    auth_service = AuthService(config=config)
    logger.info("Authentication Service started successfully")

    yield

    # Shutdown
    logger.info("Shutting down Authentication Service...")


# Create FastAPI app
app = FastAPI(
    title="Authentication Service",
    version=__version__,
    description="OIDC authentication with local JWT token minting",
    lifespan=lifespan,
)


@app.get("/")
async def root() -> dict[str, Any]:
    """Root endpoint redirects to health check."""
    return await health()


@app.get("/health")
async def health() -> dict[str, Any]:
    """Health check endpoint."""
    global auth_service

    stats = auth_service.get_stats() if auth_service is not None else {}

    return {
        "status": "healthy",
        "service": "auth",
        "version": __version__,
        "logins_total": stats.get("logins_total", 0),
        "tokens_minted": stats.get("tokens_minted", 0),
        "tokens_validated": stats.get("tokens_validated", 0),
        "validation_failures": stats.get("validation_failures", 0),
    }


@app.get("/readyz")
async def readyz() -> dict[str, str]:
    """Readiness check endpoint."""
    global auth_service

    if not auth_service or not auth_service.is_ready():
        raise HTTPException(status_code=503, detail="Service not ready")

    return {"status": "ready"}


@app.get("/providers")
async def list_providers() -> dict[str, Any]:
    """List available authentication providers.

    Returns information about which providers are configured and ready to use.

    Returns:
        JSON with list of configured providers and their status

    Example Response:
        {
            "providers": {
                "github": {"configured": true},
                "google": {"configured": false},
                "microsoft": {"configured": false}
            },
            "configured_count": 1,
            "total_supported": 3
        }
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    configured_providers = list(auth_service.providers.keys())

    provider_status = {}
    for provider in SUPPORTED_PROVIDERS:
        provider_status[provider] = {
            "configured": provider in configured_providers,
        }

    return {
        "providers": provider_status,
        "configured_count": len(configured_providers),
        "total_supported": len(SUPPORTED_PROVIDERS),
    }


@app.get("/login")
async def login(
    provider: str = Query(..., description="OIDC provider (github, google, microsoft)"),
    aud: str = Query("copilot-for-consensus", description="Target audience for JWT"),
    prompt: str = Query(None, description="OAuth prompt parameter"),
) -> Response:
    """Initiate OIDC login flow.

    Redirects to the provider's authorization endpoint.

    Args:
        provider: OIDC provider identifier
        aud: Target audience for the JWT token
        prompt: Optional OAuth prompt parameter

    Returns:
        Redirect to provider authorization page
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        authorization_url, state, nonce = await auth_service.initiate_login(
            provider=provider, audience=aud, prompt=prompt
        )

        # Store state and nonce in session (for production, use Redis/cookie)
        # For MVP, we'll pass them as query params to callback

        logger.info(f"Initiated login for provider={provider}, aud={aud}")

        # Record metrics
        metrics.increment("login_initiated_total", {"provider": provider, "audience": aud})

        return RedirectResponse(url=authorization_url, status_code=302)

    except ValueError as e:
        logger.error(f"Login initiation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login initiation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/callback")
async def callback(
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="OAuth state parameter"),
) -> JSONResponse:
    """OIDC callback handler.

    Exchanges authorization code for tokens and returns local JWT.

    The provider and audience are NOT accepted as query parameters - they are
    retrieved from session state using the state parameter to prevent tampering.
    This ensures the callback uses the same provider/audience as the initial
    login request.

    Args:
        code: Authorization code from provider
        state: OAuth state parameter (used to retrieve session with provider/audience)

    Returns:
        JSON with local JWT token

    Raises:
        400: Invalid state or callback parameters
        503: Service not initialized
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Handle callback - provider and audience retrieved from session via state
        local_jwt = await auth_service.handle_callback(
            code=code,
            state=state,
        )

        logger.info(f"Successful callback for state={state[:8]}...")

        # Record metrics
        metrics.increment("callback_success_total", {"audience": auth_service.config.audiences.split(",")[0]})

        return JSONResponse(
            content={
                "access_token": local_jwt,
                "token_type": "Bearer",
                "expires_in": auth_service.config.jwt_default_expiry,
            }
        )

    except ValueError as e:
        logger.error(f"Callback validation failed: {e}")
        metrics.increment("callback_failed_total", {"error": "validation_error"})
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during callback: {e}")
        metrics.increment("callback_failed_total", {"error": "internal_error"})
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/token")
def token_exchange(request: Request) -> JSONResponse:
    """Direct token exchange endpoint.

    Exchanges OIDC ID token for local JWT (server-to-server).

    Request body:
        {
            "provider": "github",
            "grant_type": "urn:copilot-for-consensus:oidc_exchange",
            "id_token": "<oidc-id-token>",
            "aud": "copilot-for-consensus"
        }

    Returns:
        JSON with local JWT token
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # This is a placeholder for server-to-server token exchange
    # In MVP, we focus on interactive login flow
    raise HTTPException(status_code=501, detail="Token exchange not implemented in MVP")


@app.get("/userinfo")
def userinfo(request: Request) -> JSONResponse:
    """Get user information from JWT.

    Requires Bearer token in Authorization header.
    Validates token for any supported audience.

    Returns:
        User information from JWT claims
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Parse audiences from config (comma-separated string)
        configured_audiences = [aud.strip() for aud in auth_service.config.audiences.split(",")]

        # Try to validate against each configured audience
        # The token must match at least one configured audience
        validation_errors = []
        for audience in configured_audiences:
            try:
                claims = auth_service.validate_token(token=token, audience=audience)
                # Successfully validated - return user info
                metrics.increment("userinfo_success_total", {"audience": audience})
                return JSONResponse(
                    content={
                        "sub": claims.get("sub"),
                        "email": claims.get("email"),
                        "name": claims.get("name"),
                        "roles": claims.get("roles", []),
                        "affiliations": claims.get("affiliations", []),
                        "aud": claims.get("aud"),  # Include actual audience from token
                    }
                )
            except Exception as e:
                validation_errors.append(f"{audience}: {str(e)}")
                continue

        # Token didn't match any configured audience
        logger.warning(f"Token validation failed for all configured audiences: {validation_errors}")
        metrics.increment("userinfo_failed_total", {"error": "invalid_audience"})
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token does not match any configured audience"
        )

    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        metrics.increment("userinfo_failed_total", {"error": "token_error"})
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/keys")
def jwks() -> JSONResponse:
    """Get JSON Web Key Set (JWKS) for token validation.

    Returns:
        JWKS with public keys
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    metrics.increment("jwks_requests_total")
    jwks_data = auth_service.get_jwks()
    return JSONResponse(content=jwks_data)


@app.get("/.well-known/jwks.json")
def well_known_jwks() -> JSONResponse:
    """Get JSON Web Key Set (JWKS) at standard OIDC discovery endpoint.

    Standard OIDC endpoint that provides the keys needed to validate
    tokens signed by this auth service.

    Format: https://tools.ietf.org/html/rfc7517

    Returns:
        JWKS with public keys
    """
    return jwks()


@app.get("/.well-known/public_key.pem")
async def get_public_key() -> Response:
    """Expose public key for JWT validation by external services (e.g., Grafana).

    Grafana will fetch this endpoint and use the public key to validate
    JWT tokens before auto-login.

    Returns:
        Public key in PEM format
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    try:
        # Get public key from JWT manager
        public_key_pem = auth_service.jwt_manager.get_public_key_pem()

        if not public_key_pem:
            raise HTTPException(status_code=404, detail="Public key not available")

        metrics.increment("public_key_requests_total")

        # Return as plain text with PEM content type
        return Response(
            content=public_key_pem,
            media_type="application/x-pem-file",
            headers={
                "Content-Disposition": 'attachment; filename="public_key.pem"'
            }
        )
    except Exception as e:
        logger.error(f"Failed to retrieve public key: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve public key")





# Pydantic models for admin API
class SearchByField(str, Enum):
    """Enum for valid search fields."""
    USER_ID = "user_id"
    EMAIL = "email"
    NAME = "name"


class RoleAssignmentRequest(BaseModel):
    """Request model for assigning roles."""

    roles: list[str] = Field(..., description="List of roles to assign", min_length=1)


class RoleRevocationRequest(BaseModel):
    """Request model for revoking roles."""

    roles: list[str] = Field(..., description="List of roles to revoke", min_length=1)


# Helper function to extract and validate admin role
def require_admin_role(request: Request) -> tuple[str, str | None]:
    """Validate that the user has admin role and return user info.

    Args:
        request: FastAPI request object

    Returns:
        Tuple of (user_id, user_email)

    Raises:
        HTTPException: If user lacks admin role or token is invalid
    """
    global auth_service

    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")

    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    logger.info(
        f"Authorization header present: {bool(auth_header)}, "
        f"starts with Bearer: {auth_header.startswith('Bearer ')}"
    )
    if not auth_header.startswith("Bearer "):
        logger.warning("Missing or invalid Authorization header")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing or invalid Authorization header")

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        # Parse audiences from config
        configured_audiences = [aud.strip() for aud in auth_service.config.audiences.split(",")]
        logger.info(f"Configured audiences: {configured_audiences}")

        # Try to validate against each configured audience
        for audience in configured_audiences:
            try:
                claims = auth_service.validate_token(token=token, audience=audience)

                # Check for admin role
                user_roles = claims.get("roles", [])
                if "admin" not in user_roles:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")

                # Return user info
                return claims.get("sub"), claims.get("email")

            except HTTPException:
                raise
            except Exception as e:
                # Log unexpected validation errors for debugging
                logger.warning(
                    f"Token validation failed for audience {audience}: {type(e).__name__}: {e}",
                    extra={"audience": audience, "error_type": type(e).__name__},
                )
                logger.info(f"Token (first 50 chars): {token[:50]}...")
                continue

        # Token didn't match any configured audience
        logger.error(
            f"Token didn't match any configured audience. "
            f"Audiences: {configured_audiences}, Token preview: {token[:50]}..."
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


# Admin endpoints
@app.get("/admin/role-assignments/pending")
async def list_pending_assignments(
    request: Request,
    user_id: str | None = Query(None, description="Filter by user ID"),
    role: str | None = Query(None, description="Filter by role"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results per page"),
    skip: int = Query(0, ge=0, description="Number of results to skip"),
    sort_by: str = Query("requested_at", description="Field to sort by"),
    sort_order: int = Query(-1, ge=-1, le=1, description="Sort order: -1 desc, 1 asc"),
) -> JSONResponse:
    """List pending role assignment requests.

    Requires admin role. Supports filtering by user ID or role, with pagination.

    Args:
        request: FastAPI request
        user_id: Optional filter by user ID
        role: Optional filter by role
        limit: Maximum results to return (1-100, default: 50)
        skip: Number of results to skip for pagination (default: 0)
        sort_by: Field to sort by (default: requested_at)
        sort_order: Sort order: -1 for descending, 1 for ascending (default: -1)

    Returns:
        JSON with pending assignments and pagination info
    """
    global auth_service

    # Validate admin role
    admin_user_id, admin_email = require_admin_role(request)

    try:
        assignments, total = auth_service.role_store.list_pending_role_assignments(
            user_id=user_id,
            role=role,
            limit=limit,
            skip=skip,
            sort_by=sort_by,
            sort_order=sort_order,
        )

        logger.info(
            f"Admin {admin_user_id} listed pending role assignments",
            extra={
                "event": "admin_list_pending",
                "admin_user_id": admin_user_id,
                "filters": {"user_id": user_id, "role": role},
                "result_count": len(assignments),
            },
        )

        metrics.increment("admin_list_pending_total", {"admin": admin_user_id})

        return JSONResponse(
            content={
                "assignments": assignments,
                "total": total,
                "limit": limit,
                "skip": skip,
            }
        )

    except Exception as e:
        logger.error(f"Failed to list pending assignments: {e}")
        raise HTTPException(status_code=500, detail="Failed to list pending assignments")


@app.get("/admin/users/search")
async def search_users(
    request: Request,
    search_term: str = Query(..., description="Search term (email, name, or user ID)"),
    search_by: SearchByField = Query(SearchByField.EMAIL, description="Field to search by: user_id, email, or name"),
) -> JSONResponse:
    """Search for users by email, name, or user_id.

    Requires admin role. Returns matching user records.

    Args:
        request: FastAPI request
        search_term: The search term to look for
        search_by: Field to search by (user_id, email, or name)

    Returns:
        JSON with matching user records
    """
    global auth_service

    # Validate admin role
    admin_user_id, admin_email = require_admin_role(request)

    try:
        users = auth_service.role_store.search_users(
            search_term=search_term,
            search_by=search_by.value,  # Use .value to get the string value from Enum
        )

        # Redact search term from logs to avoid exposing PII (email addresses, names)
        logger.info(
            f"Admin {admin_user_id} searched for users",
            extra={
                "event": "admin_search_users",
                "admin_user_id": admin_user_id,
                "search_by": search_by.value,
                "result_count": len(users),
                # search_term intentionally omitted to protect user privacy
            },
        )

        metrics.increment("admin_search_users_total", {"admin": admin_user_id, "search_by": search_by.value})

        return JSONResponse(
            content={
                "users": users,
                "count": len(users),
                "search_by": search_by.value,
                "search_term": search_term,
            }
        )

    except ValueError as e:
        logger.warning(f"Invalid search request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to search users: {e}")
        raise HTTPException(status_code=500, detail="Failed to search users")


@app.get("/admin/users/{user_id}/roles")
async def get_user_roles(
    user_id: str,
    request: Request,
) -> JSONResponse:
    """Get current roles assigned to a user.

    Requires admin role.

    Args:
        user_id: User identifier
        request: FastAPI request

    Returns:
        JSON with user role information
    """
    global auth_service

    # Validate admin role
    admin_user_id, admin_email = require_admin_role(request)

    try:
        user_record = auth_service.role_store.get_user_roles(user_id)

        if not user_record:
            raise HTTPException(status_code=404, detail=f"User not found: {user_id}")

        logger.info(
            f"Admin {admin_user_id} viewed roles for user {user_id}",
            extra={
                "event": "admin_view_roles",
                "admin_user_id": admin_user_id,
                "target_user_id": user_id,
            },
        )

        metrics.increment("admin_view_roles_total", {"admin": admin_user_id})

        return JSONResponse(content=user_record)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user roles: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user roles")


@app.post("/admin/users/{user_id}/roles")
async def assign_user_roles(
    user_id: str,
    request: Request,
    role_request: RoleAssignmentRequest,
) -> JSONResponse:
    """Assign roles to a user.

    Requires admin role. Updates user status to 'approved' and sets the specified roles.
    Logs the action for audit purposes.

    Args:
        user_id: User identifier
        request: FastAPI request
        role_request: Role assignment request body

    Returns:
        JSON with updated user record
    """
    global auth_service

    # Validate admin role
    admin_user_id, admin_email = require_admin_role(request)

    try:
        updated_record = auth_service.role_store.assign_roles(
            user_id=user_id,
            roles=role_request.roles,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
        )

        logger.info(
            f"Admin {admin_user_id} assigned roles to user {user_id}",
            extra={
                "event": "admin_assign_roles",
                "admin_user_id": admin_user_id,
                "target_user_id": user_id,
                "roles": role_request.roles,
            },
        )

        metrics.increment(
            "admin_assign_roles_total",
            {
                "admin": admin_user_id,
                "roles": ",".join(role_request.roles),
            },
        )

        return JSONResponse(content=updated_record)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to assign roles: {e}")
        raise HTTPException(status_code=500, detail="Failed to assign roles")


@app.delete("/admin/users/{user_id}/roles")
async def revoke_user_roles(
    user_id: str,
    request: Request,
    role_request: RoleRevocationRequest,
) -> JSONResponse:
    """Revoke roles from a user.

    Requires admin role. Removes the specified roles from the user's role list.
    Logs the action for audit purposes.

    Args:
        user_id: User identifier
        request: FastAPI request
        role_request: Role revocation request body

    Returns:
        JSON with updated user record
    """
    global auth_service

    # Validate admin role
    admin_user_id, admin_email = require_admin_role(request)

    try:
        updated_record = auth_service.role_store.revoke_roles(
            user_id=user_id,
            roles=role_request.roles,
            admin_user_id=admin_user_id,
            admin_email=admin_email,
        )

        logger.info(
            f"Admin {admin_user_id} revoked roles from user {user_id}",
            extra={
                "event": "admin_revoke_roles",
                "admin_user_id": admin_user_id,
                "target_user_id": user_id,
                "roles": role_request.roles,
            },
        )

        metrics.increment(
            "admin_revoke_roles_total",
            {
                "admin": admin_user_id,
                "roles": ",".join(role_request.roles),
            },
        )

        return JSONResponse(content=updated_record)

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to revoke roles: {e}")
        raise HTTPException(status_code=500, detail="Failed to revoke roles")


if __name__ == "__main__":
    # Run with uvicorn
    port = int(os.getenv("PORT", "8090"))
    host = os.getenv("HOST", "0.0.0.0")
    log_level = os.getenv("LOG_LEVEL", "INFO")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_config=create_uvicorn_log_config("auth", log_level),
        access_log=True,
    )
