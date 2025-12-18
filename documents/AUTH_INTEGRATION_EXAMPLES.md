<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Auth Service Integration Examples

This document provides practical examples for integrating the Auth service into Copilot-for-Consensus microservices and external applications.

## Table of Contents

- [Overview](#overview)
- [FastAPI Service Integration](#fastapi-service-integration)
- [CLI Tool Integration](#cli-tool-integration)
- [Web UI Integration](#web-ui-integration)
- [Testing Authentication](#testing-authentication)

## Overview

The Auth service provides:
1. **OIDC Login Flow**: User-facing login via GitHub, Google, or Microsoft
2. **JWT Token Minting**: Service-scoped JWTs with custom claims
3. **JWT Validation**: Middleware for protecting service endpoints
4. **JWKS Endpoint**: Public key distribution for distributed validation

## FastAPI Service Integration

### Step 1: Add JWT Middleware

```python
# main.py
from fastapi import FastAPI
from auth.app.middleware import create_jwt_middleware

app = FastAPI(title="My Service")

# Add JWT middleware
jwt_middleware = create_jwt_middleware(
    auth_service_url="http://auth:8090",
    audience="my-service",
    public_paths=["/health", "/docs", "/openapi.json"]
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
    depends_on:
      auth:
        condition: service_healthy
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
    auth_url = os.getenv("AUTH_SERVICE_URL", "http://localhost:8090")
    
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

### Example: JavaScript/React Login Flow

```javascript
// authService.js
const AUTH_SERVICE_URL = process.env.REACT_APP_AUTH_SERVICE_URL || 'http://localhost:8090';
const AUDIENCE = 'copilot-reporting';

export const initiateLogin = (provider = 'github') => {
  const params = new URLSearchParams({
    provider: provider,
    aud: AUDIENCE,
  });
  
  // Redirect to auth service
  window.location.href = `${AUTH_SERVICE_URL}/login?${params}`;
};

export const handleCallback = () => {
  // This would be called on your callback page
  // Parse URL parameters or POST body to extract JWT
  const urlParams = new URLSearchParams(window.location.search);
  const token = urlParams.get('access_token');
  
  if (token) {
    // Store token in localStorage or sessionStorage
    localStorage.setItem('jwt_token', token);
    
    // Redirect to app
    window.location.href = '/';
  }
};

export const getToken = () => {
  return localStorage.getItem('jwt_token');
};

export const logout = () => {
  localStorage.removeItem('jwt_token');
  window.location.href = '/login';
};

export const fetchWithAuth = async (url, options = {}) => {
  const token = getToken();
  
  if (!token) {
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
    // Token expired, logout and redirect to login
    logout();
    throw new Error('Authentication expired');
  }
  
  return response;
};
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
        const response = await fetchWithAuth('http://localhost:8080/api/reports');
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
curl http://localhost:8090/keys

# 2. Initiate login (this will redirect, so use -i to see headers)
curl -i "http://localhost:8090/login?provider=github&aud=copilot-orchestrator"

# 3. After completing OAuth flow in browser, you'll get a JWT
# Use it to call protected endpoints:
JWT_TOKEN="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImRlZmF1bHQifQ..."

# 4. Get user info
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8090/userinfo

# 5. Call protected API
curl -H "Authorization: Bearer $JWT_TOKEN" \
  http://localhost:8080/api/reports
```

### Automated Testing

```python
# test_auth_integration.py
import pytest
import httpx

@pytest.fixture
def auth_service_url():
    return "http://localhost:8090"

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
