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

## Configuration

Configuration is provided via environment variables:

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
- `AUTH_GITHUB_CLIENT_ID`: GitHub OAuth client ID
- `AUTH_GITHUB_CLIENT_SECRET`: GitHub OAuth client secret
- `AUTH_GITHUB_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)
- `AUTH_GITHUB_API_BASE_URL`: GitHub API base URL (default: `https://api.github.com`)

**Google:**
- `AUTH_GOOGLE_CLIENT_ID`: Google OAuth client ID
- `AUTH_GOOGLE_CLIENT_SECRET`: Google OAuth client secret
- `AUTH_GOOGLE_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)

**Microsoft:**
- `AUTH_MS_CLIENT_ID`: Microsoft OAuth client ID
- `AUTH_MS_CLIENT_SECRET`: Microsoft OAuth client secret
- `AUTH_MS_REDIRECT_URI`: OAuth callback URL (default: `{issuer}/callback`)
- `AUTH_MS_TENANT`: Azure AD tenant ID (default: `common`)

### Security Configuration

- `AUTH_REQUIRE_PKCE`: Require PKCE for OAuth (default: `true`)
- `AUTH_REQUIRE_NONCE`: Require nonce for OIDC (default: `true`)
- `AUTH_MAX_SKEW_SECONDS`: Maximum clock skew tolerance (default: `90`)
- `AUTH_ENABLE_DPOP`: Enable DPoP proof-of-possession (default: `false`)

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

3. **Set environment variables:**
   ```bash
   export AUTH_ISSUER="http://localhost:8090"
   export AUTH_AUDIENCES="copilot-orchestrator,copilot-reporting"
   export JWT_ALGORITHM="RS256"
   export JWT_PRIVATE_KEY_PATH="config/dev_jwt_private.pem"
   export JWT_PUBLIC_KEY_PATH="config/dev_jwt_public.pem"
   
   # Configure at least one provider (example: GitHub)
   export AUTH_GITHUB_CLIENT_ID="your_github_client_id"
   export AUTH_GITHUB_CLIENT_SECRET="your_github_client_secret"
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

## Production Deployment

For production deployments:

1. **Use Azure Key Vault** for JWT key storage
2. **Enable HTTPS** with valid TLS certificates
3. **Use Redis** for session storage (replace in-memory sessions)
4. **Enable DPoP** for proof-of-possession
5. **Configure rate limiting** on auth endpoints
6. **Monitor metrics** via Prometheus/Grafana
7. **Audit logs** for all authentication events

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
