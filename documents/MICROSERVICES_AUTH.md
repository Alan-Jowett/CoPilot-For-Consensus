<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Microservices Authentication Integration

This document describes how authentication and authorization are integrated across all Copilot-for-Consensus microservices.

## Overview

All microservices in the Copilot-for-Consensus system enforce authentication and role-based access control (RBAC) using JWT tokens issued by the centralized Auth service.

## Architecture

```
┌─────────────┐
│  End User   │
└──────┬──────┘
       │ 1. Login via OIDC
       ▼
┌─────────────┐
│Auth Service │◄─── GitHub/Google/Microsoft
└──────┬──────┘
       │ 2. Issue JWT
       ▼
┌─────────────┐
│ User/Client │
└──────┬──────┘
       │ 3. Request with JWT
       ▼
┌─────────────┐
│ Microservice│───► Validate JWT via JWKS
│ (FastAPI)   │     Enforce role requirements
└─────────────┘
```

## Service Integration Status

All microservices have been integrated with JWT authentication:

| Service | Status | Required Role | Public Endpoints |
|---------|--------|---------------|------------------|
| Auth Service | ✅ Issuer | N/A | `/login`, `/callback`, `/keys`, `/health` |
| Reporting API | ✅ Protected | `reader` | `/health`, `/`, `/docs` |
| Orchestrator | ✅ Protected | `orchestrator` | `/health`, `/docs` |
| Chunking | ✅ Protected | `processor` | `/health`, `/docs` |
| Embedding | ✅ Protected | `processor` | `/health`, `/docs` |
| Parsing | ✅ Protected | `processor` | `/health`, `/docs` |
| Summarization | ✅ Protected | `processor` | `/health`, `/docs` |
| Ingestion API | ✅ Protected | `admin` | `/health`, `/`, `/docs` |

## Role Definitions

### Standard Roles

- **`reader`**: Read-only access to reports and summaries (public-facing)
- **`contributor`**: Can submit feedback and participate in discussions
- **`processor`**: Internal service role for processing pipeline services
- **`orchestrator`**: Coordinate workflow and trigger summarization
- **`admin`**: Full administrative access including source management
- **`chair`**: Working group chair privileges

### Role Assignment

Roles are assigned based on:
1. **OIDC Provider Claims**: GitHub organizations, Google groups, Microsoft group memberships
2. **Manual Assignment**: Via role management API (future enhancement)
3. **Default Role**: New users receive `reader` role by default

## Authentication Flow

### 1. User Login

```bash
# User initiates login
curl -i "http://localhost:8090/login?provider=github&aud=copilot-reporting"

# User is redirected to provider (GitHub/Google/Microsoft)
# After authorization, callback returns JWT
```

### 2. API Request with JWT

```bash
# Request with JWT in Authorization header
curl -H "Authorization: Bearer <jwt-token>" \
     http://localhost:8080/api/reports
```

### 3. Token Validation

The middleware:
1. Extracts JWT from `Authorization: Bearer <token>` header
2. Fetches JWKS from auth service (`http://auth:8090/keys`)
3. Validates JWT signature using public key
4. Checks token expiration (`exp` claim)
5. Validates audience (`aud` claim matches service name)
6. Enforces role requirements (`roles` claim)
7. Adds claims to `request.state` for handlers

## Implementation Details

### Middleware Integration

Each service uses the `copilot_auth` adapter:

```python
from fastapi import FastAPI
from copilot_auth import create_jwt_middleware

app = FastAPI(title="Service Name")

# Add JWT middleware
auth_middleware = create_jwt_middleware(
    auth_service_url="http://auth:8090",  # Defaults to AUTH_SERVICE_URL env var
    audience="service-name",               # Defaults to SERVICE_NAME env var
    required_roles=["reader"],             # Optional: enforce role requirements
    public_paths=["/health", "/docs"],     # Optional: public endpoints
)
app.add_middleware(auth_middleware)
```

### Environment Configuration

```yaml
# docker-compose.services.yml
services:
  my-service:
    environment:
      - AUTH_SERVICE_URL=http://auth:8090
      - SERVICE_NAME=copilot-my-service
    volumes:
      - ./adapters/copilot_auth:/app/adapters/copilot_auth:ro
    depends_on:
      auth:
        condition: service_healthy
```

### Request State

After successful authentication, the middleware adds user information to `request.state`:

