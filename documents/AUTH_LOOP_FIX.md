# Authentication Loop Fix - Issue Resolution

## Problem Summary

Users authenticating via OAuth without the required `reader` role were experiencing an infinite authentication loop:

1. User completes OAuth login successfully
2. Auth service issues a valid JWT token (but user has no roles)
3. SPA stores token in localStorage
4. SPA makes API request (e.g., `/reporting/api/sources`)
5. Reporting service validates token but returns **403 Forbidden** (user lacks `reader` role)
6. SPA's `fetchWithAuth` incorrectly treats 403 as "expired token" and triggers automatic refresh
7. User is redirected back to OAuth flow
8. **Loop repeats indefinitely from step 1**

## Root Causes

1. **Incorrect HTTP Status Interpretation**: The UI treated 403 (Forbidden - missing permissions) the same as 401 (Unauthorized - expired token)
2. **Automatic Token Refresh for Wrong Condition**: Token refresh should only occur for expired tokens (401), not missing permissions (403)
3. **Lack of User Feedback**: User never saw why they were stuck in the loop

## Solution Implemented

### 1. Fixed HTTP Status Code Handling (`ui/src/api.ts`)

**Before:**
```typescript
// 403 triggered token refresh with complex loop prevention logic
if (response.status === 403) {
  // ~80 lines of token refresh logic including:
  // - Checking if redirect already in progress
  // - Tracking last refresh token
  // - Waiting for role changes
  // - Redirecting to OAuth
}
```

**After:**
```typescript
// 403 now throws clear error without triggering refresh
if (response.status === 403) {
  console.log('[fetchWithAuth] Got 403 Forbidden - user lacks required permissions')
  let errorDetail = 'You do not have permission to access this resource.'
  try {
    const errorData = await response.json()
    if (errorData.detail) {
      errorDetail = errorData.detail
    }
  } catch (e) {
    // Couldn't parse error response, use default message
  }
  throw new Error(`ACCESS_DENIED: ${errorDetail}`)
}
```

### 2. Created AccessDenied Component (`ui/src/components/AccessDenied.tsx`)

A reusable component that displays:
- Clear error icon (🚫)
- "Access Denied" heading
- Detailed error message from the API
- Logout button for the user to sign in with a different account

### 3. Updated All API-Calling Components

Modified error handling in:
- `ReportsList.tsx`
- `SourcesList.tsx`
- `ReportDetail.tsx`
- `ThreadSummary.tsx`
- `SourceForm.tsx`

Pattern used:
```typescript
const [accessDenied, setAccessDenied] = useState<string | null>(null)

// In error handler:
if (e?.message?.startsWith('ACCESS_DENIED:')) {
  setAccessDenied(e.message.replace('ACCESS_DENIED: ', ''))
  return
}

// In render:
if (accessDenied) return <AccessDenied message={accessDenied} />
```

## HTTP Status Code Clarification

| Status | Meaning | Cause | Action |
|--------|---------|-------|--------|
| **401 Unauthorized** | Token is expired or invalid | Token lifetime exceeded, token malformed, signature invalid | Redirect to login page |
| **403 Forbidden** | Valid token but user lacks permission | User doesn't have required role in JWT claims | Show access denied message, user must request role assignment |

## Testing the Fix

### Scenario 1: User Lacks Required Role

1. Create a user with no roles in the role store
2. User authenticates via OAuth (receives valid token)
3. User attempts to access `/reports` page
4. **Expected Result**: AccessDenied component displays with message "Missing required role: reader"
5. User clicks "Logout" button
6. **No infinite loop occurs**

### Scenario 2: Token Expired

1. User has valid roles but token expires
2. User attempts to access protected resource
3. **Expected Result**: 401 status triggers redirect to login page
4. User re-authenticates and can access resources

### Scenario 3: User Has Required Roles

1. User has `reader` role
2. User authenticates via OAuth
3. User accesses `/reports` page
4. **Expected Result**: Reports page loads successfully, no errors

## Files Changed

1. `ui/src/api.ts` - Removed token refresh logic for 403, added clear error
2. `ui/src/components/AccessDenied.tsx` - New component for permission errors
3. `ui/src/routes/ReportsList.tsx` - Added ACCESS_DENIED handling
4. `ui/src/routes/SourcesList.tsx` - Added ACCESS_DENIED handling
5. `ui/src/routes/ReportDetail.tsx` - Added ACCESS_DENIED handling
6. `ui/src/routes/ThreadSummary.tsx` - Added ACCESS_DENIED handling
7. `ui/src/routes/SourceForm.tsx` - Added ACCESS_DENIED handling

## Related Issues & Future Work

### Short-term (Addressed in this PR)
- ✅ Stop the authentication loop
- ✅ Provide clear user feedback for permission errors

### Long-term (Future PRs)
- ⏳ Auto-assign `reader` role to all authenticated users
- ⏳ Add "Request Access" button that creates a pending role assignment
- ⏳ Admin UI for approving pending role assignments
- ⏳ Token refresh mechanism for legitimate token expiration cases

## Security Review

**CodeQL Results**: ✅ No vulnerabilities detected

The changes:
- Do not introduce new authentication bypasses
- Do not expose sensitive information in error messages
- Maintain proper separation between authentication (401) and authorization (403)
- Follow secure coding practices for error handling

## References

- Issue: #XXX - "auth: SPA stuck in authentication loop when user lacks required roles"
- Related: Auth middleware logs show `"User missing required role"` warnings
- Documentation: `documents/AUTH_IMPLEMENTATION_COMPLETE.md`
