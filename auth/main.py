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
from pathlib import Path

# Add app directory to path
sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
import uvicorn

from copilot_logging import create_logger, create_uvicorn_log_config
from copilot_metrics import create_metrics_collector

from app import __version__
from app.service import AuthService
from app.config import AuthConfig

# Configure structured JSON logging
logger = create_logger(logger_type="stdout", level="INFO", name="auth")

# Create FastAPI app
app = FastAPI(
    title="Authentication Service",
    version=__version__,
    description="OIDC authentication with local JWT token minting"
)

# Global service instance
auth_service: AuthService | None = None


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint redirects to health check."""
    return health()


@app.get("/health")
def health() -> dict[str, any]:
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
def readyz() -> dict[str, str]:
    """Readiness check endpoint."""
    global auth_service
    
    if not auth_service or not auth_service.is_ready():
        raise HTTPException(status_code=503, detail="Service not ready")
    
    return {"status": "ready"}


@app.get("/login")
def login(
    provider: str = Query(..., description="OIDC provider (github, google, microsoft)"),
    aud: str = Query("copilot-orchestrator", description="Target audience for JWT"),
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
        authorization_url, state, nonce = auth_service.initiate_login(
            provider=provider,
            audience=aud,
            prompt=prompt
        )
        
        # Store state and nonce in session (for production, use Redis/cookie)
        # For MVP, we'll pass them as query params to callback
        
        logger.info(f"Initiated login for provider={provider}, aud={aud}")
        
        return RedirectResponse(url=authorization_url, status_code=302)
    
    except ValueError as e:
        logger.error(f"Login initiation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during login initiation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/callback")
def callback(
    code: str = Query(..., description="Authorization code from provider"),
    state: str = Query(..., description="OAuth state parameter"),
) -> JSONResponse:
    """OIDC callback handler.
    
    Exchanges authorization code for tokens and returns local JWT.
    Provider and audience are retrieved from session state to prevent tampering.
    
    Args:
        code: Authorization code from provider
        state: OAuth state parameter
    
    Returns:
        JSON with local JWT token
    """
    global auth_service
    
    if not auth_service:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Handle callback - provider and audience are validated from session state
        local_jwt = auth_service.handle_callback(
            code=code,
            state=state,
        )
        
        logger.info(f"Successful callback for state={state[:8]}...")
        
        return JSONResponse(content={
            "access_token": local_jwt,
            "token_type": "Bearer",
            "expires_in": auth_service.config.jwt.default_expiry
        })
    
    except ValueError as e:
        logger.error(f"Callback validation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during callback: {e}")
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
            "aud": "copilot-orchestrator"
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
        # Decode token without validating audience to extract it first
        import jwt
        unverified_claims = jwt.decode(token, options={"verify_signature": False})
        audience = unverified_claims.get("aud")
        
        if not audience:
            raise HTTPException(status_code=401, detail="Token missing audience claim")
        
        # Now validate token with correct audience
        claims = auth_service.validate_token(
            token=token,
            audience=audience
        )
        
        return JSONResponse(content={
            "sub": claims.get("sub"),
            "email": claims.get("email"),
            "name": claims.get("name"),
            "roles": claims.get("roles", []),
            "affiliations": claims.get("affiliations", []),
        })
    
    except Exception as e:
        logger.error(f"Token validation failed: {e}")
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
    
    jwks_data = auth_service.get_jwks()
    return JSONResponse(content=jwks_data)


@app.on_event("startup")
def startup() -> None:
    """Initialize the auth service on startup."""
    global auth_service
    
    logger.info("Starting Authentication Service...")
    
    # Load configuration
    config = AuthConfig.from_env()
    
    # Initialize auth service
    auth_service = AuthService(config=config)
    
    logger.info("Authentication Service started successfully")


@app.on_event("shutdown")
def shutdown() -> None:
    """Cleanup on shutdown."""
    logger.info("Shutting down Authentication Service...")


if __name__ == "__main__":
    # Run with uvicorn
    port = int(os.getenv("PORT", "8090"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        log_config=create_uvicorn_log_config(),
        access_log=True,
    )
