<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Adapter Examples

This directory contains example applications demonstrating how to use the Copilot adapter modules.

## Authentication Example

**File**: `auth_example.py`

A complete Flask application demonstrating how to integrate the authentication abstraction layer for role-based access control.

### Features

- **Bearer token authentication**: Extract and validate tokens from Authorization headers
- **Role-based access control**: Require specific roles for endpoint access
- **Affiliation checking**: Verify user organizational affiliations
- **Mock provider**: Pre-configured test users for demonstration

### Running the Example

1. Install dependencies:
   ```bash
   pip install flask
   cd adapters/copilot_auth
   pip install -e .
   ```

2. Run the example:
   ```bash
   cd adapters/copilot_auth/examples
   python3 auth_example.py
   ```

3. Test the endpoints:

   **Health check (no authentication required)**:
   ```bash
   curl http://localhost:5000/
   ```

   **Get user profile (requires authentication)**:
   ```bash
   curl -H 'Authorization: Bearer token-contributor' \
        http://localhost:5000/api/profile
   ```

   **Get summaries (requires 'contributor' role)**:
   ```bash
   curl -H 'Authorization: Bearer token-contributor' \
        http://localhost:5000/api/summaries
   ```

   **Create report (requires 'chair' role)**:
   ```bash
   curl -X POST -H 'Authorization: Bearer token-chair' \
        -H 'Content-Type: application/json' \
        -d '{"title": "My Report"}' \
        http://localhost:5000/api/admin/reports
   ```

   **Get working group members (requires 'IETF' affiliation)**:
   ```bash
   curl -H 'Authorization: Bearer token-chair' \
        http://localhost:5000/api/wg-members
   ```

   **Try with invalid token (should fail)**:
   ```bash
   curl -H 'Authorization: Bearer invalid-token' \
        http://localhost:5000/api/profile
   ```

### Test Users

The example includes two pre-configured test users:

1. **Jane Contributor** (token: `token-contributor`)
   - Roles: `contributor`
   - Affiliations: `IETF`

2. **John Chair** (token: `token-chair`)
   - Roles: `contributor`, `chair`
   - Affiliations: `IETF`, `IRTF`

### Integration Patterns

The example demonstrates several integration patterns:

#### 1. Token Extraction
```python
def get_authenticated_user():
    """Extract and validate authentication token from request."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    return provider.get_user(token)
```

#### 2. Role-Based Decorator
```python
@require_role("chair")
def create_report(user):
    """Create a report (requires chair role)."""
    # Implementation
```

#### 3. Affiliation Checking
```python
if not user.has_affiliation("IETF"):
    return jsonify({"error": "IETF affiliation required"}), 403
```

### Adapting for Production

To use this pattern in production:

1. **Configure the identity provider**:
   ```python
   # Use GitHub OAuth
   provider = create_identity_provider(
       "github",
       client_id=os.environ["GITHUB_CLIENT_ID"],
       client_secret=os.environ["GITHUB_CLIENT_SECRET"]
   )
   ```

2. **Add token validation**:
   - Implement token expiration checking
   - Add rate limiting
   - Log authentication attempts

3. **Secure the application**:
   - Use HTTPS in production
   - Store secrets securely (use environment variables or secret managers)
   - Implement CORS policies
   - Add request logging and monitoring

4. **Handle errors gracefully**:
   ```python
   try:
       user = provider.get_user(token)
   except AuthenticationError as e:
       logger.warning(f"Authentication failed: {e}")
       return jsonify({"error": "Invalid token"}), 401
   except ProviderError as e:
       logger.error(f"Provider error: {e}")
       return jsonify({"error": "Authentication service unavailable"}), 503
   ```

## Future Examples

Additional examples to be added:

- Event publishing and subscribing patterns
- Integration with RabbitMQ
- Multi-service authentication flow
- Token refresh and session management
- WebSocket authentication
