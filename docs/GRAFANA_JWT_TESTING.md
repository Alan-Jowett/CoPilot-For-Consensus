# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Testing JWT Authentication for Grafana

> Status: Rolled back on Dec 29, 2025 — JWT SSO is temporarily disabled. The testing steps below are deprecated for the current deployment. Use local Grafana admin credentials as a temporary workaround until SSO is re‑implemented.

This document describes how to test the JWT authentication implementation for Grafana.

## Prerequisites

1. Auth service must be running and configured with RSA keys
2. Grafana service must be running
3. API Gateway (nginx) must be running
4. Public key must be extracted from auth service

## Setup Steps

### 1. Start the Required Services

```bash
# Start all infrastructure services
docker compose up -d auth gateway grafana

# Wait for services to be healthy
docker compose ps
```

### 2. Extract Public Key from Auth Service

```bash
# Run the setup script to extract the public key
./scripts/setup_grafana_jwt.sh

# Verify the public key was created
ls -lh secrets/auth_service_public_key.pem

# Verify it's a valid PEM file
openssl pkey -pubin -in secrets/auth_service_public_key.pem -noout -text
```

### 3. Restart Grafana to Pick Up the Public Key

```bash
docker compose restart grafana

# Check Grafana logs for JWT configuration
docker compose logs grafana | grep -i jwt
```

## Testing the Implementation

### Test 1: Verify Public Key Endpoint

```bash
# Check that the public key endpoint is accessible
curl -v http://localhost:8080/auth/.well-known/public_key.pem

# Expected: Returns PEM-formatted public key
# -----BEGIN PUBLIC KEY-----
# ...
# -----END PUBLIC KEY-----
```

### Test 2: Verify JWKS Endpoint

```bash
# Check that the JWKS endpoint returns valid JSON
curl http://localhost:8080/auth/.well-known/jwks.json | jq

# Expected: Returns JWK Set with keys array
# {
#   "keys": [
#     {
#       "kty": "RSA",
#       "use": "sig",
#       "kid": "...",
#       "alg": "RS256",
#       "n": "...",
#       "e": "..."
#     }
#   ]
# }
```

### Test 3: Login and Get JWT Token

```bash
# 1. Open browser and navigate to the UI
open http://localhost:8080/ui/

# 2. Click login and authenticate with OAuth provider

# 3. After authentication, verify both storage mechanisms:

# 3a. Check localStorage for token (used by API calls)
# Open browser console and run:
# localStorage.getItem('auth_token')

# 3b. Check httpOnly cookie (used by browser navigation)
# Open browser DevTools → Application/Storage → Cookies
# Look for 'auth_token' cookie with:
#   - HttpOnly flag set
#   - SameSite=Lax
#   - Path=/

# 4. Decode the token to verify claims (use jwt.io or jwt-decode)
# Expected claims:
# - sub: user ID
# - email: user email
# - name: user name
# - roles: array of roles (e.g., ["admin"])
```

### Test 4: Access Grafana with JWT Token (Cookie-Based SSO)

#### For Admin Users (with 'admin' role in JWT):

```bash
# 1. Login as admin user in the UI
# 2. Look for the "Admin Tools" section in the UI
# 3. Click on "📊 Grafana Dashboards" link
# 4. Verify:
#    - Grafana opens in a new tab
#    - You are automatically logged in (no login page)
#    - You have Admin role (can see Admin menu/gear icon)
#    - You can create/edit dashboards
#
# Behind the scenes:
# - Browser automatically sends auth_token cookie
# - Nginx extracts JWT from cookie
# - Nginx forwards as Authorization: Bearer {token}
# - Grafana validates and auto-logins user
```

#### For Non-Admin Users (without 'admin' role):

```bash
# 1. Login as regular user in the UI
# 2. Verify "Admin Tools" section is NOT visible in the UI
# 3. Manually navigate to http://localhost:8080/grafana/
# 4. Verify:
#    - You are automatically logged in (no login page)
#    - You have Viewer role (cannot edit dashboards)
#    - No Admin menu visible
```

### Test 5: Manual JWT Token Test

```bash
# 1. Get a valid JWT token from the auth service
TOKEN=$(curl -s -X POST http://localhost:8080/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"testuser","password":"testpass"}' | jq -r '.access_token')

# 2. Test accessing Grafana API with JWT
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8080/grafana/api/user

# Expected: Returns user information from JWT claims
# {
#   "id": ...,
#   "email": "user@example.com",
#   "name": "User Name",
#   "login": "user_id",
#   "orgId": 1,
#   "isGrafanaAdmin": true/false  # Based on admin claim
# }
```

