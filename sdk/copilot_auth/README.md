<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Authentication SDK

An abstraction layer for identity and authentication providers in the Copilot-for-Consensus system. This module enables secure, role-aware access to summaries, drafts, and feedback tools while supporting multiple authentication strategies.

## Features

- **Abstract IdentityProvider Interface**: Common interface for all identity providers
- **User Model**: Standardized user representation with roles and affiliations
- **Multiple Provider Support**: GitHub OAuth, IETF Datatracker, and mock providers
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

The authentication module is part of the copilot-events SDK:

```bash
cd sdk
pip install -e .
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

### Example: Protecting API Endpoints

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
cd sdk
pytest tests/test_auth*.py -v
```

### Test Coverage

```bash
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
