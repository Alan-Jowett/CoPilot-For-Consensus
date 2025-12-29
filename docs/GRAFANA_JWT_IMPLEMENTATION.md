# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# JWT Token Authentication for Grafana - Implementation Summary

> Status: Rolled back on Dec 29, 2025 — JWT SSO is temporarily disabled. Grafana currently uses local admin authentication via Docker secrets. This document remains for reference and future re‑implementation plans (e.g., auth_proxy or cookie-based SSO).

## Overview

This implementation adds JWT token-based authentication to Grafana, enabling seamless SSO integration with the existing OAuth/OIDC auth service. Users authenticate once via OAuth/OIDC and can access Grafana without a separate login, including when clicking Grafana links in the UI.

## Key Features

1. **Automatic User Authentication**: JWT tokens from the auth service are automatically validated by Grafana
2. **Role-Based Access Control**: Users with 'admin' role in JWT receive Grafana Admin access
3. **Seamless SSO Experience**: No separate Grafana login required, works with browser link navigation
4. **Cookie-Based Authentication**: JWT stored in httpOnly cookie enables SSO via regular HTML links
5. **Admin-Only UI Integration**: Grafana link only shown to users with admin role
6. **Backward Compatibility**: Hardcoded admin credentials still work as fallback

## Architecture

```
User Flow (with Cookie-Based SSO):
1. User logs in via OAuth/OIDC → receives JWT token
2. Auth service sets JWT in:
   - Response body (for localStorage storage by UI)
   - httpOnly cookie (for automatic browser inclusion)
3. When user clicks Grafana link:
   - Browser automatically sends auth_token cookie
   - Nginx extracts JWT from cookie
   - Nginx forwards JWT as Authorization header to Grafana
4. Grafana validates JWT using public key
5. User auto-logged-in with role based on JWT claims
```

## Components Modified

### Backend Changes

1. **auth/main.py**
   - Modified `/callback` endpoint to set JWT in httpOnly cookie
   - Added `/logout` endpoint to clear auth cookie
   - Cookie settings: httpOnly, samesite=lax, path=/, secure flag for production
   - Added `GET /.well-known/public_key.pem` endpoint
   - Added `GET /.well-known/jwks.json` endpoint (OIDC standard)

2. **infra/nginx/nginx.conf**
   - Updated `/grafana/` location to extract JWT from cookie when Authorization header is absent
   - Priority: Authorization header (API calls) → auth_token cookie (browser navigation)
   - Format: "Bearer $cookie_auth_token" forwarded to Grafana
   - Updated both HTTP and HTTPS server blocks

3. **docker-compose.infra.yml**
   - Grafana configured with JWT authentication environment variables
   - Configured claim mappings: email, sub (username), name, roles
   - Added volume mount for public key file
   - Enabled auto-sign-up and admin role assignment

4. **scripts/setup_grafana_jwt.sh**
   - Automated script to extract public key from auth service
   - Validates key is valid PEM format
   - Creates secrets/auth_service_public_key.pem

### Frontend Changes

1. **ui/package.json**
   - Added `jwt-decode` dependency for token parsing

2. **ui/src/contexts/AuthContext.tsx**
   - Added `isAdmin` state to context
   - Added `isUserAdmin()` function to check for 'admin' role in JWT
   - Optimized initialization to avoid duplicate localStorage reads

3. **ui/src/components/AdminLinks.tsx**
   - New component displaying Grafana link for admin users
   - Simple HTML link (`<a href="/grafana/">`) works with cookie-based SSO
   - No JavaScript required to add Authorization headers

4. **ui/src/components/AdminLinks.module.css**
   - Styling for admin tools section

5. **ui/src/ui/AppLayout.tsx**
   - Integrated AdminLinks component in main layout

### Testing & Documentation

1. **auth/tests/test_public_key_endpoints.py**
   - Tests for new public key endpoints
   - Validates PEM format and JWKS structure

