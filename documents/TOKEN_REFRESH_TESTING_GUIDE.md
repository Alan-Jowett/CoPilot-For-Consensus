<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Manual Test Guide: Token Refresh on 403

This guide provides step-by-step instructions for manually testing the automatic token refresh feature.

## Prerequisites

1. Running instance of Copilot for Consensus
2. Two user accounts:
   - **User Account**: Standard user with `user` role
   - **Admin Account**: Administrator with `admin` role
3. Browser with DevTools (Chrome, Firefox, Edge)

## Test Environment Setup

### 1. Enable DevTools Console Logging
1. Open browser DevTools (F12)
2. Go to Console tab
3. **Enable "Preserve log"** (important to see full flow across redirects)
4. Set log level to "Verbose" or "All"

### 2. Verify Initial State
1. Logout if currently logged in
2. Clear localStorage: `localStorage.clear()`
3. Clear sessionStorage: `sessionStorage.clear()`

## Test Scenarios

---

## Test 1: Basic Token Refresh (Role Assignment)

**Objective:** Verify automatic refresh when admin assigns new role

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/
   Login with user credentials
   Verify: Dashboard loads
   ```

2. **Check Initial Token**
   ```
   Open Console
   Run: localStorage.getItem('auth_token')
   Copy token and decode using an offline JWT decoder
   (WARNING: Never paste production tokens into third-party sites like jwt.io)
   Expected: roles = ["user"]
   ```

3. **Admin Assigns New Role**
   ```
   In separate browser/incognito:
   - Login as admin
   - Navigate to Admin → User Roles
   - Search for test user
   - Assign role: "analyst"
   - Save changes
   ```

4. **Trigger 403 with Stale Token**
   ```
   In user browser:
   - Navigate to /ui/reports
   - Click any action requiring analyst role
   OR
   - Manually call API that requires analyst role
   ```

5. **Observe Automatic Refresh**
   ```
   Expected Console Output:
   [fetchWithAuth] Got 403 Forbidden, user may need permission refresh
   [fetchWithAuth] First 403, attempting token refresh
   [fetchWithAuth] Waiting 500ms before refresh...
   [fetchWithAuth] Redirecting to refresh login flow
   
   Browser redirects to OAuth
   OAuth completes (may be silent)
   
   [Callback] Token refreshed, returning to: /ui/reports
   [Callback] Redirecting to /ui/reports
   ```

6. **Verify New Token**
   ```
   After redirect:
   Run: localStorage.getItem('auth_token')
   Copy and decode using an offline JWT decoder
   (WARNING: Never paste production tokens into third-party sites)
   Expected: roles = ["user", "analyst"]
   ```

7. **Verify Action Succeeds**
   ```
   - Retry the action that triggered 403
   - Expected: Action succeeds with new permissions
   ```

### Success Criteria
- ✓ Automatic redirect to OAuth occurred
- ✓ User returned to same page
- ✓ New token contains updated roles
- ✓ Action succeeds after refresh
- ✓ Console shows expected log messages

---

## Test 2: Loop Prevention (True Permission Denial)

**Objective:** Verify no infinite loop when role NOT assigned

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/
   Login with user credentials (role: user)
   ```

2. **Trigger 403 Without Role Assignment**
   ```
   - Navigate to admin-only page: /ui/admin
   OR
   - Call API requiring admin role
   
   Note: Admin should NOT assign admin role to user
   ```

3. **Observe First Refresh Attempt**
   ```
   Expected Console Output:
   [fetchWithAuth] Got 403 Forbidden, user may need permission refresh
   [fetchWithAuth] First 403, attempting token refresh
   [fetchWithAuth] Waiting 500ms before refresh...
   [fetchWithAuth] Redirecting to refresh login flow
   
   Browser redirects to OAuth
   ```

4. **Verify Token Unchanged**
   ```
   After OAuth:
   Run: localStorage.getItem('auth_token')
   Decode using an offline JWT decoder
   (WARNING: Never paste production tokens into third-party sites)
   Expected: roles = ["user"] (no change)
   ```

5. **Trigger Second 403**
   ```
   - Browser returns to original page
   - Page tries to load (triggers another 403)
   OR
   - Manually retry the action
   ```

6. **Verify Loop Prevention**
   ```
   Expected Console Output:
   [fetchWithAuth] Got 403 Forbidden, user may need permission refresh
   [fetchWithAuth] Token already refreshed, still 403 - user lacks permission
   
   NO additional OAuth redirect
   ```

