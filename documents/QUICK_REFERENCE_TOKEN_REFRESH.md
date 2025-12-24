<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Token Refresh Quick Reference

## What It Does
Automatically refreshes JWT tokens when users get 403 (Forbidden) due to stale permission claims after role changes.

## User Experience

### Before Token Refresh
```
User has role: [user]
Admin assigns: analyst
User clicks action → 403 Forbidden
User must logout and login manually
Context lost, frustrating experience
```

### After Token Refresh
```
User has role: [user]
Admin assigns: analyst
User clicks action → 403 Forbidden
→ Automatic silent redirect to OAuth
→ New token with [user, analyst] roles
→ Return to original page
Action succeeds automatically
```

## How It Works

### Step-by-Step
1. API request returns 403
2. `fetchWithAuth()` detects first-time 403
3. Save current URL to sessionStorage
4. Redirect to OAuth with `?refresh=true`
5. OAuth issues new token (if roles updated)
6. Callback detects `refresh=true` parameter
7. Restore original URL from sessionStorage
8. User continues with new token

### Loop Prevention
- **Per-request**: Flag prevents multiple refreshes for same API call
- **Cross-page**: Token comparison prevents loops after page reload

## Code Locations

### API Handler
**File:** `ui/src/api.ts`
**Function:** `fetchWithAuth()`
**Key Variable:** `lastRefreshToken`

### Callback Handler
**File:** `ui/src/routes/Callback.tsx`
**Detection:** `searchParams.get('refresh') === 'true'`
**Storage:** `sessionStorage.getItem('postLoginUrl')`

## Console Logs

### Successful Refresh
```
[fetchWithAuth] Got 403 Forbidden, user may need permission refresh
[fetchWithAuth] First 403, attempting token refresh
[fetchWithAuth] Waiting 500ms before refresh...
[fetchWithAuth] Redirecting to refresh login flow
[Callback] Token refreshed, returning to: /ui/reports/abc
```

### Loop Prevention Active
```
[fetchWithAuth] Got 403 Forbidden, user may need permission refresh
[fetchWithAuth] Token already refreshed, still 403 - user lacks permission
```

## Quick Test

### Test Automatic Refresh
1. Login as user (role: `user`)
2. Admin assigns role `analyst` via Admin UI
3. Trigger action requiring `analyst` role
4. Watch console → automatic refresh should occur
5. Verify action succeeds after refresh

### Test Loop Prevention
1. Login as user (role: `user`)
2. Trigger action requiring `admin` role (without being granted it)
3. Watch console → first refresh attempted
4. Second 403 blocked with "Token already refreshed" message
5. No infinite loop

## Key Parameters

| Parameter | Location | Purpose |
|-----------|----------|---------|
| `refresh=true` | URL query param | Marks OAuth flow as token refresh |
| `postLoginUrl` | sessionStorage | Stores original page URL |
| `lastRefreshToken` | Memory (api.ts) | Tracks token for loop prevention |
| `_attemptedRefresh` | Request options | Prevents per-request loops |

## Common Issues

### Issue: Infinite Loop
**Check:** `lastRefreshToken` being set correctly?
**Check:** Console shows "Token already refreshed" message?

### Issue: Lost Original URL
**Check:** `sessionStorage.getItem('postLoginUrl')` returns value?
**Check:** sessionStorage not cleared before redirect?

### Issue: No Refresh Triggered
**Check:** Response status is exactly 403?
**Check:** `attemptedRefresh` flag not already set?

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `BASE_URL` | `/ui/` | Vite base path for routing |
| `VITE_REPORTING_API_URL` | `/reporting` | API endpoint prefix |

## Related Files

- `ui/src/api.ts` - API handler with 403 detection
- `ui/src/routes/Callback.tsx` - OAuth callback with refresh detection
- `ui/src/contexts/AuthContext.tsx` - Auth state management
- `documents/TOKEN_REFRESH_ON_403.md` - Full documentation

## Performance

- **Trigger:** Only on 403 responses
- **Delay:** 500ms (allows server processing)
- **Overhead:** Single OAuth redirect
- **Memory:** Minimal (one string variable)

## Security

- **Storage:** localStorage (development), move to httpOnly cookies (production)
- **OAuth:** Standard authorization code flow with state parameter
- **Session:** sessionStorage for temporary URL preservation
- **Tracking:** In-memory variable, cleared on page refresh

## Testing Checklist

- [ ] Basic refresh works when role assigned
- [ ] No infinite loop when role NOT assigned
- [ ] Original URL preserved (including query params)
- [ ] JWT claims verified (roles updated)
- [ ] Logout works during refresh flow
- [ ] Multiple concurrent 403s handled
- [ ] Console logs show expected messages

## Debug Tips

1. **Enable "Preserve log"** in browser DevTools to see full flow
2. **Decode JWT tokens** at jwt.io to verify claims
3. **Check sessionStorage** in DevTools → Application tab
4. **Monitor Network tab** for OAuth redirects
5. **Watch Console** for detailed log messages

## References

- [Full Documentation](TOKEN_REFRESH_ON_403.md)
- [OAuth Testing Guide](OAUTH_TESTING_GUIDE.md)
- [Architecture Overview](ARCHITECTURE.md)
