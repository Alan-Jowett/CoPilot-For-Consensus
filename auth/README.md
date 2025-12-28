<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Authentication Service

A dedicated microservice for **OIDC authentication** with **local JWT token minting**. This service authenticates end-users via OIDC providers (GitHub, Google, Microsoft) and issues locally signed JWTs for authorization across Copilot-for-Consensus services.

## Features

- **OIDC Support**: Login via GitHub, Google, and Microsoft Entra ID
- **Local JWT Minting**: Issue service-scoped JWTs with custom claims and controlled expiry
- **Token Validation**: Validate JWTs with audience and issuer checks
- **JWKS Endpoint**: Publish public keys for distributed token validation
- **Multi-Provider**: Support multiple OIDC providers with per-provider configuration
- **Security**: RS256 signing, nonce/state validation, CSRF protection

## Architecture

```
┌─────────┐       ┌──────────────┐       ┌─────────────┐
│ User    │──────>│ Auth Service │──────>│ OIDC        │
│         │<──────│              │<──────│ Provider    │
└─────────┘       └──────────────┘       │ (GitHub/    │
                        │                 │  Google/    │
                        │                 │  Microsoft) │
                        ▼                 └─────────────┘
                  ┌──────────────┐
                  │ Local JWT    │
                  │ (RS256)      │
                  └──────────────┘
                        │
                        ▼
                  ┌──────────────┐
                  │ Services     │
                  │ (Validate    │
                  │  via JWKS)   │
                  └──────────────┘
```

## API Endpoints

### `GET /login`

Initiate OIDC login flow.

**Query Parameters:**
- `provider` (required): OIDC provider (`github`, `google`, `microsoft`)
- `aud` (optional): Target audience for JWT (default: `copilot-orchestrator`)
- `prompt` (optional): OAuth prompt parameter

**Response:**
- `302 Redirect` to provider authorization page

**Example:**
```bash
curl -i "http://localhost:8090/login?provider=github&aud=copilot-orchestrator"
```

### `GET /callback`

OIDC callback handler (called by provider after user authorization).

**Query Parameters:**
- `code` (required): Authorization code from provider
- `state` (required): OAuth state parameter
- `provider` (required): Provider identifier
- `aud` (optional): Target audience

**Response:**
```json
{
  "access_token": "<local-jwt>",
  "token_type": "Bearer",
  "expires_in": 1800
}
```

### `POST /token`

Direct token exchange (server-to-server).

**Status:** Not implemented in MVP (placeholder)

### `GET /userinfo`

Get user information from JWT.

**Headers:**
- `Authorization: Bearer <jwt>`

**Response:**
```json
{
  "sub": "github:12345",
  "email": "user@example.com",
  "name": "User Name",
  "roles": ["contributor"],
  "affiliations": ["org1", "org2"]
}
```

### `GET /keys`

Get JSON Web Key Set (JWKS) for token validation.

**Response:**
```json
{
  "keys": [
    {
      "kty": "RSA",
      "use": "sig",
      "kid": "default",
      "alg": "RS256",
      "n": "<modulus>",
      "e": "<exponent>"
    }
  ]
}
```

### `GET /health`

Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "service": "auth",
  "version": "0.1.0",
  "logins_total": 42,
  "tokens_minted": 42,
  "tokens_validated": 100,
  "validation_failures": 0
}
```

### `GET /readyz`

Readiness check endpoint.

**Response:**
```json
{
  "status": "ready"
}
```

### `GET /providers`

List available authentication providers and their configuration status.

Returns information about which OAuth providers (GitHub, Google, Microsoft) are currently configured and available for authentication.

**Response:**
```json
{
  "providers": {
    "github": {
      "configured": true
    },
    "google": {
      "configured": false
    },
    "microsoft": {
      "configured": false
    }
  },
  "configured_count": 1,
  "total_supported": 3
}
```

**Example:**
```bash
# Via API Gateway (recommended for typical deployments)
curl http://localhost:8080/auth/providers