7. **Verify Permission Error Displayed**
   ```
   - User sees permission denied error
   - No browser stuck in redirect loop
   - Can navigate away normally
   ```

### Success Criteria
- ✓ First 403 triggered refresh attempt
- ✓ OAuth completed but token unchanged
- ✓ Second 403 blocked (no additional redirect)
- ✓ Console shows "Token already refreshed" message
- ✓ User sees permission error, not stuck in loop

---

## Test 3: URL Preservation

**Objective:** Verify original page context preserved

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/
   Login with credentials
   ```

2. **Navigate to Complex URL**
   ```
   Navigate to: /ui/reports?thread_id=test123&page=2&filter=active
   Note the full URL with query parameters
   ```

3. **Admin Assigns Role**
   ```
   In separate browser:
   - Login as admin
   - Assign role "analyst" to user
   ```

4. **Trigger 403**
   ```
   - Click action requiring analyst role
   - Watch automatic refresh occur
   ```

5. **Verify URL Restored**
   ```
   After OAuth callback:
   Check URL in address bar
   Expected: /ui/reports?thread_id=test123&page=2&filter=active
   
   All query parameters preserved
   ```

6. **Verify Page State**
   ```
   - Page loads with correct filters
   - Pagination shows page 2
   - Thread ID filter active
   ```

### Success Criteria
- ✓ Full URL preserved (pathname + query params)
- ✓ Page loads with correct state
- ✓ No query parameters lost
- ✓ Console shows correct redirect URL

---

## Test 4: Token Claims Verification

**Objective:** Verify JWT token actually updated with new claims

### Steps

1. **Login and Capture Initial Token**
   ```
   Login as user
   Run: localStorage.getItem('auth_token')
   Copy token to clipboard
   ```

2. **Decode Initial Token**
   ```
   Use an offline JWT decoder (browser extension or local tool)
   WARNING: Only use sanitized/non-production tokens with external sites
   If using a third-party site for testing only: https://jwt.io
   Paste token in "Encoded" section
   Note the "roles" claim in payload
   Example: { "roles": ["user"], ... }
   ```

3. **Admin Assigns Multiple Roles**
   ```
   Admin assigns: ["analyst", "reviewer"]
   ```

4. **Trigger Refresh**
   ```
   - Trigger action requiring analyst role
   - Watch automatic refresh complete
   ```

5. **Capture New Token**
   ```
   Run: localStorage.getItem('auth_token')
   Copy new token to clipboard
   ```

6. **Decode New Token**
   ```
   Use an offline JWT decoder (browser extension or local tool)
   WARNING: Only use sanitized/non-production tokens with external sites
   If using a third-party site for testing only: https://jwt.io
   Paste new token
   Compare with initial token
   ```

7. **Verify Claims Updated**
   ```
   Expected Payload:
   {
     "roles": ["user", "analyst", "reviewer"],
     "iat": [new timestamp],
     "exp": [new expiry],
     ...
   }
   
   Verify:
   - roles array contains new roles
   - iat (issued at) is newer
   - exp (expiry) is newer
   - Token signature changed
   ```

### Success Criteria
- ✓ New token issued (different signature)
- ✓ Roles array contains new roles
- ✓ Timestamps updated (iat, exp)
- ✓ Token format valid (decodes with offline JWT decoder)

---

## Test 5: Logout During Refresh

**Objective:** Verify logout works during OAuth flow

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/
   Login with credentials
   ```

2. **Trigger Refresh**
   ```
   - Admin assigns new role
   - Trigger action that causes 403
   - Watch OAuth redirect start
   ```

3. **Interrupt with Logout**
   ```
   - Before OAuth completes, click Logout button
   OR
   - During OAuth redirect, manually navigate to logout
   ```

4. **Verify Logout Succeeds**
   ```
   Expected:
   - localStorage.getItem('auth_token') returns null
   - User redirected to login page
   - No errors in console
   - No stuck state
   ```

5. **Verify Clean State**
   ```
   Check:
   - sessionStorage.getItem('postLoginUrl') is null
   - No orphaned OAuth state
   - Can login again normally
   ```

### Success Criteria
- ✓ Logout works during OAuth flow
- ✓ Token cleared from localStorage
- ✓ No JavaScript errors
- ✓ Can login again normally
- ✓ No stuck or corrupted state

---

## Test 6: Multiple Concurrent 403s

