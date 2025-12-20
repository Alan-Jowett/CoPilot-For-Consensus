<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Authentication API Integration Fix

## Problem

After successful OAuth2 authentication and JWT token generation, API requests were returning `401 Unauthorized` even though the token was successfully stored in localStorage and retrieved by the AuthContext. This was caused by a disconnect between token management in different modules.

## Root Cause

The authentication system had **two separate `setAuthToken()` functions** that didn't communicate with each other:

1. **`ui/src/contexts/AuthContext.tsx`**: Exported `setAuthToken(token)` that updates AuthContext state
2. **`ui/src/api.ts`**: Had its own `setAuthToken(token)` function that updates a local `authToken` variable

When the OAuth Callback component completed authentication:
1. It stored the token to localStorage ✓
2. It called `setAuthToken()` from AuthContext ✓
3. But `api.ts`'s local `authToken` variable remained `null` ✗
4. API requests used `api.ts`'s `authToken` variable ✗
5. Result: No Authorization header sent, all API requests returned 401

## Solution

Changed `ui/src/api.ts` to read the token directly from localStorage in the `fetchWithAuth()` function, rather than relying on a state variable that wasn't being properly synchronized.

### Before (Broken)
```typescript
let authToken: string | null = null

function setAuthToken(token: string | null) {
  authToken = token  // Never called from Callback!
}

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {})
  if (authToken) {  // Always null because setAuthToken was never called
    headers.set('Authorization', `Bearer ${authToken}`)
  }
  // ... rest of function
}
```

### After (Fixed)
```typescript
async function fetchWithAuth(url: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers || {})
  
  // Get the token from localStorage (most recent source of truth)
  const token = localStorage.getItem('auth_token')
  console.log('[fetchWithAuth] URL:', url, 'Has token:', !!token)
  
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)  // Now sends the token!
  }

  const response = await fetch(url, { ...options, headers })

  // Handle 401 Unauthorized - redirect to login
  if (response.status === 401) {
    console.log('[fetchWithAuth] Got 401, clearing token and redirecting to login')
    localStorage.removeItem('auth_token')
    const callback = getUnauthorizedCallback()
    if (callback) {
      callback()
    }
    throw new Error('UNAUTHORIZED')
  }

  return response
}
```

## Why This Works

1. **Single Source of Truth**: localStorage is the authoritative store for the auth token
2. **No State Synchronization**: Each API call fetches the current token from localStorage, no need to keep module-level state in sync
3. **Token Lifecycle**: Token is written to localStorage in Callback, read from localStorage in API calls, cleared from localStorage on 401
4. **Immediate Availability**: API calls work even if AuthContext hasn't finished initializing

## Security Implications

⚠️ **Current Implementation (Development Only)**:
- Uses localStorage to store JWT tokens
- Vulnerable to XSS attacks
- Acceptable for local development and protected networks only

🔒 **Production Migration (Future)**:
- Move token storage to httpOnly Secure cookies
- Implement CSRF protection with SameSite attribute
- Add token refresh mechanism
- Consider using dedicated auth libraries (e.g., Auth0, Okta SDKs)

See TODO in `ui/src/routes/Callback.tsx` for migration notes.

## Testing the Fix

### Manual Test Flow

1. **Clear existing state**:
   - Open DevTools (F12)
   - Go to Storage → Cookies → Delete all
   - Go to Application → Storage → localStorage → Clear Site Data

2. **Start OAuth flow**:
   - Navigate to `http://localhost:8080/ui/login`
   - Click "Login with GitHub"
   - Authorize the application
   - Callback should redirect to `/ui/reports`

3. **Verify token was stored**:
   - In DevTools, go to Application → localStorage
   - Should see `auth_token` key with ~700 character JWT value

4. **Verify API calls succeed**:
   - Reports page should load data
   - Console should show `[fetchWithAuth] ... 'Has token': true`
   - API calls should return 200, not 401
   - Console should show reports and sources loaded

### Test Console Logs

Watch the browser console for:

```
[fetchWithAuth] URL: http://localhost:8080/reporting/api/reports?limit=20&skip=0 Has token: true
[fetchWithAuth] URL: http://localhost:8080/reporting/api/sources Has token: true
```

If logs show `Has token: false`, the fix didn't work. Check:
1. Is the token in localStorage? (DevTools → Storage)
2. Was Callback executed? (Look for `[Callback] Storing token...` logs)
3. Is the UI container running the latest build? (Run `docker compose build ui --no-cache`)

## Related Files

- `ui/src/api.ts` - Token injection in API requests (FIXED)
- `ui/src/routes/Callback.tsx` - OAuth callback and token storage (working)
- `ui/src/contexts/AuthContext.tsx` - Token state management (working)
- `auth/app/main.py` - OAuth flows and JWT generation (working)

## Lessons Learned

1. **Module-Level State is Fragile**: When multiple functions in different files rely on shared state, it's easy to break the contract
2. **Prefer Direct Reads**: Reading from a reliable source (localStorage) beats trying to keep module-level variables in sync
3. **Single Responsibility**: AuthContext should manage auth state, API module should just use it
4. **Development vs Production**: localStorage works fine for dev but needs cookies for production

## Future Improvements

- [ ] Migrate from localStorage to httpOnly cookies
- [ ] Add token refresh before expiry
- [ ] Implement PKCE for additional security
- [ ] Add CORS preflight handling
- [ ] Automatic token rotation
- [ ] Rate limiting on auth endpoints
