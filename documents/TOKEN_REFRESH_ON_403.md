# Automatic Token Refresh on 403 (Permission Changes)

## Overview

This document describes the automatic JWT token refresh mechanism that transparently handles permission updates when users encounter 403 (Forbidden) responses due to stale permission claims after role assignment.

## Problem Statement

### Without Token Refresh
1. User logs in with JWT token containing role claims (e.g., `[user]`)
2. Admin assigns new role (e.g., `analyst`) to the user
3. User makes API request with stale token → server returns 403 Forbidden
4. **User must manually logout and login** to get new token with updated claims
5. Disruptive user experience, loss of context

### With Token Refresh
1. User logs in with JWT containing initial role claims
2. Admin assigns new role
3. User makes API request with stale token → gets 403
4. **System automatically and transparently initiates token refresh**
5. New token obtained with updated role claims
6. **Original page context preserved**
7. User continues without interruption

## Architecture

### High-Level Flow

```
User Request (with stale token)
    ↓
API returns 403 Forbidden
    ↓
fetchWithAuth() detects 403
    ↓
First-time 403 check passes? → YES
    ↓
Save current URL to sessionStorage
    ↓
Redirect to OAuth: /auth/login?redirect_uri=.../callback?refresh=true
    ↓
User silently re-authenticates (if needed)
    ↓
OAuth callback: Callback.tsx detects refresh=true
    ↓
Retrieve original page location from sessionStorage
    ↓
Redirect back to original page with new token
    ↓
User has new token with updated role claims
    ↓
Original request can now succeed
```

### Key Components

#### 1. API Handler: `ui/src/api.ts`

**Global Variables:**
- `lastRefreshToken`: Tracks the last token used for refresh to prevent loops

**fetchWithAuth() Enhancement:**
- Detects 403 responses
- Checks if refresh already attempted for this request
- Checks if token was already refreshed (loop prevention)
- Stores current URL in sessionStorage
- Redirects to OAuth with `refresh=true` parameter
- Comprehensive console logging

**Code Structure:**
```typescript
let lastRefreshToken: string | null = null

async function fetchWithAuth(url: string, options: RequestInit = {}) {
  // ... existing auth logic ...
  
  if (response.status === 403) {
    const attemptedRefresh = (options as any)._attemptedRefresh === true
    const currentToken = localStorage.getItem('auth_token')
    const tokenAlreadyRefreshed = currentToken === lastRefreshToken && lastRefreshToken !== null
    
    if (!attemptedRefresh && !tokenAlreadyRefreshed) {
      // First 403 - attempt refresh
      lastRefreshToken = currentToken
      await new Promise(resolve => setTimeout(resolve, 500))
      sessionStorage.setItem('postLoginUrl', window.location.pathname + window.location.search)
      
      const redirectUri = `${window.location.origin}${import.meta.env.BASE_URL}callback?refresh=true`
      const loginUrl = `/auth/login?provider=github&aud=copilot-for-consensus&redirect_uri=${encodeURIComponent(redirectUri)}`
      window.location.href = loginUrl
      
      throw new Error('TOKEN_REFRESH_IN_PROGRESS')
    }
    // Second 403 with same token - user lacks permission
  }
  
  return response
}
```

#### 2. OAuth Callback: `ui/src/routes/Callback.tsx`

**Token Storage Enhancement:**
- Detects `refresh=true` URL parameter
- Retrieves original page location from sessionStorage
- Redirects to original page or fallback to `/ui/reports`
- Cleans up sessionStorage after use

**Code Structure:**
```typescript
// Check if this is a token refresh (automatic permission re-sync)
const isRefresh = searchParams.get('refresh') === 'true'
let redirectUrl = '/ui/reports'

if (isRefresh) {
  // Return to original page
  const postLoginUrl = sessionStorage.getItem('postLoginUrl')
  if (postLoginUrl) {
    redirectUrl = postLoginUrl
    sessionStorage.removeItem('postLoginUrl')
    console.log('[Callback] Token refreshed, returning to:', redirectUrl)
  } else {
    console.log('[Callback] Token refreshed, location lost, using default')
  }
} else {
  console.log('[Callback] Normal login, redirecting to reports')
}

window.location.href = redirectUrl
```

## Loop Prevention

The implementation prevents infinite loops through two mechanisms:

