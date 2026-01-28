<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Authentication Adapter

An abstraction layer for identity and authentication providers in the Copilot-for-Consensus system. This module enables secure, role-aware access to summaries, drafts, and feedback tools while supporting multiple authentication strategies.

## Features

- **Abstract IdentityProvider Interface**: Common interface for all identity providers
- **User Model**: Standardized user representation with roles and affiliations
- **Multiple Provider Support**: GitHub OAuth, Google OIDC, Microsoft Entra ID, IETF Datatracker, and mock providers
- **JWT Middleware**: FastAPI middleware for validating JWT tokens across services
- **Factory Pattern**: Simple factory function for creating providers based on configuration
- **Role-Based Access**: Support for role and affiliation checking
- **Privacy-Conscious**: Designed with privacy and security in mind

## Supported Providers

### MockIdentityProvider
- **Purpose**: Testing and local development
- **Features**: In-memory user storage, no external dependencies
- **Use Cases**: Unit tests, local development, integration testing

### GitHubIdentityProvider (Scaffold)
- **Purpose**: Authenticate via GitHub OAuth
- **Features**: GitHub profile retrieval, organization affiliations
- **Status**: Scaffold implementation (requires completion)

### DatatrackerIdentityProvider (Scaffold)
- **Purpose**: Authenticate via IETF Datatracker
- **Features**: IETF profile retrieval, working group memberships, chair/delegate roles
- **Status**: Scaffold implementation (requires completion)

## Installation

Install the copilot-auth module:

```bash
cd adapters/copilot_auth
pip install -e .
```

Or for production:

```bash
pip install copilot-auth
```

## Quick Start

### Using Mock Provider for Testing

```python
from copilot_auth import create_identity_provider, User

# Create a mock provider
provider = create_identity_provider("mock")

# Add a test user
test_user = User(
    id="user-123",
    email="test@example.com",
    name="Test User",
    roles=["contributor"],
    affiliations=["IETF"]
)
provider.add_user("test-token", test_user)

# Retrieve the user
user = provider.get_user("test-token")
print(f"Welcome, {user.name}!")
```

### Creating Provider from Environment

```python
import os
from copilot_auth import create_identity_provider

# Set environment variable
os.environ["IDENTITY_PROVIDER"] = "mock"

# Create provider (uses environment variable)
provider = create_identity_provider()
```

### GitHub Provider (Scaffold)

```python
from copilot_auth import create_identity_provider

# Create GitHub provider
provider = create_identity_provider(
    "github",
    client_id="your-github-client-id",
    client_secret="your-github-client-secret"
)

# Or use environment variables
# GITHUB_CLIENT_ID=your-client-id
# GITHUB_CLIENT_SECRET=your-secret
provider = create_identity_provider("github")
```

### Datatracker Provider (Scaffold)

```python
from copilot_auth import create_identity_provider

# Create Datatracker provider
provider = create_identity_provider("datatracker")

# Or with custom API URL
provider = create_identity_provider(
    "datatracker",
    api_base_url="https://custom.datatracker.ietf.org/api"
)
```

## User Model

The `User` model represents an authenticated user:

```python
from copilot_auth import User

user = User(
    id="user-456",
    email="contributor@example.com",
    name="Jane Contributor",
    roles=["contributor", "reviewer", "chair"],
    affiliations=["IETF", "IRTF"]
)

# Check roles and affiliations
if user.has_role("chair"):
    print("User is a working group chair")

if user.has_affiliation("IETF"):
    print("User is affiliated with IETF")

# Serialize to dictionary
user_dict = user.to_dict()
```

## Using in Services

### JWT Middleware for FastAPI

The JWT middleware validates tokens on all requests (except public paths) and enforces audience and role-based access control:

```python
from fastapi import FastAPI, Request
from copilot_auth import create_jwt_middleware

app = FastAPI()

# Add JWT middleware with factory function
middleware = create_jwt_middleware(
    auth_service_url="http://auth:8090",
    audience="orchestrator",
    required_roles=["reader"],
)
app.add_middleware(middleware)

# Or use environment variables
# AUTH_SERVICE_URL=http://auth:8090
# SERVICE_NAME=orchestrator
app.add_middleware(create_jwt_middleware(required_roles=["reader"]))

# Protected endpoint - middleware validates token automatically
@app.get("/api/data")
async def get_data(request: Request):
    # JWT claims are available in request state
    user_id = request.state.user_id
    user_email = request.state.user_email
    user_roles = request.state.user_roles

    return {
        "data": "secret",
        "user": user_id,
        "roles": user_roles
    }

# Public endpoint - no token required
@app.get("/health")
async def health():
    return {"status": "ok"}
```

**Middleware Configuration:**

- `auth_service_url`: URL of auth service for JWKS retrieval (default: `AUTH_SERVICE_URL` env var)
- `audience`: Expected audience claim (default: `SERVICE_NAME` env var)
- `required_roles`: Optional list of required roles (default: none)
- `public_paths`: List of paths that don't require auth (default: `/health`, `/readyz`, `/docs`, `/openapi.json`)
- `jwks_cache_ttl`: JWKS cache TTL in seconds (default: 3600 = 1 hour)
- `jwks_fetch_retries`: Maximum number of attempts (including the initial attempt) to fetch JWKS during initial load (default: 10)
- `jwks_fetch_retry_delay`: Initial delay between retries in seconds (default: 1.0)
- `jwks_fetch_timeout`: Timeout for JWKS fetch requests in seconds (default: 30.0)
- `defer_jwks_fetch`: Defer JWKS fetch to background thread to avoid blocking startup (default: True)

