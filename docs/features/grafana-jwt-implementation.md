# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# JWT Token Authentication for Grafana - Implementation Summary

## Overview

This implementation adds JWT token-based authentication to Grafana, enabling seamless SSO integration with the existing OAuth/OIDC auth service. Users authenticate once via OAuth/OIDC and can access Grafana without a separate login.

## Key Features

1. **Automatic User Authentication**: JWT tokens from the auth service are automatically validated by Grafana
2. **Role-Based Access Control**: Users with 'admin' role in JWT receive Grafana Admin access
3. **Seamless SSO Experience**: No separate Grafana login required
4. **Admin-Only UI Integration**: Grafana link only shown to users with admin role
5. **Backward Compatibility**: Hardcoded admin credentials still work as fallback

## Architecture

```
User Flow:
1. User logs in via OAuth/OIDC → receives JWT token
2. JWT token stored in browser localStorage
3. Browser requests /grafana/ with Authorization header
4. Nginx forwards Authorization header to Grafana
5. Grafana validates JWT using public key
6. User auto-logged-in with role based on JWT claims
```

## Components Modified

### Backend Changes

1. **docker-compose.infra.yml**
   - Added JWT authentication environment variables to Grafana service
   - Configured claim mappings: email, sub (username), name, roles
   - Added volume mount for public key file
   - Enabled auto-sign-up and admin role assignment

2. **infra/nginx/nginx.conf**
   - Added `proxy_set_header Authorization $http_authorization;` to forward JWT
   - Updated both HTTP and HTTPS server blocks

3. **auth/main.py**
   - Added `GET /.well-known/public_key.pem` endpoint
   - Added `GET /.well-known/jwks.json` endpoint (OIDC standard)
   - Both endpoints expose public key for external validation

4. **adapters/copilot_auth/copilot_auth/jwt_manager.py**
   - Added `get_public_key_pem()` method to export public key in PEM format

5. **scripts/setup_grafana_jwt.sh**
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
   - Opens Grafana in new tab with Authorization header

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

### Potential Risks & Mitigations

⚠️ **Token Theft**: If JWT token is stolen, attacker has access until expiry
   - **Mitigation**: Use short-lived tokens (30 minutes default)
   - **Mitigation**: Implement token refresh mechanism
   - **Mitigation**: Use HTTPS (already implemented)

⚠️ **Key Rotation**: If private key is compromised, all tokens become invalid
   - **Mitigation**: Implement key rotation mechanism with multiple key IDs
   - **Mitigation**: Monitor auth service logs for suspicious activity
   - **Mitigation**: Use Azure Key Vault in production (recommended)

⚠️ **XSS Attacks**: Could steal token from localStorage
   - **Mitigation**: Strict CSP headers (should be added)
   - **Mitigation**: Input sanitization in UI
   - **Mitigation**: Consider httpOnly cookies in production

## Configuration Reference

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

## Troubleshooting

See `docs/GRAFANA_JWT_TESTING.md` for detailed troubleshooting steps.

Common issues:
- Public key file not mounted → Run setup script
- 401 Unauthorized → Check Grafana logs for JWT validation errors
- Admin Tools not visible → Verify JWT contains 'admin' role
- Login page shown → Verify Authorization header forwarding in nginx

## Future Enhancements

1. **Token Refresh**: Implement automatic token refresh before expiry
2. **Key Rotation**: Support multiple key IDs for zero-downtime key rotation
3. **CSP Headers**: Add strict Content Security Policy headers
4. **HttpOnly Cookies**: Consider using httpOnly cookies instead of localStorage
5. **Audit Logging**: Log all Grafana access attempts with user info
6. **Custom Roles**: Map more granular roles from JWT to Grafana permissions
7. **JWKS Auto-Update**: Automatically update public key from JWKS endpoint

## References

- [Grafana JWT Authentication Docs](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#jwt-authentication)
- [RFC 7519 - JSON Web Token (JWT)](https://tools.ietf.org/html/rfc7519)
- [RFC 7517 - JSON Web Key (JWK)](https://tools.ietf.org/html/rfc7517)
- [OIDC Discovery - Well-Known Endpoints](https://openid.net/specs/openid-connect-discovery-1_0.html)

## Related Issues

- Issue #[number]: Add JWT Token Authentication to Grafana
- Issue #560: Token Refresh on 403
- Issue #554: Auth Env Var Fix
