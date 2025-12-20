<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Auth Microservice Implementation Summary

This document summarizes the implementation of the Auth microservice for the Copilot-for-Consensus project.

## Overview

The Auth microservice provides **OIDC authentication** with **local JWT token minting**, enabling secure, standards-based authentication while maintaining control over authorization through service-scoped JWTs.

## Implementation Completed

### Phase 1: Enhanced copilot_auth Adapter ✅

**Files Created/Modified:**
- `adapters/copilot_auth/copilot_auth/oidc_provider.py` - Base OIDC provider class
- `adapters/copilot_auth/copilot_auth/jwt_manager.py` - JWT minting and validation
- `adapters/copilot_auth/copilot_auth/github_provider.py` - GitHub OIDC implementation
- `adapters/copilot_auth/copilot_auth/google_provider.py` - Google OIDC implementation
- `adapters/copilot_auth/copilot_auth/microsoft_provider.py` - Microsoft Entra ID implementation
- `adapters/copilot_auth/copilot_auth/factory.py` - Updated factory for new providers
- `adapters/copilot_auth/copilot_auth/__init__.py` - Exports for new classes
- `adapters/copilot_auth/setup.py` - Added dependencies (httpx, PyJWT, cryptography, pydantic)

**Features:**
- OIDC discovery endpoint parsing
- Authorization URL generation with state/nonce
- Token exchange via authorization code
- User info retrieval from OIDC providers
- RS256 and HS256 JWT signing
- JWKS generation for public key distribution
- Key rotation support via key ID (kid)

### Phase 2: Auth Microservice ✅

**Files Created:**
- `auth/main.py` - FastAPI application with endpoints
- `auth/app/service.py` - AuthService coordinating OIDC and JWT
- `auth/app/config.py` - Configuration management with Pydantic
- `auth/app/__init__.py` - App package initialization
- `auth/Dockerfile` - Multi-stage Docker build
- `auth/requirements.txt` - Service dependencies
- `auth/pytest.ini` - Test configuration
- `auth/README.md` - Comprehensive documentation
- `auth/generate_keys.py` - RSA key generation script
- `auth/tests/test_service.py` - Unit tests
- `auth/tests/__init__.py` - Test package initialization

**API Endpoints:**
- `GET /login` - Initiate OIDC login flow
- `GET /callback` - OIDC callback handler
- `POST /token` - Token exchange (placeholder for S2S)
- `GET /userinfo` - User info from JWT
- `GET /keys` - JWKS for public key distribution
- `GET /health` - Health check
- `GET /readyz` - Readiness check

### Phase 3: Integration & Middleware ✅