**Objective:** Verify multiple API calls with 403 handled correctly

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/
   Login with user role only
   ```

2. **Trigger Multiple API Calls**
   ```
   Open Console, run:
   
   fetch('/reporting/api/reports').catch(e => console.log('Req 1:', e))
   fetch('/reporting/api/sources').catch(e => console.log('Req 2:', e))
   fetch('/reporting/api/threads').catch(e => console.log('Req 3:', e))
   
   All should return 403 (if roles require it)
   ```

3. **Observe Single Refresh**
   ```
   Expected:
   - Only ONE OAuth redirect occurs
   - Not three separate redirects
   - Console shows refresh for first request only
   ```

4. **Verify Others Blocked**
   ```
   Expected Console Output:
   [fetchWithAuth] Got 403 Forbidden, user may need permission refresh
   [fetchWithAuth] First 403, attempting token refresh
   [then for other requests]
   [fetchWithAuth] Already attempted refresh for this request
   ```

### Success Criteria
- ✓ Multiple 403s in quick succession handled
- ✓ Only one OAuth redirect triggered
- ✓ Subsequent requests blocked from refreshing
- ✓ No race conditions or errors

---

## Test 7: Session Loss During OAuth

**Objective:** Verify graceful fallback if sessionStorage lost

### Steps

1. **Login as User**
   ```
   Navigate to: /ui/reports?thread_id=test
   ```

2. **Trigger Refresh**
   ```
   - Admin assigns role
   - Trigger 403 action
   - OAuth redirect starts
   ```

3. **Clear sessionStorage During OAuth**
   ```
   During OAuth flow (before callback):
   Open Console in callback page
   Run: sessionStorage.clear()
   ```

4. **Verify Fallback Behavior**
   ```
   Expected Console Output:
   [Callback] Token refreshed, location lost, using default
   [Callback] Redirecting to /ui/reports
   
   User redirected to /ui/reports (not original URL)
   ```

5. **Verify No Errors**
   ```
   - No JavaScript errors
   - Page loads normally
   - User can navigate manually
   ```

### Success Criteria
- ✓ Fallback to /ui/reports works
- ✓ No JavaScript errors
- ✓ User not stuck or confused
- ✓ Can navigate to desired page manually

---

## Debugging Checklist

If tests fail, check these common issues:

### Console Logs Not Showing
- [ ] DevTools console open?
- [ ] "Preserve log" enabled?
- [ ] Log level set to "Verbose"?

### OAuth Redirect Fails
- [ ] BASE_URL environment variable correct?
- [ ] Redirect URI matches auth service config?
- [ ] Auth service running and accessible?

### Token Not Updating
- [ ] Admin successfully assigned role?
- [ ] Check admin UI for confirmation
- [ ] Decode token to verify claims

### Infinite Loop
- [ ] lastRefreshToken being set correctly?
- [ ] Console shows "Token already refreshed" message?
- [ ] Check api.ts line 69 and 92

### Original URL Lost
- [ ] sessionStorage.getItem('postLoginUrl') has value?
- [ ] Check before OAuth redirect
- [ ] Verify sessionStorage not cleared

## Test Results Template

```markdown
## Test Results: Token Refresh on 403

**Date:** YYYY-MM-DD
**Tester:** [Name]
**Environment:** [Local/Dev/Staging]

### Test 1: Basic Token Refresh
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 2: Loop Prevention
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 3: URL Preservation
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 4: Token Claims Verification
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 5: Logout During Refresh
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 6: Multiple Concurrent 403s
- Status: [PASS/FAIL]
- Notes: [Observations]

### Test 7: Session Loss During OAuth
- Status: [PASS/FAIL]
- Notes: [Observations]

### Overall Assessment
- All tests passed: [YES/NO]
- Critical issues: [None/List]
- Recommendations: [Notes]
```

## Automated Testing Considerations

While this guide focuses on manual testing, consider these areas for future automated tests:

1. **Unit Tests**
   - Loop prevention logic (token comparison)
   - URL preservation (sessionStorage)
   - Flag management (_attemptedRefresh)

2. **Integration Tests**
   - OAuth flow with refresh parameter
   - Token refresh end-to-end
   - Multiple 403 handling

3. **E2E Tests**
   - Full user journey with role assignment
   - Browser automation with Playwright/Cypress
   - Console log verification

## References

- [TOKEN_REFRESH_ON_403.md](TOKEN_REFRESH_ON_403.md) - Full documentation
- [QUICK_REFERENCE_TOKEN_REFRESH.md](QUICK_REFERENCE_TOKEN_REFRESH.md) - Quick reference
- [OAUTH_TESTING_GUIDE.md](OAUTH_TESTING_GUIDE.md) - OAuth testing guide
