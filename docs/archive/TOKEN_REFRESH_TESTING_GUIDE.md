<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Moved: Manual Test Guide – Token Refresh on 403

This content now lives at [docs/features/authentication.md](../docs/features/authentication.md).
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