# Direct access (for development/debugging)
curl http://localhost:8090/providers
```

**Use Case:**
This endpoint is useful for:
- Verifying which providers are configured during setup
- Debugging authentication issues
- UI applications to show only available login buttons

### Admin Endpoints

The following endpoints require authentication with an `admin` role. All require the `Authorization: Bearer <jwt>` header with a valid JWT containing the `admin` role.

**Note on URLs:** Examples use `http://localhost:8090` for local development. When accessing from within the Docker Compose network, use `http://auth:8090` instead (where `auth` is the service name).

#### `GET /admin/role-assignments/pending`

List pending role assignment requests with filtering and pagination.

**Headers:**
- `Authorization: Bearer <jwt>` (required, must have `admin` role)

**Query Parameters:**
- `user_id` (optional): Filter by user ID
- `role` (optional): Filter by role
- `limit` (optional, default: 50): Maximum results per page (1-100)
- `skip` (optional, default: 0): Number of results to skip for pagination
- `sort_by` (optional, default: requested_at): Field to sort by
- `sort_order` (optional, default: -1): Sort order (-1 for descending, 1 for ascending)

**Response:**
```json
{
  "assignments": [
    {
      "user_id": "github:123",
      "email": "user@example.com",
      "name": "User Name",
      "provider": "github",
      "roles": [],
      "status": "pending",
      "requested_at": "2025-01-01T00:00:00Z",
      "updated_at": "2025-01-01T00:00:00Z"
    }
  ],
  "total": 10,
  "limit": 50,
  "skip": 0
}
```

**Example:**
```bash
# List all pending assignments
curl -H "Authorization: Bearer <admin-jwt>" \
  "http://localhost:8090/admin/role-assignments/pending"

# Filter by user ID
curl -H "Authorization: Bearer <admin-jwt>" \
  "http://localhost:8090/admin/role-assignments/pending?user_id=github:123"

# Paginate results
curl -H "Authorization: Bearer <admin-jwt>" \
  "http://localhost:8090/admin/role-assignments/pending?limit=10&skip=20"
```

#### `GET /admin/users/{user_id}/roles`

Get current roles assigned to a specific user.

**Headers:**
- `Authorization: Bearer <jwt>` (required, must have `admin` role)

**Path Parameters:**
- `user_id`: User identifier (e.g., `github:123`)

**Response:**
```json
{
  "user_id": "github:123",
  "email": "user@example.com",
  "name": "User Name",
  "provider": "github",
  "roles": ["contributor", "reviewer"],
  "status": "approved",
  "requested_at": "2025-01-01T00:00:00Z",
  "updated_at": "2025-01-02T00:00:00Z",
  "approved_by": "github:admin",
  "approved_at": "2025-01-02T00:00:00Z"
}
```

**Example:**
```bash
curl -H "Authorization: Bearer <admin-jwt>" \
  "http://localhost:8090/admin/users/github:123/roles"
```

#### `POST /admin/users/{user_id}/roles`

Assign roles to a user. Updates status to 'approved' and sets the specified roles.

**Headers:**
- `Authorization: Bearer <jwt>` (required, must have `admin` role)
- `Content-Type: application/json`

**Path Parameters:**
- `user_id`: User identifier (e.g., `github:123`)

**Request Body:**
```json
{
  "roles": ["contributor", "reviewer"]
}
```

**Response:**
```json
{
  "user_id": "github:123",
  "email": "user@example.com",
  "name": "User Name",
  "provider": "github",
  "roles": ["contributor", "reviewer"],
  "status": "approved",
  "updated_at": "2025-01-02T12:00:00Z",
  "approved_by": "github:admin",
  "approved_at": "2025-01-02T12:00:00Z"
}
```

**Example:**
```bash
curl -X POST \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["contributor", "reviewer"]}' \
  "http://localhost:8090/admin/users/github:123/roles"
```

**Audit Logging:** All role assignments are logged with admin user information and timestamp.

#### `DELETE /admin/users/{user_id}/roles`

Revoke roles from a user. Removes the specified roles from the user's role list.

**Headers:**
- `Authorization: Bearer <jwt>` (required, must have `admin` role)
- `Content-Type: application/json`

**Path Parameters:**
- `user_id`: User identifier (e.g., `github:123`)

**Request Body:**
```json
{
  "roles": ["reviewer"]
}
```