### 1. Per-Request Prevention
**Mechanism:** `_attemptedRefresh` flag
- Prevents multiple refresh attempts for the same API call
- Each request tracked independently

**Example:**
```typescript
const attemptedRefresh = (options as any)._attemptedRefresh === true
if (!attemptedRefresh) {
  // Attempt refresh
}
```

### 2. Cross-Page Prevention
**Mechanism:** `lastRefreshToken` global variable
- Tracks the token used for last refresh attempt
- Compares with current token after page reload
- Detects if server issued new token with updated claims

**Example Scenarios:**

**Scenario 1: Role Successfully Assigned**
```
First 403:
  currentToken = "tokenA"
  lastRefreshToken = null
  → Trigger refresh, set lastRefreshToken = "tokenA"

After OAuth:
  Server issues new token: "tokenB" (different from A)
  
Page Reload:
  currentToken = "tokenB"
  lastRefreshToken = "tokenA"
  Check: "tokenB" === "tokenA"? NO
  → Allow refresh if another 403 occurs ✓
```

**Scenario 2: Role NOT Assigned (No Loop)**
```
First 403:
  currentToken = "tokenA"
  lastRefreshToken = null
  → Trigger refresh, set lastRefreshToken = "tokenA"

After OAuth:
  Server issues same token: "tokenA" (no new roles)
  
Page Reload:
  currentToken = "tokenA"
  lastRefreshToken = "tokenA"
  Check: "tokenA" === "tokenA"? YES
  → Block refresh, return 403 to user ✓
```

## Console Logging

The implementation includes comprehensive console logging for debugging:

### Successful Refresh Flow
```
[fetchWithAuth] Got 403 Forbidden, user may need permission refresh
[fetchWithAuth] First 403, attempting token refresh
[fetchWithAuth] Waiting 500ms before refresh...
[fetchWithAuth] Redirecting to refresh login flow
[Callback] Token refreshed, returning to: /ui/reports/abc123
[Callback] Redirecting to /ui/reports/abc123
```

### Loop Prevention (Token Already Refreshed)
```
[fetchWithAuth] Got 403 Forbidden, user may need permission refresh
[fetchWithAuth] Token already refreshed, still 403 - user lacks permission
```

### Loop Prevention (Request Already Attempted)
```
[fetchWithAuth] Got 403 Forbidden, user may need permission refresh
[fetchWithAuth] Already attempted refresh for this request
```

## Manual Testing Guide

### Test 1: Basic Token Refresh
**Objective:** Verify automatic refresh works when role assigned

**Steps:**
1. Login as user (role: `user`)
2. Have admin assign role `analyst` via Admin UI
3. Navigate to a page requiring `analyst` role
4. **Expected:** Automatic redirect to OAuth → return to page with new token
5. **Verify:** Console shows refresh flow messages
6. **Verify:** Page loads successfully with new permissions

### Test 2: Loop Prevention
**Objective:** Verify no infinite loop when permission truly denied

**Steps:**
1. Login as user (role: `user`)
2. Navigate to a page requiring `admin` role (without being granted it)
3. **Expected:** First 403 triggers refresh attempt
4. **Expected:** After OAuth, still 403 (user still lacks `admin` role)
5. **Expected:** Second 403 is blocked, no additional redirect
6. **Verify:** Console shows "Token already refreshed, still 403"
7. **Verify:** User sees permission error, not stuck in loop

### Test 3: URL Preservation
**Objective:** Verify original page context preserved

**Steps:**
1. Login as user
2. Navigate to complex URL: `/ui/reports?thread_id=abc&page=2`
3. Have admin assign new role
4. Trigger 403 (e.g., click action requiring new role)
5. **Expected:** Automatic redirect to OAuth
6. **Expected:** Return to exact same URL with query params
7. **Verify:** URL is `/ui/reports?thread_id=abc&page=2`

### Test 4: Token Claims Verification
**Objective:** Verify JWT token actually updated

**Steps:**
1. Login as user, decode JWT token (use jwt.io)
2. Note roles in token claims (e.g., `["user"]`)
3. Have admin assign role `analyst`
4. Trigger 403 and let automatic refresh complete
5. Decode new JWT token from localStorage
6. **Expected:** Roles now include `["user", "analyst"]`