2. **docs/GRAFANA_JWT_TESTING.md**
   - Comprehensive testing guide
   - Troubleshooting steps
   - Security considerations

## Security Considerations

### What's Secure

✅ **Public Key Exposure**: Safe to expose publicly; only private key must be kept secret
✅ **Token Validation**: All JWT tokens validated using cryptographic signatures
✅ **Server-Side Enforcement**: Grafana enforces permissions regardless of UI state
✅ **Defense in Depth**: Frontend hides links, but backend still validates tokens
✅ **Token Expiry**: JWT tokens expire after configured time period
✅ **Emergency Access**: Hardcoded admin credentials still work as fallback
✅ **HttpOnly Cookies**: JWT stored in httpOnly cookie prevents XSS access to token
✅ **Cookie Attributes**: SameSite=lax prevents CSRF attacks while allowing navigation

### Potential Risks & Mitigations

⚠️ **Token Theft**: If JWT token is stolen, attacker has access until expiry
   - **Mitigation**: Use short-lived tokens (30 minutes default)
   - **Mitigation**: Implement token refresh mechanism
   - **Mitigation**: Use HTTPS (already implemented)
   - **Mitigation**: HttpOnly cookie prevents XSS-based theft

⚠️ **Key Rotation**: If private key is compromised, all tokens become invalid
   - **Mitigation**: Implement key rotation mechanism with multiple key IDs
   - **Mitigation**: Monitor auth service logs for suspicious activity
   - **Mitigation**: Use Azure Key Vault in production (recommended)

⚠️ **XSS Attacks**: Could steal token from localStorage (but not from httpOnly cookie)
   - **Mitigation**: HttpOnly cookie prevents JavaScript access
   - **Mitigation**: Strict CSP headers (should be added)
   - **Mitigation**: Input sanitization in UI
   - **Mitigation**: Consider httpOnly cookies in production

## Configuration Reference

### Auth Service Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `COOKIE_SECURE` | `false` (default), `true` | Enable secure flag on cookies (requires HTTPS) |

**Note**: Set `COOKIE_SECURE=true` in production deployments with HTTPS to ensure cookies are only sent over encrypted connections.

### Grafana JWT Environment Variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `GF_AUTH_JWT_ENABLED` | `true` | Enable JWT authentication |
| `GF_AUTH_JWT_HEADER_NAME` | `Authorization` | HTTP header containing JWT |
| `GF_AUTH_JWT_EMAIL_CLAIM` | `email` | JWT claim for email |
| `GF_AUTH_JWT_USERNAME_CLAIM` | `sub` | JWT claim for username |
| `GF_AUTH_JWT_NAME_CLAIM` | `name` | JWT claim for display name |
| `GF_AUTH_JWT_ROLE_ATTRIBUTE_PATH` | `contains(roles[*], 'admin')` | Admin role check |
| `GF_AUTH_JWT_KEY_FILE` | `/etc/grafana/secrets/auth_service_public_key.pem` | Public key location |
| `GF_AUTH_JWT_AUTO_SIGN_UP` | `true` | Auto-create users |
| `GF_AUTH_JWT_ALLOW_ASSIGN_GRAFANA_ADMIN` | `true` | Allow admin role assignment |
| `GF_USERS_AUTO_ASSIGN_ORG_ROLE` | `Viewer` | Default role for non-admins |

## Setup Instructions

### 1. Generate JWT Keys (if not already done)

```bash
cd auth
python generate_keys.py
```

### 2. Start Services

```bash
docker compose up -d auth gateway grafana
```

### 3. Extract Public Key

```bash
./scripts/setup_grafana_jwt.sh
```

### 4. Restart Grafana

```bash
docker compose restart grafana
```

### 5. Verify Installation

```bash
# Check public key endpoint
curl http://localhost:8080/auth/.well-known/public_key.pem

# Check JWKS endpoint
curl http://localhost:8080/auth/.well-known/jwks.json | jq

# Login to UI and look for "Admin Tools" section
open http://localhost:8080/ui/
```

