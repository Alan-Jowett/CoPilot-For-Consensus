<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Moved: Auth Service Integration Examples

This content now lives at [docs/features/authentication.md](../docs/features/authentication.md).
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