```python
from fastapi import Request

@app.get("/api/data")
async def get_data(request: Request):
    # Access user information
    user_id = request.state.user_id          # Subject (sub claim)
    user_email = request.state.user_email    # Email claim
    user_roles = request.state.user_roles    # Roles claim (list)
    user_claims = request.state.user_claims  # Full JWT claims dict
    
    # Use for authorization or auditing
    logger.info(f"User {user_email} accessed data", user_id=user_id)
    return {"data": "..."}
```

## Error Responses

### 401 Unauthorized

Missing or invalid token:

```json
{
  "detail": "Missing or invalid Authorization header"
}
```

Expired token:

```json
{
  "detail": "Token has expired"
}
```

Invalid signature:

```json
{
  "detail": "Invalid token: Signature verification failed"
}
```

### 403 Forbidden

Missing required role:

```json
{
  "detail": "Missing required role: admin"
}
```

Wrong audience:

```json
{
  "detail": "Invalid audience. Expected: copilot-reporting"
}
```

### 503 Service Unavailable

Auth service unreachable:

```json
{
  "detail": "Authentication service unavailable"
}
```

## Testing

### Unit Tests

Each service includes auth integration tests:

```bash
# Run auth tests for reporting service
cd reporting
pytest tests/test_auth_integration.py -v

# Run auth tests for orchestrator
cd orchestrator
pytest tests/test_auth_integration.py -v
```

### Integration Testing

```bash
# Start all services including auth
docker compose up -d

# Get a token (requires OIDC provider setup)
TOKEN=$(curl -s "http://localhost:8090/login?provider=github&aud=copilot-reporting" \
  | jq -r '.access_token')

# Test protected endpoint
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8080/api/reports

# Should return 200 with data
```

### Manual Testing

For local development without OIDC providers:

```bash
# Generate test keys (if not exist)
cd auth
python generate_keys.py

# Start auth service in dev mode
AUTH_ISSUER=http://localhost:8090 \
AUTH_AUDIENCES=copilot-reporting,copilot-orchestrator \
JWT_ALGORITHM=RS256 \
JWT_PRIVATE_KEY_PATH=config/dev_jwt_private.pem \
JWT_PUBLIC_KEY_PATH=config/dev_jwt_public.pem \
python main.py
```

## Security Considerations

### Token Lifetime

- Default JWT expiry: 30 minutes (configurable via `JWT_DEFAULT_EXPIRY`)
- Refresh tokens: Not yet implemented (future enhancement)
- Short-lived tokens minimize risk of token theft

### HTTPS Requirements

- **Production**: All auth endpoints MUST use HTTPS
- **Development**: HTTP acceptable for localhost only
- Token transmission over HTTP is a security risk

### Secret Management

- JWT private keys stored in Docker secrets
- Never commit keys to version control
- Rotate keys periodically (manual process currently)

### CORS Policy

- Auth service configured for same-origin by default
- Cross-origin requests require explicit CORS configuration
- Reporting API (public-facing) has permissive CORS for UI

## Troubleshooting

### "Unable to find matching public key"

**Cause**: JWKS cache stale or key rotation occurred

**Solution**: Middleware auto-refreshes JWKS; retry request after 1 second

### "Invalid audience"

**Cause**: Token issued for different service

**Solution**: Request token with correct `aud` parameter:
```bash
curl "http://localhost:8090/login?provider=github&aud=copilot-reporting"
```

### "Missing required role"

**Cause**: User lacks necessary role

**Solution**: 
1. Check user's roles: `curl -H "Authorization: Bearer $TOKEN" http://localhost:8090/userinfo`
2. Assign role via role management (future feature)
3. Use service account with appropriate roles

## Future Enhancements

- [ ] Service-to-service authentication (client credentials flow)
- [ ] Refresh token support
- [ ] Token revocation list
- [ ] Role management UI
- [ ] Automatic key rotation
- [ ] DPoP proof-of-possession
- [ ] Multi-factor authentication
- [ ] Audit logging for all auth events

## Related Documentation

- [Auth Service README](../auth/README.md)
- [Auth Adapter README](../adapters/copilot_auth/README.md)
- [Auth Integration Examples](./AUTH_INTEGRATION_EXAMPLES.md)
- [OIDC Local Testing](./OIDC_LOCAL_TESTING.md)