### Test 6: Verify Authorization Header Forwarding

```bash
# 1. Start monitoring nginx access logs
docker compose logs -f gateway

# 2. In another terminal, access Grafana with JWT token
curl -H "Authorization: Bearer <token>" \
  http://localhost:8080/grafana/api/user

# 3. Check nginx logs - you should see the request being forwarded
# Expected: Log entry showing request to /grafana/api/user with 200 status
```

## Troubleshooting

### Issue: Grafana returns 401 Unauthorized

**Possible causes:**
1. Public key file not mounted correctly
2. JWT token signature validation failed
3. Token expired

**Solutions:**
```bash
# Verify public key file exists
ls -lh secrets/auth_service_public_key.pem

# Restart Grafana to reload configuration
docker compose restart grafana

# Check Grafana logs for JWT errors
docker compose logs grafana | grep -i "jwt\|unauthorized"
```

### Issue: Admin Tools not visible in UI

**Possible causes:**
1. JWT token doesn't contain 'admin' role
2. Frontend not detecting admin claim correctly

**Solutions:**
```bash
# Decode JWT token to verify roles claim
# In browser console:
# const token = localStorage.getItem('auth_token')
# const decoded = JSON.parse(atob(token.split('.')[1]))
# console.log(decoded.roles)

# Expected: ["admin"] for admin users
```

### Issue: Grafana shows login page instead of auto-login

**Possible causes:**
1. auth_token cookie not set by auth service
2. Cookie not being sent by browser (domain/path mismatch)
3. Nginx not extracting JWT from cookie
4. Grafana JWT configuration incorrect

**Solutions:**
```bash
# 1. Check if cookie is set after login
# In browser DevTools → Application → Cookies
# Look for 'auth_token' cookie at domain of gateway

# 2. Check nginx configuration for cookie extraction
docker compose exec gateway cat /etc/nginx/nginx.conf | grep -A 20 "location /grafana"

# Verify cookie extraction logic (using map directive):
# map $http_authorization $auth_header {
#   "" "Bearer $cookie_auth_token";
#   default $http_authorization;
# }
# proxy_set_header Authorization $auth_header;

# 3. Test cookie extraction manually
# Get auth_token cookie value from browser
# Then test Grafana API:
curl -H "Authorization: Bearer <cookie_value>" \
  http://localhost:8080/grafana/api/user

# Should return user info, not 401

# 4. Check Grafana JWT configuration
docker compose exec grafana env | grep GF_AUTH_JWT

# Expected variables:
# GF_AUTH_JWT_ENABLED=true
# GF_AUTH_JWT_HEADER_NAME=Authorization
# GF_AUTH_JWT_KEY_FILE=/etc/grafana/secrets/auth_service_public_key.pem
```

### Issue: Cookie not sent to Grafana

**Possible causes:**
1. Cookie domain doesn't match
2. Cookie path is incorrect
3. SameSite attribute blocks cookie

**Solutions:**
```bash
# Check cookie attributes in browser DevTools → Application → Cookies
# auth_token cookie should have:
#   - Domain: matches your gateway domain
#   - Path: /
#   - SameSite: Lax (allows top-level navigation)
#   - HttpOnly: true
#   - Secure: false (true in production with HTTPS)

# If cookie is not sent, check browser console for warnings about:
# - Cross-site cookie restrictions
# - SameSite attribute issues
```

## Success Criteria

- ✅ Public key endpoint returns valid PEM
- ✅ JWKS endpoint returns valid JWK Set
- ✅ Auth callback sets JWT in both localStorage and httpOnly cookie
- ✅ Admin users see "Admin Tools" section in UI
- ✅ Non-admin users don't see "Admin Tools" section
- ✅ Admin users can access Grafana with Admin role via link click
- ✅ Non-admin users can access Grafana with Viewer role
- ✅ No separate Grafana login required (seamless SSO)
- ✅ User email and name from JWT shown in Grafana profile

## Security Notes

1. **Public key security:** The public key is safe to expose publicly. Only the private key must be kept secret.

2. **Token validation:** All JWT tokens are validated by Grafana using the public key. Tampering with tokens will cause validation to fail.

3. **Role enforcement:** While the UI hides the Grafana link from non-admin users, Grafana still enforces permissions server-side. Users cannot grant themselves admin access by modifying localStorage.

4. **Token expiry:** JWT tokens expire after the configured time period. Users will need to re-authenticate when their token expires.

5. **Emergency access:** The hardcoded Grafana admin credentials still work as a fallback for emergency access.