**JWKS Fetch Resilience:**

The middleware implements robust JWKS (JSON Web Key Set) fetching with several reliability features:

1. **Jittered Exponential Backoff**: JWKS fetch attempts use exponential backoff with ±20% random jitter to prevent thundering herd problems when multiple services start simultaneously
2. **Increased Default Timeout**: 30-second timeout (up from 10s) accommodates cold-start and network delays
3. **More Fetch Attempts**: Up to 10 total attempts by default (including the initial attempt; previously 5) provide better resilience during startup
4. **Consolidated Error Logging**: Instead of logging a warning for each failed attempt, the middleware logs a single consolidated error with timing information after all attempts fail
5. **Background Fetch**: By default, JWKS fetch happens in a background thread to avoid blocking service startup

These improvements significantly reduce JWKS timeout/refusal errors observed in production environments with slow auth service startup or transient network issues.

**Request State Attributes:**

After successful validation, the middleware adds these attributes to `request.state`:
- `user_claims`: Full JWT claims dictionary
- `user_id`: Subject (`sub` claim)
- `user_email`: Email claim
- `user_roles`: Roles claim (list)

### Example: Protecting API Endpoints (Legacy Flask)

```python
from flask import Flask, request, jsonify
from copilot_auth import create_identity_provider, AuthenticationError

app = Flask(__name__)
provider = create_identity_provider()

@app.route("/api/summaries", methods=["GET"])
def get_summaries():
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Missing or invalid authorization"}), 401

    token = auth_header[7:]  # Remove "Bearer " prefix

    try:
        user = provider.get_user(token)
        if not user:
            return jsonify({"error": "Invalid token"}), 401

        # Check if user has required role
        if not user.has_role("contributor"):
            return jsonify({"error": "Insufficient permissions"}), 403

        # Return summaries (personalized based on user)
        return jsonify({
            "summaries": [],
            "user": user.to_dict()
        })

    except AuthenticationError as e:
        return jsonify({"error": str(e)}), 401
```

### Example: Role-Based Access Control

```python
from copilot_auth import create_identity_provider

provider = create_identity_provider()

def require_role(token: str, required_role: str) -> bool:
    """Check if user has required role."""
    user = provider.get_user(token)
    if not user:
        return False
    return user.has_role(required_role)

def require_affiliation(token: str, required_affiliation: str) -> bool:
    """Check if user has required affiliation."""
    user = provider.get_user(token)
    if not user:
        return False
    return user.has_affiliation(required_affiliation)
```

## Configuration

### Environment Variables

- `IDENTITY_PROVIDER`: Provider type ("mock", "github", "datatracker")
- `GITHUB_CLIENT_ID`: GitHub OAuth client ID
- `GITHUB_CLIENT_SECRET`: GitHub OAuth client secret
- `GITHUB_API_BASE_URL`: GitHub API base URL (default: https://api.github.com)
- `DATATRACKER_API_BASE_URL`: Datatracker API base URL (default: https://datatracker.ietf.org/api)

### Example Configuration

```bash
# Use mock provider for local development
export IDENTITY_PROVIDER=mock

# Use GitHub OAuth for production
export IDENTITY_PROVIDER=github
export GITHUB_CLIENT_ID=your-client-id
export GITHUB_CLIENT_SECRET=your-client-secret

# Use custom Datatracker instance
export IDENTITY_PROVIDER=datatracker
export DATATRACKER_API_BASE_URL=https://test.datatracker.ietf.org/api
```

## Testing

The authentication module includes comprehensive tests:

```bash
cd adapters/copilot_auth
pytest tests/test_auth*.py -v
```

### Test Coverage

```bash
cd adapters/copilot_auth
pytest tests/test_auth*.py --cov=copilot_auth --cov-report=html
```

## Architecture

### IdentityProvider Interface

All providers implement the `IdentityProvider` abstract base class:

```python
class IdentityProvider(ABC):
    @abstractmethod
    def get_user(self, token: str) -> Optional[User]:
        """Retrieve user information from an authentication token."""
        pass
```

### Factory Pattern

The `create_identity_provider` factory function selects the appropriate provider based on configuration:

```python
provider = create_identity_provider(
    provider_type="github",  # or None to use IDENTITY_PROVIDER env var
    **provider_specific_config
)
```

## Future Enhancements

- Complete GitHub OAuth implementation
- Complete Datatracker implementation
- Add email-based authentication provider
- Add JWT token validation
- Add OAuth2 token refresh
- Add user session management
- Add audit logging for authentication events

## Security Considerations

- Store tokens securely (never log or commit tokens)
- Use HTTPS for all authentication endpoints
- Implement token expiration and refresh
- Follow OAuth2 best practices
- Validate all tokens before granting access
- Implement rate limiting on authentication endpoints

## Contributing

See the main repository's CONTRIBUTING.md for contribution guidelines.

## License

MIT License - see LICENSE file for details.