## Success Criteria

All criteria met:

- ✅ Grafana accepts JWT tokens from Authorization header
- ✅ JWT signature validated using public key from auth service
- ✅ User auto-created/updated in Grafana from JWT claims
- ✅ Admin role in JWT grants Grafana Admin access
- ✅ Non-admin users get Viewer role
- ✅ No separate Grafana login required (seamless SSO)
- ✅ Email and name from JWT shown in Grafana user profile
- ✅ Works with RSA256 JWT algorithm
- ✅ Public key endpoint available from auth service
- ✅ Nginx properly forwards Authorization header
- ✅ All existing functionality preserved
- ✅ Fallback to hardcoded credentials works
- ✅ No security vulnerabilities detected (CodeQL passed)

## Solution Approach: Cookie-Based JWT for Browser Navigation

The original implementation attempted to use Authorization headers for Grafana SSO, but this approach fails when users click regular HTML links because browsers cannot send custom headers during standard navigation.

**Problem**: The `<a href="/grafana/">` link in AdminLinks.tsx opened Grafana in a new tab, but the browser made a standard GET request without the Authorization header from localStorage.

**Solution**: We implemented a hybrid cookie + header approach:
1. Auth service `/callback` endpoint now sets JWT in both:
   - Response body (for localStorage, used by API calls)
   - httpOnly cookie (automatically sent by browser)
2. Nginx extracts JWT from cookie when Authorization header is absent
3. Nginx forwards JWT to Grafana as "Bearer {token}" in Authorization header
4. Grafana validates JWT using its existing configuration (no changes needed)

**Benefits**:
- ✅ Works with regular HTML links (browser sends cookies automatically)
- ✅ Works with API calls (explicit Authorization header takes precedence)
- ✅ Improved security (httpOnly cookie prevents XSS token theft)
- ✅ Minimal changes (no Grafana config changes, simple nginx logic)
- ✅ No client-side JavaScript needed for SSO

**Alternative Approaches Considered** (see issue for details):
- Auth Proxy mode: Would require JWT validation in nginx (complex)
- Anonymous + JWT upgrade: Would show login page briefly (poor UX)
- iframe embedding: Complex and restricted by security policies
- Cookie-only: Would require changing all API calls (breaking change)

## Troubleshooting

See `docs/GRAFANA_JWT_TESTING.md` for detailed troubleshooting steps.

Common issues:
- Public key file not mounted → Run setup script
- 401 Unauthorized → Check Grafana logs for JWT validation errors
- Admin Tools not visible → Verify JWT contains 'admin' role
- Login page shown → Check if auth_token cookie is set, verify nginx cookie extraction
- Cookie not sent → Check cookie domain/path settings, ensure same-origin

## Future Enhancements

1. **Token Refresh**: Implement automatic token refresh before expiry
2. **Key Rotation**: Support multiple key IDs for zero-downtime key rotation
3. **CSP Headers**: Add strict Content Security Policy headers
4. **Audit Logging**: Log all Grafana access attempts with user info
5. **Custom Roles**: Map more granular roles from JWT to Grafana permissions
6. **JWKS Auto-Update**: Automatically update public key from JWKS endpoint

**Note**: Cookie secure flag support has been implemented via the `COOKIE_SECURE` environment variable.

## References

- [Grafana JWT Authentication Docs](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#jwt-authentication)
- [RFC 7519 - JSON Web Token (JWT)](https://tools.ietf.org/html/rfc7519)
- [RFC 7517 - JSON Web Key (JWK)](https://tools.ietf.org/html/rfc7517)
- [OIDC Discovery - Well-Known Endpoints](https://openid.net/specs/openid-connect-discovery-1_0.html)

## Related Issues

- Issue #[number]: Add JWT Token Authentication to Grafana
- Issue #560: Token Refresh on 403
- Issue #554: Auth Env Var Fix
