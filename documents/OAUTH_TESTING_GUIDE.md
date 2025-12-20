<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# End-to-End OAuth2 + JWT Authentication Testing Guide

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                       React SPA (UI)                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Routes: /login, /callback, /reports, /sources           │   │
│  │ AuthContext: Manages token state in React              │   │
│  │ api.ts: Injects Authorization header in API calls      │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│                         localStorage                             │
│                    [JWT Token ~700 chars]                        │
└──────────────────┬──────────────────────────────────────────────┘
                   │
                   │ https://localhost:8080/ui/*
                   │
        ┌──────────▼──────────┐
        │  Nginx API Gateway  │
        │   Port: 8080        │
        │  /ui/ → React SPA   │
        │  /auth/ → Auth API  │
        └──────────┬──────────┘
                   │
         ┌─────────┴──────────┐
         │                    │
    ┌────▼────┐        ┌─────▼──────┐
    │ Auth    │        │ Reporting  │
    │ Service │        │ Service    │
    │(OAuth2) │        │(JWT Auth)  │
    └────┬────┘        └─────▲──────┘
         │                   │
    ┌────▼────────────────────┴──────────┐
    │      Docker Network (default)       │
    │  - All services communicate here   │
    └────┬──────────────────────────────┘
         │
    ┌────▼────────────────────┐
    │    MongoDB              │
    │  - User Roles Storage   │
    │  - Session Data         │
    └───────────────────────┘
```

## Complete Authentication Flow

### Step 1: User Initiates Login
1. User navigates to `http://localhost:8080/ui/login`
2. React Login component renders with provider buttons
3. User clicks "Login with GitHub" button
4. Browser redirects to GitHub OAuth login

### Step 2: GitHub OAuth Authorization
1. User sees GitHub authorization screen
2. User authorizes the application
3. GitHub redirects to: `http://localhost:8080/auth/callback?code=<AUTH_CODE>&state=<STATE>`

### Step 3: Auth Service Processes OAuth Callback
**Auth Service Flow** (`auth/main.py` → `/callback` endpoint):
```
1. Receive code and state from GitHub
2. Verify state matches session (CSRF protection)
3. Exchange code for access token from GitHub
4. Request user info from GitHub (email, username, etc.)
5. Lookup or create user in MongoDB (role assignment)
6. Generate local JWT token with:
   - User ID
   - Email
   - GitHub username
   - Role (from MongoDB)
   - 30-minute expiry
   - RS256 signature
7. Return JSON: { access_token, token_type: "Bearer", expires_in: 1800 }
```

### Step 4: React Callback Component Handles Token
**Callback Component** (`ui/src/routes/Callback.tsx`):
```
1. Extract code and state from URL
2. Call: GET /auth/callback?code=...&state=...
3. Receive JSON with access_token
4. Store to localStorage: localStorage.setItem('auth_token', token)
5. Call AuthContext.setAuthToken(token)
6. Redirect to: /ui/reports
```

### Step 5: AuthContext Initializes from Token
**AuthContext** (`ui/src/contexts/AuthContext.tsx`):
```
1. Component mounts
2. Reads from localStorage: getItem('auth_token')
3. Sets React state: setToken(loadedToken)
4. useAuth() hook now provides token to components
```

### Step 6: API Calls Include Authorization Header
**API Function** (`ui/src/api.ts` → `fetchWithAuth()`):
```
1. Component calls: fetchWithAuth('/reporting/api/reports')
2. Function reads token: localStorage.getItem('auth_token')
3. Adds header: Authorization: Bearer <TOKEN>
4. Makes request: GET /reporting/api/reports
   Headers: { Authorization: "Bearer <TOKEN>" }
5. Reporting service validates JWT signature (using auth service's public key)
6. Request succeeds, returns 200 with data
```

## Verification Steps

### Prerequisites
- Docker and docker-compose running
- System has been started: `docker compose up -d`
- All services are healthy:
  ```bash
  docker compose ps --filter "status=running" | grep -E "auth|reporting|ui|gateway"
  ```

### Verify Each Layer

#### 1. Auth Service Ready
```bash
curl -s http://localhost:8080/auth/health | jq .
# Expected: { "status": "ok" }

curl -s http://localhost:8080/auth/.well-known/jwks.json | jq '.keys | length'
# Expected: 1 (one RSA key for JWT validation)
```