**Response:**
```json
{
  "user_id": "github:123",
  "email": "user@example.com",
  "name": "User Name",
  "provider": "github",
  "roles": ["contributor"],
  "status": "approved",
  "updated_at": "2025-01-02T13:00:00Z",
  "last_modified_by": "github:admin"
}
```

**Example:**
```bash
curl -X DELETE \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["reviewer"]}' \
  "http://localhost:8090/admin/users/github:123/roles"
```

**Audit Logging:** All role revocations are logged with admin user information and timestamp.

### Admin Workflows

**Approving a Pending User:**

1. List pending assignments:
   ```bash
   curl -H "Authorization: Bearer <admin-jwt>" \
     "http://localhost:8090/admin/role-assignments/pending"
   ```

2. Review the user's information and assign appropriate roles:
   ```bash
   curl -X POST \
     -H "Authorization: Bearer <admin-jwt>" \
     -H "Content-Type: application/json" \
     -d '{"roles": ["contributor"]}' \
     "http://localhost:8090/admin/users/github:123/roles"
   ```

**Modifying User Roles:**

1. Check current roles:
   ```bash
   curl -H "Authorization: Bearer <admin-jwt>" \
     "http://localhost:8090/admin/users/github:123/roles"
   ```

2. Add additional roles:
   ```bash
   curl -X POST \
     -H "Authorization: Bearer <admin-jwt>" \
     -H "Content-Type: application/json" \
     -d '{"roles": ["contributor", "reviewer", "admin"]}' \
     "http://localhost:8090/admin/users/github:123/roles"
   ```

3. Or remove specific roles:
   ```bash
   curl -X DELETE \
     -H "Authorization: Bearer <admin-jwt>" \
     -H "Content-Type: application/json" \
     -d '{"roles": ["admin"]}' \
     "http://localhost:8090/admin/users/github:123/roles"
   ```

## Configuration

Configuration is provided via environment variables and secrets (mounted at `/run/secrets`).

### JWT Configuration

- `AUTH_ISSUER`: JWT issuer URL (default: `http://localhost:8090`)
- `AUTH_AUDIENCES`: Comma-separated list of allowed audiences (default: `copilot-orchestrator`)
- `JWT_ALGORITHM`: Signing algorithm `RS256` or `HS256` (default: `RS256`)
- `JWT_KEY_ID`: Key ID for rotation (default: `default`)
- `JWT_DEFAULT_EXPIRY`: Token lifetime in seconds (default: `1800` = 30 minutes)
- `JWT_PRIVATE_KEY_PATH`: Path to RSA private key (required for RS256)
- `JWT_PUBLIC_KEY_PATH`: Path to RSA public key (required for RS256)
- `JWT_SECRET_KEY`: HMAC secret (required for HS256)

### OIDC Provider Configuration

**GitHub:**
- `github_oauth_client_id`: GitHub OAuth client ID (secret file `secrets/github_oauth_client_id`)
- `github_oauth_client_secret`: GitHub OAuth client secret (secret file `secrets/github_oauth_client_secret`)
- `AUTH_GITHUB_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)
- `AUTH_GITHUB_API_BASE_URL`: GitHub API base URL (default: `https://api.github.com`)

**Google:**
- `google_oauth_client_id`: Google OAuth client ID (secret file `secrets/google_oauth_client_id`)
- `google_oauth_client_secret`: Google OAuth client secret (secret file `secrets/google_oauth_client_secret`)
- `AUTH_GOOGLE_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)

**Microsoft:**
- `microsoft_oauth_client_id`: Microsoft OAuth client ID (secret file `secrets/microsoft_oauth_client_id`)
- `microsoft_oauth_client_secret`: Microsoft OAuth client secret (secret file `secrets/microsoft_oauth_client_secret`)
- `AUTH_MS_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)
- `AUTH_MS_TENANT`: Azure AD tenant ID (default: `common`)

### Security Configuration

- `AUTH_REQUIRE_PKCE`: Require PKCE for OAuth (default: `true`)
- `AUTH_REQUIRE_NONCE`: Require nonce for OIDC (default: `true`)
- `AUTH_MAX_SKEW_SECONDS`: Maximum clock skew tolerance (default: `90`)
- `AUTH_ENABLE_DPOP`: Enable DPoP proof-of-possession (default: `false`)
- `AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED`: Enable auto-promotion of first user to admin (default: `false`, **recommended for production**)

