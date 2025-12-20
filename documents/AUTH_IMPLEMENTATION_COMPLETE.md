<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# OAuth2 + JWT Authentication - Complete Implementation Guide

## Quick Start

### System Status
✅ **All systems operational and ready for testing**

### Verify System is Running
```bash
# Check all services are healthy
docker compose ps | grep -E "auth|reporting|ui|gateway"

# Quick health check
curl http://localhost:8080/auth/health
curl http://localhost:8080/ui/ | head -c 20
```

### Test OAuth Flow
1. Navigate to: **[http://localhost:8080/ui/login](http://localhost:8080/ui/login)**
2. Click **"Login with GitHub"**
3. Authorize the application when prompted
4. Should be redirected to **[http://localhost:8080/ui/reports](http://localhost:8080/ui/reports)**
5. Reports and sources tables should load with data
6. Open DevTools (F12) → Console to see auth logs

### Expected Console Logs
```
[AuthContext] Initialized from localStorage: true
[fetchWithAuth] URL: http://localhost:8080/reporting/api/reports Has token: true
[fetchWithAuth] URL: http://localhost:8080/reporting/api/sources Has token: true
```

If you see `Has token: false`, the fix hasn't been applied correctly. Rebuild UI:
```bash
docker compose build ui --no-cache
docker compose restart ui
```

## Documentation Map

### For Different Audiences

**Want to test the OAuth flow?**
→ Read: [OAUTH_TESTING_GUIDE.md](documents/OAUTH_TESTING_GUIDE.md)
- Complete manual testing walkthrough
- Console log verification steps
- Debugging common issues
- Performance expectations

**Want to understand the authentication architecture?**
→ Read: [ARCHITECTURE.md](documents/ARCHITECTURE.md)
- System design overview
- Component interactions
- Security architecture
- Token flow diagrams

**Want to understand what was fixed in this session?**
→ Read: [AUTH_API_INTEGRATION_FIX.md](documents/AUTH_API_INTEGRATION_FIX.md)
- Detailed explanation of the bug
- Root cause analysis
- Solution explanation
- Security implications

**Want the complete implementation history?**
→ Read: [AUTH_IMPLEMENTATION_SUMMARY.md](documents/AUTH_IMPLEMENTATION_SUMMARY.md)
- Phase 1: Auth Adapter
- Phase 2: Auth Microservice
- Phase 3: React UI Integration
- Production considerations

**Want code examples?**
→ Read: [AUTH_INTEGRATION_EXAMPLES.md](documents/AUTH_INTEGRATION_EXAMPLES.md)
- Code snippets for using the auth system
- API examples
- Configuration examples

**Want to set up local testing?**
→ Read: [OIDC_LOCAL_TESTING.md](documents/OIDC_LOCAL_TESTING.md)
- Local development setup
- OAuth provider configuration
- Testing procedures

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────┐
│                  Browser / React SPA                     │
│  http://localhost:8080/ui                              │
│                                                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ [Login] → GitHub OAuth → [Callback] → [Reports]  │  │
│  │           (extract token)                         │  │
│  │           (store to localStorage)                 │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                  │
│            API Calls with Authorization Header           │
│            (read from localStorage in fetchWithAuth)     │
└─────────────────────────────────────────────────────────┘
                        ↓
         ┌──────────────────────────────┐
         │   Nginx API Gateway          │
         │   http://localhost:8080      │
         ├──────────────────────────────┤
         │  /ui/         → React App    │
         │  /auth/       → Auth Service │
         │  /reporting/  → Reporting API│
         └─────────────┬────────────────┘
                       ↓
      ┌────────────────────────────────┐
      │    Docker Network (default)    │
      ├────────┬──────────┬────────────┤
      │ Auth   │Reporting │  MongoDB   │
      │Service │ Service  │  (roles)   │
      └────────┴──────────┴────────────┘
```

## Key Files & Their Responsibilities

### Frontend (React)
| File | Purpose |
|------|---------|
| `ui/src/routes/Login.tsx` | Login UI with OAuth provider buttons |
| `ui/src/routes/Callback.tsx` | OAuth callback handler, token extraction & storage |
| `ui/src/contexts/AuthContext.tsx` | Token state management, useAuth() hook |
| `ui/src/api.ts` | API client with Authorization header injection (CRITICAL FIX) |
| `ui/src/main.tsx` | React Router setup with `/ui` basename |

### Backend Services
| File | Purpose |
|------|---------|
| `auth/main.py` | OAuth endpoints and JWT generation |
| `auth/app/service.py` | AuthService orchestrating OIDC flows |
| `auth/app/role_store.py` | MongoDB integration for user roles |
| `auth/app/config.py` | Configuration management |

### Infrastructure
| File | Purpose |
|------|---------|
| `docker-compose.services.yml` | Service configuration (OAuth URIs, secrets) |
| `.env` | Environment overrides (OAuth config) |
| `docker-compose.yml` | Main compose file |

## Critical Fixes Applied

### 1. API Token Injection Fix ✅
**File**: `ui/src/api.ts`
**What Was Wrong**: Authorization header wasn't being sent with API requests despite token being stored
**Why**: Two separate `setAuthToken()` functions (AuthContext vs api.ts) weren't synchronized
**How Fixed**: Changed `fetchWithAuth()` to read token directly from localStorage
**Commit**: `6dccadc`

### 2. OAuth Redirect URI Configuration ✅
**Files**: `docker-compose.services.yml`, `.env`
**What Was Wrong**: Redirect URIs pointing to `/auth/callback` instead of `/ui/callback`
**Why**: React app is served at `/ui/` subpath
**How Fixed**: Updated all `AUTH_*_REDIRECT_URI` values to point to `/ui/callback`
**Commits**: `d3d5ec5`, `31be0ad`

### 3. MongoDB Credentials Reading ✅
**File**: `auth/app/role_store.py`
**What Was Wrong**: Auth service couldn't connect to MongoDB
**Why**: Credentials were in Docker secrets files, but code was reading from env vars
**How Fixed**: Implemented `get_secret_or_env()` helper to read from `/run/secrets/` with fallback to env vars
**Commit**: `8c15602`

### 4. React Router Subpath Configuration ✅
**File**: `ui/src/main.tsx`
**What Was Wrong**: React Router routes didn't work when serving from `/ui/` subpath
**Why**: React Router needs `basename` to match the subpath
**How Fixed**: Added `basename: '/ui'` to router configuration
**Commit**: `54b1cd1`

## Verification Checklist

- [x] Auth service health: `curl http://localhost:8080/auth/health`
- [x] JWKS endpoint: `curl http://localhost:8080/auth/keys`
- [x] UI service: `curl http://localhost:8080/ui/`
- [x] API requires auth: `curl http://localhost:8080/reporting/api/reports` (returns 401)
- [x] Docker secrets readable: Auth service MongoDB connection works
- [x] OAuth redirect URIs: All point to `/ui/callback`
- [x] Token injection: API calls include Authorization header
- [x] Token storage: localStorage has ~700 char JWT
- [x] Token retrieval: AuthContext initializes from localStorage
- [x] API calls: Return 200 with data when token present

## Common Tasks

### Test OAuth Flow
```bash
# Follow guide at http://localhost:8080/ui/login
# See documents/OAUTH_TESTING_GUIDE.md for detailed steps
```

### Check Auth Service Logs
```bash
docker compose logs -f auth --tail=20
```

### Check JWT Token in Browser
```javascript
// In browser console:
const token = localStorage.getItem('auth_token')
console.log('Token length:', token.length)
console.log('Token payload:', JSON.parse(atob(token.split('.')[1])))
```

### Clear Auth State
```javascript
// In browser console:
localStorage.removeItem('auth_token')
location.href = '/ui/login'
```

### Rebuild UI with Latest Code
```bash
docker compose build ui --no-cache
docker compose restart ui
```

### Test API with Token
```bash
# Get a token (requires manual OAuth flow or admin endpoint)
TOKEN=$(curl -s http://localhost:8080/auth/debug/token \
  -H "Content-Type: application/json" \
  -d '{"sub": "test-user", "email": "test@example.com"}' | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

# Use token in API call
curl http://localhost:8080/reporting/api/reports \
  -H "Authorization: Bearer $TOKEN"
```

## Security Status

### ✅ Current Implementation (Safe for Local Development)
- JWT validation working with RS256 signature
- OAuth redirect URIs properly configured
- MongoDB role storage functional
- Role-based access control via JWT claims
- Console logging for debugging

### ⚠️ Not Yet Implemented (Required for Production)
- [ ] httpOnly Secure cookies (instead of localStorage)
- [ ] CSRF protection (SameSite attribute)
- [ ] Token refresh mechanism
- [ ] PKCE for OAuth
- [ ] Rate limiting on auth endpoints
- [ ] Automated key rotation
- [ ] Redis session storage
- [ ] Audit logging

See [AUTH_API_INTEGRATION_FIX.md](documents/AUTH_API_INTEGRATION_FIX.md) for production migration roadmap.

## Troubleshooting

### Issue: Browser shows blank page after OAuth redirect
**Solution**:
1. Check browser console for errors (F12)
2. Verify redirect URI in browser URL starts with `/ui/callback`
3. Check auth service logs: `docker compose logs auth | grep -i callback`

### Issue: API calls return 401 even with token
**Solution**:
1. Verify token in localStorage: `localStorage.getItem('auth_token')` (should have value)
2. Check console logs show "Has token: true" in fetchWithAuth
3. Rebuild UI: `docker compose build ui --no-cache && docker compose restart ui`

### Issue: Can't see OAuth callback logs
**Solution**:
1. Open DevTools BEFORE clicking login
2. Enable "Preserve log" in console (⚙ → Preserve log)
3. Then start OAuth flow
4. Logs will persist even through redirect

### Issue: MongoDB connection errors
**Solution**:
1. Verify secrets are readable: `docker exec copilot-for-consensus-auth-1 ls -la /run/secrets/`
2. Check MongoDB is running: `docker compose ps documentdb`
3. Verify credentials: `docker exec copilot-for-consensus-auth-1 cat /run/secrets/mongodb_username`

## Performance Baseline

| Operation | Expected Time |
|-----------|----------------|
| OAuth redirect to GitHub | 2-5 seconds |
| GitHub authorization | 5-30 seconds (user dependent) |
| Callback token exchange | <500ms |
| Reports page load | 1-3 seconds |
| JWT generation | <100ms |
| JWT validation | <10ms |
| API call overhead | <50ms |

## Next Session Tasks

### High Priority
1. [ ] Test OAuth flow with all three providers (GitHub, Google, Microsoft)
2. [ ] Verify role-based access control works
3. [ ] Test token expiry and redirect to login

### Medium Priority
1. [ ] Implement token refresh mechanism
2. [ ] Add PKCE support to OAuth
3. [ ] Create admin panel for role management

### Low Priority
1. [ ] Migrate localStorage to httpOnly cookies
2. [ ] Implement Redis session storage
3. [ ] Add detailed audit logging

## Useful References

- **JWT Tokens**: https://jwt.io (decode tokens here)
- **OAuth 2.0 Spec**: https://datatracker.ietf.org/doc/html/rfc6749
- **OpenID Connect**: https://openid.net/specs/openid-connect-core-1_0.html
- **FastAPI Security**: https://fastapi.tiangolo.com/tutorial/security/
- **React Auth Patterns**: https://developer.okta.com/docs/guides/sign-into-spa/

## Support

For issues or questions:
1. Check the relevant documentation in `documents/`
2. Review the troubleshooting section above
3. Check service logs: `docker compose logs <service_name>`
4. Enable debugging: Set detailed console logging and check browser DevTools

---

**Status**: 🟢 **READY FOR TESTING**  
**Last Updated**: 2025-12-19  
**Branch**: `copilot/integrate-microservices-auth-model`