#### 2. Reporting Service Ready
```bash
# Should return 401 without token
curl -s -i http://localhost:8080/reporting/api/reports | head -1
# Expected: HTTP/1.1 401 Unauthorized

# Check error message
curl -s http://localhost:8080/reporting/api/reports | jq .detail
# Expected: "Missing or invalid Authorization header"
```

#### 3. UI Service Ready
```bash
curl -s http://localhost:8080/ui/ | head -c 100
# Expected: HTML with <div id="root"></div>
```

#### 4. Gateway Routing
```bash
curl -s http://localhost:8080/ | jq '.version // .status'
# Expected: Reporting service response
```

### Manual OAuth Flow Test

#### Open Browser to UI
```
http://localhost:8080/ui/login
```

#### Check Console Logs (F12 → Console tab)
Watch for these logs in order:

1. **Before clicking login**:
   ```
   [AuthContext] Initialized from localStorage: false
   ```

2. **During OAuth redirect (see only if "Preserve log" is enabled)**:
   ```
   [Callback] Component mounted, searchParams: { code: "...", state: "..." }
   [Callback] Code found, exchanging for token
   [Callback] Exchanging code for token, calling /auth/callback...
   [Callback] Response status: 200
   [Callback] Got response: { access_token: true, token_type: "Bearer" }
   [Callback] Storing token directly to localStorage
   [Callback] Token stored in localStorage, length: 796
   [Callback] Verify localStorage has token: true
   [Callback] Calling setAuthToken()
   [Callback] Will redirect to /ui/reports in 1 second
   [Callback] NOW redirecting to /ui/reports
   ```

3. **After redirect to reports page**:
   ```
   [AuthContext] Initialized from localStorage: true
   [AuthContext] Token changed: true
   [fetchWithAuth] URL: http://localhost:8080/reporting/api/reports?limit=20&skip=0 Has token: true
   [fetchWithAuth] URL: http://localhost:8080/reporting/api/sources Has token: true
   ```

4. **If reports load**:
   - Reports table should show data
   - Sources table should show data
   - No 401 errors

#### Check Storage (F12 → Storage → LocalStorage)
After successful login, should see:
```
auth_token: eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...
```

The token should be:
- Type: JWT (starts with `eyJ`)
- Length: ~700-800 characters
- Payload contains: `sub`, `email`, `github_username`, `role`, `iat`, `exp`

To decode JWT (in console):
```javascript
// Get the payload (middle part)
const payload = localStorage.getItem('auth_token').split('.')[1]
// Decode base64
const decoded = JSON.parse(atob(payload))
console.log(decoded)
// Should show: {
//   sub: "user-id",
//   email: "user@github.com",
//   github_username: "username",
//   role: "user",
//   iat: 1702500000,
//   exp: 1702501800
// }
```

### Test API Calls Directly

#### With Token (Successful)
```bash
# Get token from running browser console
TOKEN=$(curl -s http://localhost:8080/ui/ -H "Cookie: auth_token=..." | grep -o '"[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*\.[a-zA-Z0-9_-]*"' | head -1 | tr -d '"')

# Or generate a test token (requires auth service)
# curl -s -X POST http://localhost:8080/auth/debug/token \
#   -H "Content-Type: application/json" \
#   -d '{"sub": "test-user", "email": "test@example.com"}' | jq -r '.access_token'

# Call reporting API with token
curl -s http://localhost:8080/reporting/api/reports \
  -H "Authorization: Bearer $TOKEN" | jq '.count'
# Expected: number > 0
```

#### Without Token (Should Fail)
```bash
curl -s -i http://localhost:8080/reporting/api/reports | head -1
# Expected: HTTP/1.1 401 Unauthorized
```

### Debugging Common Issues

#### Issue: "Preserve log" not showing Callback logs
**Symptom**: Don't see `[Callback]` logs during OAuth redirect

**Solution**:
1. Open DevTools before login
2. Click "Preserve log" checkbox (⚙ button → Preserve log)
3. Then start the OAuth flow

#### Issue: API calls return 401 on reports page
**Symptom**: See `[fetchWithAuth] ... Has token: false`