## Local Development

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (optional)

### Setup

1. **Install dependencies:**
   ```bash
   cd auth
   pip install -r requirements.txt
   pip install -e ../adapters/copilot_auth
   pip install -e ../adapters/copilot_logging
   pip install -e ../adapters/copilot_metrics
   ```

2. **Generate JWT keys** (required for first-time setup):
   ```bash
   cd auth
   python generate_keys.py
   # This creates config/dev_jwt_private.pem and config/dev_jwt_public.pem
   ```

3. **Set configuration (env for non-secrets, files for secrets):**
   ```bash
   export AUTH_ISSUER="http://localhost:8090"
   export AUTH_AUDIENCES="copilot-orchestrator,copilot-reporting"
   export JWT_ALGORITHM="RS256"
   export JWT_PRIVATE_KEY_PATH="config/dev_jwt_private.pem"
   export JWT_PUBLIC_KEY_PATH="config/dev_jwt_public.pem"

   # Configure at least one provider (example: GitHub)
  echo "your_github_client_id" > secrets/github_oauth_client_id
  echo "your_github_client_secret" > secrets/github_oauth_client_secret
   ```

4. **Run the service:**
   ```bash
   python main.py
   ```

5. **Test endpoints:**
   ```bash
   # Health check
   curl http://localhost:8090/health

   # JWKS
   curl http://localhost:8090/keys

   # Initiate login (will redirect)
   curl -i "http://localhost:8090/login?provider=github"
   ```

### Docker

Build and run with Docker:

```bash
docker build -t copilot-auth:latest .
docker run -p 8090:8090 \
  -e AUTH_ISSUER="http://localhost:8090" \
  -e JWT_ALGORITHM="RS256" \
  -e JWT_PRIVATE_KEY_PATH="/app/config/dev_jwt_private.pem" \
  -e JWT_PUBLIC_KEY_PATH="/app/config/dev_jwt_public.pem" \
  copilot-auth:latest
```

## JWT Claim Structure

Example JWT claims:

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

Run tests:

```bash
pytest tests/ -v
```

## Security Considerations

- **RS256 Recommended**: Use RS256 for production; HS256 only for local development
- **Secure Key Storage**: Store private keys securely (Azure Key Vault in production)
- **Token Lifetime**: Keep JWTs short-lived (15-60 minutes)
- **HTTPS Only**: Always use HTTPS for auth endpoints in production
- **State/Nonce Validation**: Implemented for CSRF protection
- **Audience Validation**: Always validate `aud` claim in consuming services
- **First User Auto-Promotion**: **SECURITY RISK** - The system can auto-promote the first user to admin when no admins exist. This is **disabled by default** (`AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED=false`) to prevent attackers from gaining admin access by authenticating first. For production, create the initial admin in a strictly isolated environment with temporary auto-promotion enabled, then immediately disable it. A dedicated bootstrap token mechanism is planned but not yet implemented. See [auth-implementation-summary.md](../docs/implementation-notes/auth-implementation-summary.md#security-considerations) for details.

## Production Deployment

For production deployments:

1. **Use Azure Key Vault** for JWT key storage
2. **Enable HTTPS** with valid TLS certificates
3. **Use Redis** for session storage (replace in-memory sessions)
4. **Enable DPoP** for proof-of-possession
5. **Configure rate limiting** on auth endpoints
6. **Monitor metrics** via Prometheus/Grafana
7. **Audit logs** for all authentication events
8. **Initial admin setup**: Create the first admin in a strictly isolated environment with temporary auto-promotion enabled, then immediately disable it. Bootstrap token mechanism is planned but not yet implemented.

## Future Enhancements

- [ ] Refresh token support
- [ ] DPoP proof-of-possession enablement
- [ ] Role mapping from provider organizations
- [ ] Service-to-service authentication (client credentials)
- [ ] Admin UI for key rotation and provider management
- [ ] Token revocation list
- [ ] Multi-factor authentication requirements

## License

MIT License - see LICENSE file for details.
