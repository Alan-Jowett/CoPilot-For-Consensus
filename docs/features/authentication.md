<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Auth Service Integration Examples

This document provides practical examples for integrating the Auth service into Copilot-for-Consensus microservices and external applications.

## Table of Contents

- [Overview](#overview)
- [FastAPI Service Integration](#fastapi-service-integration)
- [Role-Based Access Control](#role-based-access-control)
- [Service-to-Service Authentication](#service-to-service-authentication)
- [CLI Tool Integration](#cli-tool-integration)
- [Web UI Integration](#web-ui-integration)
- [Testing Authentication](#testing-authentication)

## Overview

The Auth service provides:
1. **OIDC Login Flow**: User-facing login via GitHub, Google, or Microsoft
2. **JWT Token Minting**: Service-scoped JWTs with custom claims
3. **JWT Validation**: Middleware for protecting service endpoints
4. **JWKS Endpoint**: Public key distribution for distributed validation
5. **Role-Based Access Control**: Enforce role requirements per endpoint

## FastAPI Service Integration

### Step 1: Add JWT Middleware

All Copilot-for-Consensus microservices now use the `copilot_auth` adapter for authentication:

```python
# main.py
from fastapi import FastAPI, Request
from copilot_auth import create_jwt_middleware

app = FastAPI(title="My Service")

# Add JWT middleware with role-based access control
jwt_middleware = create_jwt_middleware(
    auth_service_url="http://auth:8090",  # Optional: defaults to AUTH_SERVICE_URL env var
    audience="my-service",                 # Optional: defaults to SERVICE_NAME env var
    required_roles=["reader"],             # Optional: roles required for protected endpoints
    public_paths=["/health", "/docs", "/openapi.json"]  # Optional: public endpoints
)
app.add_middleware(jwt_middleware)

@app.get("/api/protected")
def protected_endpoint(request: Request):
    """Protected endpoint requiring authentication."""
    # Access user claims from request.state
    user_id = request.state.user_id
    user_email = request.state.user_email
    user_roles = request.state.user_roles

    return {
        "message": "Access granted",
        "user": {
            "id": user_id,
            "email": user_email,
            "roles": user_roles
        }
    }
```

### Step 2: Configure Environment Variables

```bash
# docker-compose.yml or .env
AUTH_SERVICE_URL=http://auth:8090
SERVICE_NAME=my-service
```

### Step 3: Add Auth Service Dependency

```yaml
# docker-compose.yml
services:
  my-service:
    image: my-service:latest
    environment:
      - AUTH_SERVICE_URL=http://auth:8090
      - SERVICE_NAME=my-service
    volumes:
      - ./adapters/copilot_auth:/app/adapters/copilot_auth:ro
    depends_on:
      auth:
        condition: service_healthy
```

## Role-Based Access Control

### Service Role Requirements

Each microservice enforces specific role requirements:

| Service | Required Role | Purpose |
|---------|--------------|---------|
| Reporting API | `reader` | Public read access to summaries and reports |
| Orchestrator | `orchestrator` | Coordinate RAG workflow and summarization |
| Chunking | `processor` | Internal processing service |
| Embedding | `processor` | Internal processing service |
| Parsing | `processor` | Internal processing service |
| Summarization | `processor` | Internal processing service |
| Ingestion API | `admin` | Administrative source management |

### Example: Multiple Role Requirements

```python
# Require multiple roles
jwt_middleware = create_jwt_middleware(
    required_roles=["reader", "contributor"],
    public_paths=["/health", "/docs"]
)
app.add_middleware(jwt_middleware)
```

### Example: Endpoint-Specific Role Checks

```python
from fastapi import HTTPException, Request

@app.get("/api/admin/users")
def admin_only_endpoint(request: Request):
    """Endpoint requiring admin role."""
    user_roles = request.state.user_roles

    if "admin" not in user_roles:
        raise HTTPException(
            status_code=403,
            detail="Admin role required"
        )

    return {"users": [...]}
```

## Service-to-Service Authentication

For internal service-to-service calls, services can use service accounts or system tokens:

```python
import httpx

# Service making authenticated request to another service
async def call_reporting_api(token: str):
    """Call reporting API with authentication."""
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://reporting:8080/api/reports",
            headers=headers
        )
        response.raise_for_status()
        return response.json()
```

## CLI Tool Integration

### Example: Python CLI with Auth

```python
#!/usr/bin/env python3
# cli_tool.py

import os
import sys
import webbrowser
import httpx
from urllib.parse import urlencode

def login(provider="github", audience="copilot-orchestrator"):
    """Initiate OAuth login flow."""
    auth_url = os.getenv("AUTH_SERVICE_URL", "http://localhost:8080/auth")

    # Build login URL
    params = {
        "provider": provider,
        "aud": audience
    }
    login_url = f"{auth_url}/login?{urlencode(params)}"

    print(f"Opening browser for {provider} login...")
    print(f"Login URL: {login_url}")

    # Open browser
    webbrowser.open(login_url)

    # In a real CLI, you'd:
    # 1. Start a local HTTP server to receive callback
    # 2. Parse the callback and extract the JWT
    # 3. Store the JWT in a config file or keychain

    # For this example, user manually copies token
    print("\nAfter logging in, copy the 'access_token' from the JSON response")
    token = input("Paste your JWT token here: ").strip()

    # Save token
    token_file = os.path.expanduser("~/.copilot/token")
    os.makedirs(os.path.dirname(token_file), exist_ok=True)
    with open(token_file, "w") as f:
        f.write(token)

    print(f"Token saved to {token_file}")
    return token

def api_call(endpoint, audience="copilot-orchestrator"):
    """Make authenticated API call."""
    # Load token
    token_file = os.path.expanduser("~/.copilot/token")
    if not os.path.exists(token_file):
        print("Not logged in. Run: python cli_tool.py login")
        sys.exit(1)

    with open(token_file, "r") as f:
        token = f.read().strip()

    # Make API call
    api_url = os.getenv("API_URL", "http://localhost:8080")

    response = httpx.get(
        f"{api_url}{endpoint}",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code == 401:
        print("Token expired or invalid. Please login again.")
        sys.exit(1)

    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cli_tool.py [login|call]")
        sys.exit(1)

    command = sys.argv[1]

    if command == "login":
        provider = sys.argv[2] if len(sys.argv) > 2 else "github"
        login(provider=provider)

    elif command == "call":
        endpoint = sys.argv[2] if len(sys.argv) > 2 else "/api/reports"
        data = api_call(endpoint)
        print(data)
```

**Usage:**

```bash
# Login via GitHub
python cli_tool.py login github

# Make API call
python cli_tool.py call /api/reports
```

## Web UI Integration

### Example: JavaScript/React Login Flow (Secure)

**IMPORTANT SECURITY NOTES:**
- ❌ **NEVER put JWTs in URL query parameters** - they leak via browser history, referrers, and logs
- ❌ **NEVER use localStorage for tokens** - vulnerable to XSS attacks and malicious scripts
- ✅ **Use httpOnly cookies** (best) or POST responses with sessionStorage (acceptable)

```javascript
// authService.js
const AUTH_SERVICE_URL = process.env.REACT_APP_AUTH_SERVICE_URL || 'http://localhost:8080/auth';
const AUDIENCE = 'copilot-reporting';

export const initiateLogin = (provider = 'github') => {
  // Store return URL for post-login redirect
  sessionStorage.setItem('auth_return_url', window.location.pathname);

  const params = new URLSearchParams({
    provider: provider,
    aud: AUDIENCE,
  });

  // Redirect to auth service
  window.location.href = `${AUTH_SERVICE_URL}/login?${params}`;
};

export const handleCallback = async () => {
  /**
   * SECURE callback handler.
   *
   * The auth service should redirect to your callback page with:
   * - state parameter (validated)
   * - code parameter (exchanged server-side)
   *
   * Your backend should:
   * 1. Exchange code for token server-side
   * 2. Store token in httpOnly cookie
   * 3. Redirect to application
   */

  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');

  if (!code || !state) {
    throw new Error('Invalid callback - missing code or state');
  }

  // Exchange code for token via your backend
  const response = await fetch('/api/auth/callback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    credentials: 'include', // Include cookies
    body: JSON.stringify({ code, state }),
  });

  if (!response.ok) {
    throw new Error('Authentication failed');
  }

  // Token is now stored in httpOnly cookie by backend
  // Redirect to original URL
  const returnUrl = sessionStorage.getItem('auth_return_url') || '/';
  sessionStorage.removeItem('auth_return_url');
  window.location.href = returnUrl;
};

export const logout = async () => {
  // Clear httpOnly cookie via backend
  await fetch('/api/auth/logout', {
    method: 'POST',
    credentials: 'include',
  });

  window.location.href = '/login';
};

export const fetchWithAuth = async (url, options = {}) => {
  /**
   * Fetch with automatic auth handling.
   * Token is sent automatically via httpOnly cookie.
   */
  const response = await fetch(url, {
    ...options,
    credentials: 'include', // Send cookies
  });

  if (response.status === 401) {
    // Token expired or invalid - redirect to login
    window.location.href = '/login';
    throw new Error('Authentication required');
  }

  return response;
};

// Alternative: If you MUST use sessionStorage (less secure than cookies)
export const handleCallbackWithSessionStorage = async () => {
  const urlParams = new URLSearchParams(window.location.search);
  const code = urlParams.get('code');
  const state = urlParams.get('state');

  // Exchange code for token via backend
  const response = await fetch('/api/auth/callback', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ code, state }),
  });

  if (!response.ok) {
    throw new Error('Authentication failed');
  }

  const data = await response.json();

  // Store in sessionStorage (cleared on tab close, safer than localStorage)
  sessionStorage.setItem('jwt_token', data.access_token);

  // Clean URL (remove code/state from history)
  window.history.replaceState({}, document.title, window.location.pathname);

  // Redirect to app
  const returnUrl = sessionStorage.getItem('auth_return_url') || '/';
  sessionStorage.removeItem('auth_return_url');
  window.location.href = returnUrl;
};

export const fetchWithSessionStorage = async (url, options = {}) => {
  const token = sessionStorage.getItem('jwt_token');

  if (!token) {
    window.location.href = '/login';
    throw new Error('Not authenticated');
  }

  const headers = {
    ...options.headers,
    'Authorization': `Bearer ${token}`,
  };

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    sessionStorage.removeItem('jwt_token');
    window.location.href = '/login';
    throw new Error('Authentication expired');
  }

  return response;
};
```

**Backend callback handler (Node.js/Express example):**

```javascript
// server/routes/auth.js
app.post('/api/auth/callback', async (req, res) => {
  const { code, state } = req.body;

  // Exchange code for token with auth service
  const tokenResponse = await fetch(`${AUTH_SERVICE_URL}/callback?code=${code}&state=${state}`);

  if (!tokenResponse.ok) {
    return res.status(401).json({ error: 'Authentication failed' });
  }

  const { access_token, expires_in } = await tokenResponse.json();

  // Store token in httpOnly cookie (SECURE)
  res.cookie('jwt_token', access_token, {
    httpOnly: true,  // Not accessible to JavaScript
    secure: true,    // Only sent over HTTPS
    sameSite: 'strict', // CSRF protection
    maxAge: expires_in * 1000, // Match token expiry
  });

  res.json({ success: true });
});

app.post('/api/auth/logout', (req, res) => {
  res.clearCookie('jwt_token');
  res.json({ success: true });
});

// Middleware to extract token from cookie and validate
app.use('/api/*', async (req, res, next) => {
  const token = req.cookies.jwt_token;

  if (!token) {
    return res.status(401).json({ error: 'Not authenticated' });
  }

  // Validate token with auth service or verify locally with JWKS
  try {
    const userInfo = await fetch(`${AUTH_SERVICE_URL}/userinfo`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (!userInfo.ok) {
      return res.status(401).json({ error: 'Invalid token' });
    }

    req.user = await userInfo.json();
    next();
  } catch (error) {
    return res.status(401).json({ error: 'Authentication failed' });
  }
});
```

**Usage in React component:**

```jsx
// Login.jsx
import React from 'react';
import { initiateLogin } from './authService';

const Login = () => {
  return (
    <div>
      <h1>Login to Copilot for Consensus</h1>
      <button onClick={() => initiateLogin('github')}>
        Login with GitHub
      </button>
      <button onClick={() => initiateLogin('google')}>
        Login with Google
      </button>
      <button onClick={() => initiateLogin('microsoft')}>
        Login with Microsoft
      </button>
    </div>
  );
};

export default Login;
```

```jsx
// Reports.jsx
import React, { useEffect, useState } from 'react';
import { fetchWithAuth } from './authService';

const Reports = () => {
  const [reports, setReports] = useState([]);

  useEffect(() => {
    const loadReports = async () => {
      try {
        const response = await fetchWithAuth('http://localhost:8080/reporting/api/reports');
        const data = await response.json();
        setReports(data);
      } catch (error) {
        console.error('Failed to load reports:', error);
      }
    };

    loadReports();
  }, []);

  return (
    <div>
      <h1>Reports</h1>
      <ul>
        {reports.map(report => (
          <li key={report.id}>{report.title}</li>
        ))}
      </ul>
    </div>
  );
};

export default Reports;
```

## Testing Authentication

### Manual Testing with cURL

```bash
# 1. Get JWKS to verify service is running
curl http://localhost:8080/auth/keys

# 2. Initiate login (this will redirect, so use -i to see headers)
curl -i "http://localhost:8080/auth/login?provider=github&aud=copilot-orchestrator"

# 3. After completing OAuth flow in browser, you'll get a JWT
# Use it to call protected endpoints:
JWT_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImRlZmF1bHQifQ..."

# 4. Get user info
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8080/auth/userinfo

# 5. Call protected API
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8080/reporting/api/reports
```

### Automated Testing

```python
# test_auth_integration.py
import pytest
import httpx

@pytest.fixture
def auth_service_url():
  return "http://localhost:8080/auth"

@pytest.fixture
def test_token(auth_service_url):
    """Get a test token (requires mock provider)."""
    # In real tests, you'd use a mock OIDC provider
    # For this example, we assume a mock endpoint
    response = httpx.post(
        f"{auth_service_url}/test/mint_token",
        json={
            "user_id": "test-user",
            "email": "test@example.com",
            "roles": ["contributor"]
        }
    )
    return response.json()["access_token"]

def test_userinfo_with_valid_token(auth_service_url, test_token):
    """Test /userinfo endpoint with valid token."""
    response = httpx.get(
        f"{auth_service_url}/userinfo",
        headers={"Authorization": f"Bearer {test_token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "contributor" in data["roles"]

def test_userinfo_without_token(auth_service_url):
    """Test /userinfo endpoint without token."""
    response = httpx.get(f"{auth_service_url}/userinfo")
    assert response.status_code == 401

def test_jwks_endpoint(auth_service_url):
    """Test JWKS endpoint."""
    response = httpx.get(f"{auth_service_url}/keys")
    assert response.status_code == 200

    data = response.json()
    assert "keys" in data
    assert len(data["keys"]) > 0
    assert data["keys"][0]["kty"] == "RSA"
```

## Best Practices

1. **Token Storage**:
   - Web apps: Use `httpOnly` cookies or sessionStorage
   - Mobile apps: Use secure keychain/keystore
   - CLI tools: Use encrypted config files

2. **Token Refresh**:
   - Handle 401 responses by redirecting to login
   - Implement token refresh before expiry (proactive renewal)

3. **Security**:
   - Always use HTTPS in production
   - Validate audience (`aud`) claim
   - Check token expiry (`exp`) on every request
   - Never log or commit tokens

4. **Error Handling**:
   - Handle network errors gracefully
   - Provide clear error messages
   - Log authentication failures for audit

## See Also

- [Auth Service README](../auth/README.md)
- [OIDC Specification](https://openid.net/specs/openid-connect-core-1_0.html)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