### Test 5: Logout During Refresh
**Objective:** Verify logout works during OAuth flow

**Steps:**
1. Login as user
2. Trigger 403 and automatic refresh
3. **Before OAuth completes**, click Logout button
4. **Expected:** Logout works normally
5. **Expected:** No stuck state or errors

## Edge Cases Handled

1. **Multiple 403s in quick succession**
   - Each request blocked independently by `attemptedRefresh` flag
   - No multiple redirects

2. **User logout during refresh**
   - Logout clears localStorage and token state
   - No stuck state, works normally

3. **Session loss during OAuth**
   - postLoginUrl not found in sessionStorage
   - Falls back to `/ui/reports`
   - User can manually navigate

4. **Page refresh during OAuth**
   - OAuth callback completes normally
   - sessionStorage persists across refresh

5. **Complex URLs with query params**
   - Full URL preserved: `pathname + search`
   - Query params restored correctly

6. **Concurrent requests with 403**
   - Each request handled independently
   - Single OAuth redirect triggered

7. **True permission denial**
   - No infinite loop
   - Clear console message
   - User sees permission error

## Security Considerations

1. **Token Storage**
   - Currently uses localStorage (acceptable for development)
   - Production: Consider httpOnly Secure cookies
   - See TODO comment in Callback.tsx

2. **OAuth Flow**
   - Standard OAuth 2.0 authorization code flow
   - State parameter for CSRF protection
   - Redirect URI validation by auth service

3. **Session Storage**
   - Used for temporary URL preservation
   - Cleared after successful redirect
   - Not accessible across origins

4. **Token Refresh Tracking**
   - In-memory variable (not persisted)
   - Cleared on page refresh (intentional)
   - No sensitive data stored

## Troubleshooting

### Issue: Refresh loops infinitely
**Cause:** lastRefreshToken not being set correctly
**Check:** Console logs for "Token already refreshed" message
**Fix:** Verify localStorage.getItem('auth_token') returns correct token

### Issue: Original URL lost after refresh
**Cause:** sessionStorage cleared before redirect
**Check:** sessionStorage.getItem('postLoginUrl') before OAuth
**Fix:** Verify sessionStorage.setItem() called before redirect

### Issue: 403 but no refresh triggered
**Cause:** attemptedRefresh flag set incorrectly
**Check:** Console logs for "Already attempted refresh" message
**Fix:** Verify options object not being shared across requests

### Issue: OAuth fails with redirect_uri mismatch
**Cause:** BASE_URL environment variable incorrect
**Check:** import.meta.env.BASE_URL value (should be '/ui/')
**Fix:** Verify vite.config.ts base path setting

## Performance Impact

- **Minimal overhead**: Only triggers on 403 responses
- **500ms delay**: Allows server role processing, acceptable UX
- **Single redirect**: No additional network overhead
- **No polling**: Event-driven, not continuous checking
- **Session storage**: Minimal memory footprint

## Future Improvements

1. **Silent Token Refresh**
   - Use iframe for invisible OAuth
   - Avoid full page redirect
   - Preserve JavaScript state

2. **Token Expiry Prediction**
   - Decode JWT exp claim
   - Proactively refresh before expiry
   - Reduce 403 occurrences

3. **Refresh Token Support**
   - Use OAuth refresh tokens
   - Avoid re-authentication
   - Better user experience

4. **Analytics Integration**
   - Track refresh success/failure rates
   - Monitor loop prevention effectiveness
   - Identify permission issues

## Related Documentation

- [OAuth Testing Guide](OAUTH_TESTING_GUIDE.md)
- [OIDC Local Testing](OIDC_LOCAL_TESTING.md)
- [Architecture Overview](ARCHITECTURE.md)

## References

- [HTTP 403 Forbidden](https://developer.mozilla.org/en-US/docs/Web/HTTP/Status/403)
- [JWT Token Structure (RFC 7519)](https://tools.ietf.org/html/rfc7519)
- [OAuth 2.0 Flow (RFC 6749)](https://tools.ietf.org/html/rfc6749)
- [Session Storage API](https://developer.mozilla.org/en-US/docs/Web/API/Window/sessionStorage)

## Implementation History

- **Version 1.0** (2025-12-24): Initial implementation
  - Basic 403 detection and refresh
  - Loop prevention mechanisms
  - URL preservation
  - Console logging