**Solution**:
1. Check if token is in localStorage:
   - DevTools → Storage → LocalStorage → auth_token
2. Check if Callback was executed:
   - Look for `[Callback]` logs (may need "Preserve log")
3. Ensure UI was rebuilt with latest code:
   ```bash
   docker compose build ui --no-cache
   docker compose restart ui
   ```

#### Issue: Callback component not rendering
**Symptom**: After OAuth redirect, see blank page or error

**Solution**:
1. Check browser console for errors
2. Verify redirect URI in .env and docker-compose:
   - Should be: `AUTH_*_REDIRECT_URI=http://localhost:8080/ui/callback`
3. Check auth service logs:
   ```bash
   docker compose logs auth --tail=50 | grep -i error
   ```

#### Issue: MongoDB role lookup fails
**Symptom**: Logs show "Command find requires authentication"

**Solution**:
1. Verify MongoDB secrets are readable:
   ```bash
   docker exec copilot-for-consensus-auth-1 cat /run/secrets/mongodb_username
   docker exec copilot-for-consensus-auth-1 cat /run/secrets/mongodb_password
   ```
2. Check auth service MongoDB connection:
   ```bash
   docker compose logs auth | grep -i mongodb
   ```

## Performance Expectations

| Operation | Expected Time | Indicator |
|-----------|---------------|-----------|
| OAuth redirect to GitHub | 2-5 seconds | Browser shows GitHub login |
| GitHub authorization | 5-30 seconds | Depends on user, 2FA, etc. |
| Callback processing | <500ms | Quick redirect to /reports |
| Reports page load | 1-3 seconds | API calls fetch data |
| Auth service JWT generation | <100ms | Very fast, local crypto |
| Reporting service auth validation | <10ms | JWKS cached, signature check only |

## Security Considerations

### Development (Current)
✅ Pros:
- Simple implementation
- Works for local testing
- No HTTPS required

❌ Cons:
- localStorage vulnerable to XSS
- Token visible in DevTools
- No CSRF protection
- No cookie SameSite protection

### Production (Future)
- [ ] Migrate to httpOnly Secure cookies
- [ ] Implement CSRF protection (SameSite=Strict)
- [ ] Use HTTPS only
- [ ] Implement token refresh mechanism
- [ ] Add rate limiting
- [ ] Implement PKCE for additional OAuth security
- [ ] Use short-lived access tokens + long-lived refresh tokens

See [AUTH_API_INTEGRATION_FIX.md](AUTH_API_INTEGRATION_FIX.md) for migration notes.

## Token Structure

The JWT token generated by the auth service contains:

```json
{
  "typ": "JWT",
  "alg": "RS256"  // RSA-256 signature, verified via /auth/.well-known/jwks.json
}
.
{
  "sub": "github|username",        // Subject (unique user ID)
  "email": "user@github.com",       // Email from GitHub
  "github_username": "username",    // Username from GitHub
  "role": "user",                   // Role from MongoDB (admin, user, etc.)
  "iat": 1702500000,                // Issued at (unix timestamp)
  "exp": 1702501800                 // Expires in 30 minutes (1800 seconds)
}
.
<RSA256-SIGNATURE>
```

Services validate the token by:
1. Downloading public key from `/auth/.well-known/jwks.json`
2. Verifying RSA signature matches
3. Checking `exp` timestamp hasn't passed
4. Extracting claims (`sub`, `email`, `role`, etc.)

## Next Steps

1. **Current State**: OAuth2 + JWT authentication working end-to-end
2. **Testing**: Follow this guide to verify all layers
3. **Production**: Implement security improvements in "Production (Future)" section
4. **Integration**: Other services should validate tokens using JWKS endpoint
5. **Monitoring**: Add logs to track auth failures and token expiry

## Useful Commands

```bash
# Watch auth service logs during OAuth flow
docker compose logs -f auth --tail=10

# Watch reporting service validating tokens
docker compose logs -f reporting --tail=10

# Watch UI network requests
# Open DevTools → Network tab, then login

# Check JWT signature verification
docker compose logs reporting | grep -i jwt

# View auth service configuration
docker compose exec auth env | grep AUTH_

# Decode JWT token (from browser console)
JSON.parse(atob(localStorage.getItem('auth_token').split('.')[1]))
```