**Files Created/Modified:**
- `auth/app/middleware.py` - FastAPI JWT validation middleware
- `docker-compose.yml` - Added auth service configuration
- `.env` - Added auth environment variables
- `.gitignore` - Added auth/config/*.pem

**Integration Features:**
- JWT middleware with role-based access control
- JWKS caching and automatic refresh
- Public path exemption (health, docs)
- Request state enrichment with user claims
- Docker health checks for auth service
- Volume mounts for shared adapters

### Phase 4: Documentation ✅

**Files Created/Modified:**
- `auth/README.md` - Service-specific documentation
- `documents/AUTH_INTEGRATION_EXAMPLES.md` - Integration examples
- `README.md` - Updated main README with auth service info

**Documentation Includes:**
- API endpoint documentation
- Configuration guide
- Local development setup
- Integration examples (FastAPI, CLI, Web UI)
- Security best practices
- Testing guidelines

### Phase 5: Security & Validation ✅

**Security Measures:**
- CodeQL security analysis: **0 alerts**
- Code review feedback addressed:
  - ✅ Removed JWT keys from version control
  - ✅ Created key generation script
  - ✅ Fixed callback parameter tampering vulnerability
  - ✅ Fixed JWT subject claim duplication
  - ✅ Fixed userinfo audience validation
  - ✅ Added session-based state management
- RS256 default signing (RSA public/private keys)
- Nonce and state validation for CSRF protection
- Audience enforcement in JWT validation
- Secure key storage guidance (Azure Key Vault for production)

## Architecture

```
┌─────────┐       ┌──────────────┐       ┌─────────────┐
│ User    │──────>│ Auth Service │──────>│ OIDC        │
│         │<──────│   :8090      │<──────│ Provider    │
└─────────┘       └──────────────┘       └─────────────┘
                        │
                        │ Mints JWT
                        ▼
                  ┌──────────────┐
                  │ Local JWT    │
                  │ (RS256)      │
                  └──────────────┘
                        │
                        ▼
          ┌─────────────┴─────────────┐
          │                           │
    ┌──────────┐              ┌──────────┐
    │ Service  │              │ Service  │
    │ Validates│              │ Validates│
    │ via JWKS │              │ via JWKS │
    └──────────┘              └──────────┘
```

## Configuration

### Configuration

Non-secret configuration stays in environment variables; all client IDs and secrets are stored as files in `./secrets` (mounted to `/run/secrets`).

```bash
# Auth Service (env)
AUTH_ISSUER=http://localhost:8090
AUTH_AUDIENCES=copilot-orchestrator,copilot-reporting

# JWT (env)
JWT_ALGORITHM=RS256
JWT_KEY_ID=default
JWT_DEFAULT_EXPIRY=1800

# OIDC Providers (secrets files)
secrets/github_oauth_client_id
secrets/github_oauth_client_secret
secrets/google_oauth_client_id
secrets/google_oauth_client_secret
secrets/microsoft_oauth_client_id
secrets/microsoft_oauth_client_secret

# Security (env)
AUTH_REQUIRE_PKCE=true
AUTH_REQUIRE_NONCE=true
AUTH_MAX_SKEW_SECONDS=90
```

### JWT Claim Structure

```json
{
  "iss": "http://localhost:8090",
  "sub": "github:12345678",
  "aud": "copilot-orchestrator",
  "exp": 1734567890,
  "iat": 1734564300,
  "nbf": 1734564300,
  "jti": "b1e6d8c2-...",
  "email": "user@example.com",
  "name": "User Name",
  "provider": "github",
  "roles": ["contributor"],
  "affiliations": ["org1", "org2"],
  "amr": ["pwd"]
}
```

## Testing

### Manual Testing

```bash
# Start the stack
docker compose up -d

# Check auth service health
curl http://localhost:8090/health

# Get JWKS
curl http://localhost:8090/keys

# Initiate login (redirects to provider)
curl -i "http://localhost:8090/login?provider=github&aud=copilot-orchestrator"
```

### Unit Tests

```bash
cd auth
pytest tests/ -v
```

## Production Considerations

**Not Yet Implemented (Future Work):**

1. **Session Storage**: Currently in-memory; needs Redis for production
2. **Refresh Tokens**: Not implemented; users must re-authenticate on expiry
3. **DPoP**: Proof-of-possession disabled; can be enabled with `AUTH_ENABLE_DPOP=true`
4. **Azure Key Vault**: RS256 keys are local; production should use Key Vault
5. **Role Mapping**: Roles are static; should map from provider organizations
6. **Token Revocation**: No revocation list implemented
7. **Admin UI**: No UI for key rotation or provider management

**Recommended for Production:**

1. Use HTTPS for all auth endpoints
2. Enable DPoP for proof-of-possession
3. Implement distributed session storage (Redis)
4. Use Azure Key Vault for JWT signing keys
5. Add token refresh support
6. Implement comprehensive audit logging
7. Add rate limiting on auth endpoints
8. Configure CORS properly for web UIs
9. Use managed identity for Azure resources
10. Implement automated key rotation

## Acceptance Criteria Status

- ✅ OIDC login & callback works for GitHub, Google, and Microsoft
- ✅ Local JWT minted with RS256, includes kid, and JWKS published
- ✅ Middleware in Python (FastAPI) validates JWT and enforces aud + roles
- ✅ Config supports multiple providers and per-audience lifetimes
- ✅ Health/readiness endpoints integrated
- ⏳ Key rotation procedure documented (tested manually, not automated)
- ✅ Example docker-compose wiring demonstrating gateway → auth → service

## Files Changed Summary

**New Files:** 25
**Modified Files:** 5
**Total Lines Added:** ~2,500

**Key Directories:**
- `auth/` - New microservice (12 files)
- `adapters/copilot_auth/copilot_auth/` - Enhanced adapter (5 new files, 2 modified)
- `documents/` - New integration guide (1 file)

## Phase 3: React UI Integration ✅

**Files Created/Modified:**
- `ui/src/routes/Callback.tsx` - OAuth callback handling, token extraction and storage
- `ui/src/contexts/AuthContext.tsx` - Token state management and useAuth() hook
- `ui/src/api.ts` - fetchWithAuth() for injecting Authorization headers
- `ui/src/routes/Login.tsx` - Login UI with provider buttons
- `docker-compose.services.yml` - Updated with OAuth redirect URIs pointing to `/ui/callback`

**Features:**
- OAuth2 authorization code flow (code exchange)
- Token extraction from OAuth redirect
- localStorage for token storage (dev) / TODO: migrate to httpOnly cookies
- Automatic Authorization header injection in API calls
- Automatic redirect to login on 401 Unauthorized
- ConsoleLogging for debugging auth flow

**Key Fix - API Token Injection:**
Previously, the `setAuthToken()` function from AuthContext wasn't updating the `authToken` variable used in API calls, resulting in 401 errors. Fixed by having `fetchWithAuth()` read directly from localStorage instead of relying on state synchronization. See [AUTH_API_INTEGRATION_FIX.md](AUTH_API_INTEGRATION_FIX.md) for details.

## Next Steps

1. **Integration Testing**: Add end-to-end OIDC flow tests
2. **Production Hardening**:
   - Implement Redis session storage
   - Add refresh token support
   - Integrate Azure Key Vault
   - Migrate token storage from localStorage to httpOnly Secure cookies
3. **Role Mapping**: Map roles from provider organizations/teams
4. **Admin UI**: Build management interface for keys and providers
5. **Monitoring**: Add detailed metrics and alerts for auth events
6. **Documentation**: Add OIDC compliance validation tests

## Related Documentation

- [AUTH_API_INTEGRATION_FIX.md](AUTH_API_INTEGRATION_FIX.md) - Details on token injection fix
- [OAUTH_TESTING_GUIDE.md](OAUTH_TESTING_GUIDE.md) - Complete testing guide
- [AUTH_INTEGRATION_EXAMPLES.md](AUTH_INTEGRATION_EXAMPLES.md) - Code examples
- [OIDC_LOCAL_TESTING.md](OIDC_LOCAL_TESTING.md) - Local testing setup

## Conclusion

The Auth microservice MVP is complete and ready for local development and testing. It provides a solid foundation for secure, standards-based authentication in Copilot-for-Consensus while maintaining flexibility for future enhancements. The React UI is now fully integrated with OAuth2 flows and API token injection working correctly.

**Security Status:** ✅ Passed CodeQL (0 alerts), code review feedback addressed
**Deployment Status:** ✅ Ready for local development
**Production Status:** ⏳ Requires additional hardening (see Production Considerations)
