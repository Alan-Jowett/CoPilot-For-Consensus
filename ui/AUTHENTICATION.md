<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Authentication Architecture

## Overview

The UI uses **httpOnly cookie-based authentication** to protect against XSS attacks. Authentication tokens are never accessible to JavaScript, eliminating the risk of token theft via XSS vulnerabilities.

## Security Features

### 1. HttpOnly Cookies
- **What**: JWT tokens are stored in httpOnly cookies set by the auth service
- **Why**: JavaScript cannot access httpOnly cookies, preventing XSS-based token theft
- **Implementation**: Auth service sets `httpOnly=true` flag on `auth_token` cookie

### 2. SameSite Protection
- **What**: Cookies use `SameSite=lax` attribute
- **Why**: Provides CSRF protection by preventing cookies from being sent with cross-site POST requests
- **Implementation**: Auth service sets `samesite="lax"` on cookies
- **Note**: `SameSite=lax` allows cookies on top-level navigation (clicking links), enabling seamless SSO

### 3. Secure Flag (Production)
- **What**: Cookies use `Secure` flag when HTTPS is available
- **Why**: Ensures cookies are only sent over encrypted connections
- **Implementation**: Set `COOKIE_SECURE=true` environment variable in production
- **Default**: `COOKIE_SECURE=false` for local development (HTTP)

### 4. Cookie-Based Request Flow

#### Login Flow
1. User clicks "Sign in with GitHub/Google/Microsoft"
2. UI redirects to `/auth/login?provider=<provider>&aud=copilot-for-consensus`
3. Auth service redirects to OAuth provider
4. OAuth provider redirects back to `/auth/callback?code=<code>&state=<state>`
5. Auth service exchanges code for token and sets httpOnly cookie
6. Auth service redirects to `/ui/callback?token=<token>` (token in URL for transition)
7. UI redirects to `/ui/reports` (cookie is already set)

#### API Request Flow
1. UI makes API request with `credentials: 'include'`
2. Browser automatically includes httpOnly `auth_token` cookie
3. Gateway extracts JWT from cookie and adds `Authorization: Bearer <token>` header
4. Backend service validates JWT and processes request

#### Logout Flow
1. User clicks "Logout"
2. UI calls `/auth/logout` (POST) with `credentials: 'include'`
3. Auth service clears httpOnly cookie (sets `max_age=0`)
4. UI redirects to login page

### 5. Gateway Cookie-to-Header Translation

The API Gateway extracts JWT tokens from cookies and converts them to Authorization headers for backend services:

```nginx
# Extract JWT from cookie or Authorization header
map $http_authorization $auth_header {
  "" "Bearer $cookie_auth_token";  # Use cookie if no header
  default $http_authorization;      # Use header if provided
}

# Pass to backend services
proxy_set_header Authorization $auth_header;
```

This allows:
- UI to use cookie-based authentication (secure against XSS)
- Backend services to continue using standard Bearer token authentication
- Seamless integration with services like Grafana that support JWT headers

## Removed: localStorage Token Storage

**Previous implementation (INSECURE)**:
- Tokens stored in `localStorage.setItem('auth_token', token)`
- Accessible to JavaScript via `localStorage.getItem('auth_token')`
- Vulnerable to XSS attacks - any injected script could steal tokens

**Current implementation (SECURE)**:
- Tokens stored in httpOnly cookies by auth service
- Not accessible to JavaScript
- Automatically sent by browser with `credentials: 'include'`

## CSRF Protection

### SameSite=lax
- Provides automatic CSRF protection for state-changing requests (POST, PUT, DELETE)
- Cookies are NOT sent with cross-site POST requests
- Cookies ARE sent with top-level navigation (clicking links)

### No Additional CSRF Tokens Required
Since we use `SameSite=lax` cookies, additional CSRF tokens are not necessary for most use cases. The combination of:
- httpOnly cookies (XSS protection)
- SameSite=lax (CSRF protection)
- HTTPS with Secure flag (transport security)

provides comprehensive protection against common web attacks.

## Authentication State Management

The UI checks authentication state by calling `/auth/userinfo`:

```typescript
// AuthContext.tsx
const checkAuth = async () => {
  const response = await fetch('/auth/userinfo', {
    credentials: 'include'  // Include httpOnly cookies
  })

  if (response.ok) {
    const data = await response.json()
    setUserInfo(data)
    setIsAuthenticated(true)
  }
}
```

The `/auth/userinfo` endpoint:
- Accepts JWT from either Authorization header or `auth_token` cookie
- Returns user information including roles
- Returns 401 if token is invalid or expired

## Production Configuration

### Environment Variables

Set these environment variables in production:

```bash
# Enable Secure flag for cookies (requires HTTPS)
COOKIE_SECURE=true

# Set appropriate token expiry (default: 30 minutes)
JWT_DEFAULT_EXPIRY=1800

# Configure HTTPS at the gateway
# (gateway serves on port 443 with TLS certificates)
```

### TLS Certificates

The gateway requires TLS certificates for production:

```bash
# Mount certificates in docker-compose.yml
volumes:
  - ./secrets/gateway_tls_cert:/etc/nginx/certs/server.crt:ro
  - ./secrets/gateway_tls_key:/etc/nginx/certs/server.key:ro
```

## Testing Authentication

### Verify Cookie Security

1. Open browser DevTools > Application > Cookies
2. Check `auth_token` cookie has:
   - ✅ `HttpOnly` flag set
   - ✅ `SameSite=Lax` attribute
   - ✅ `Secure` flag (if using HTTPS)
   - ✅ `Path=/`

### Verify XSS Protection

Try to access token from browser console:
```javascript
// This should return null (token not accessible to JavaScript)
localStorage.getItem('auth_token')  // null
document.cookie.match(/auth_token=([^;]+)/)  // null (httpOnly)
```

### Verify API Calls

Check Network tab in DevTools:
- ✅ API requests include Cookie header with `auth_token`
- ✅ Backend responses include proper status codes (200, 401, 403)
- ❌ No Authorization header in browser requests (cookies used instead)

## Migration Notes

### Changes from Previous Implementation

1. **Removed localStorage access**:
   - `AuthContext.tsx`: No longer reads/writes to localStorage
   - `api.ts`: No longer adds Authorization headers manually
   - `Callback.tsx`: No longer stores tokens in localStorage
   - `main.tsx`: No longer initializes from localStorage

2. **Added cookie-based authentication**:
   - All API calls use `credentials: 'include'`
   - Auth state checked via `/auth/userinfo` endpoint
   - Gateway translates cookies to Authorization headers

3. **Updated nginx configuration**:
   - Gateway extracts JWT from cookies
   - Passes JWT as Authorization header to backend services

### Backward Compatibility

The auth service supports both authentication methods:
- Cookie-based (recommended): JWT in `auth_token` cookie
- Header-based (legacy): JWT in `Authorization: Bearer <token>` header

This allows gradual migration and testing.

## References

- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)
- [OWASP XSS Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP CSRF Prevention](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [MDN: HTTP cookies](https://developer.mozilla.org/en-US/docs/Web/HTTP/Cookies)
- [RFC 6265: HTTP State Management Mechanism](https://tools.ietf.org/html/rfc6265)
