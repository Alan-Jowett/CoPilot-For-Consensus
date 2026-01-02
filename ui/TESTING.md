# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Manual Testing Guide for Cookie-Based Authentication

## Prerequisites

1. Build and start all services via Docker Compose:
```bash
docker compose build
docker compose up -d
```

2. Wait for services to be healthy:
```bash
docker compose ps
```

**Important**: All testing must be done via the API Gateway at `http://localhost:8080/ui/`. The UI container serves static files only; the gateway handles all API routing, authentication, and service proxying.

## Test 1: Login Flow

### Steps:
1. Open browser (with DevTools)
2. Navigate to http://localhost:8080/ui/
3. Should redirect to login page
4. Click "Sign in with GitHub" (or configured provider)
5. Complete OAuth flow
6. Should redirect back to reports page

### Verification:
- Open DevTools > Application > Cookies > http://localhost:8080
- Verify `auth_token` cookie exists with:
  - ✅ HttpOnly flag set
  - ✅ SameSite=Lax
  - ✅ Path=/
  - ❌ Secure flag (only if using HTTPS)

### Console Test (XSS Protection):
```javascript
// Try to access token - should return null
localStorage.getItem('auth_token')  // null
document.cookie.match(/auth_token=([^;]+)/)  // null (httpOnly blocks JS access)
```

## Test 2: API Requests with Cookies

### Steps:
1. While logged in, navigate to http://localhost:8080/ui/reports
2. Open DevTools > Network tab
3. Click on any report
4. Inspect the API request

### Verification in Network Tab:
- Request URL: `/reporting/api/reports/...`
- Request Headers should include:
  - Cookie: `auth_token=<token>`
- Response should be 200 OK with report data

### Test Protected Endpoints:
1. Navigate to http://localhost:8080/ui/sources (admin only)
2. If you have admin role, you should see the sources page
3. If not admin, should see "Access Denied" message
4. Check Network tab - should see 403 response if not admin

## Test 3: Auth State Persistence

### Steps:
1. While logged in, refresh the page (F5)
2. Should remain logged in
3. Open new tab, navigate to http://localhost:8080/ui/
4. Should still be logged in (session persisted)

### Verification:
- Page loads without redirecting to login
- User menu shows your name/email
- Reports page loads successfully

## Test 4: /auth/userinfo Endpoint

### Test with Cookie:
```bash
# After logging in, copy the auth_token cookie value from DevTools
# Then test the endpoint:

curl -v http://localhost:8080/auth/userinfo \
  --cookie "auth_token=<paste-token-here>"
```

Expected response:
```json
{
  "sub": "github|12345678",
  "email": "user@example.com",
  "name": "User Name",
  "roles": ["admin"],
  "affiliations": [],
  "aud": "copilot-for-consensus"
}
```

### Test with Authorization Header:
```bash
# Using the same token:
curl -v http://localhost:8080/auth/userinfo \
  -H "Authorization: Bearer <paste-token-here>"
```

Should return same response.

### Test without Token:
```bash
curl -v http://localhost:8080/auth/userinfo
```

Expected response: 401 Unauthorized

## Test 5: Logout Flow

### Steps:
1. While logged in, click user menu
2. Click "Logout"
3. Should redirect to login page

### Verification:
- Cookie should be cleared (check DevTools > Cookies)
- Trying to access protected pages should redirect to login
- Network tab should show `/auth/logout` POST request

### Test Cookie Cleared:
```bash
# After logout, try accessing userinfo:
curl -v http://localhost:8080/auth/userinfo \
  --cookie "auth_token=<old-token>"
```

Expected: 401 Unauthorized (token is invalid)

## Test 6: CSRF Protection

### Test Cross-Site POST (Should Fail):
1. Create a file `csrf-test.html`:
```html
<!DOCTYPE html>
<html>
<body>
  <form action="http://localhost:8080/ingestion/api/sources" method="POST">
    <input type="hidden" name="name" value="malicious-source" />
    <button type="submit">Submit</button>
  </form>
  <script>
    // Auto-submit on load
    document.forms[0].submit();
  </script>
</body>
</html>
```

2. Open the file in browser (file:///...)
3. The request should fail because:
   - SameSite=lax prevents cookie from being sent
   - Backend receives request without auth token
   - Returns 401 Unauthorized

### Test Same-Site POST (Should Work):
1. While logged in to http://localhost:8080/ui/
2. Navigate to Sources page
3. Try creating a new source
4. Should work because:
   - Same-site request
   - Cookie is sent automatically
   - Backend receives valid token

## Test 7: Token Expiry

### Steps:
1. Login and note the time
2. Wait for token to expire (default: 30 minutes)
3. Try to access a protected resource
4. Should redirect to login page

### Verification:
- Network tab shows 401 response
- Redirects to `/ui/login`
- Cookie is cleared

## Test 8: Admin Features

### Steps (requires admin role):
1. Login with admin account
2. Navigate to http://localhost:8080/ui/admin
3. Should see admin dashboard with:
   - Pending role assignments
   - User role management
   - Search functionality

### Verification:
- Admin menu is visible in navigation
- Can access `/admin` endpoints
- Can manage user roles

### Steps (without admin role):
1. Login with regular account
2. Try to access http://localhost:8080/ui/admin
3. Should see "Access Denied" message

## Test 9: Grafana SSO

### Steps:
1. Login to UI at http://localhost:8080/ui/
2. Navigate to http://localhost:8080/grafana/
3. Should automatically login to Grafana using JWT from cookie

### Verification:
- No Grafana login prompt
- User is logged in as the same user
- Admin users have Grafana admin role

## Test 10: Multi-Tab Behavior

### Steps:
1. Login in Tab 1
2. Open Tab 2, navigate to http://localhost:8080/ui/
3. Should be logged in (shared cookie)
4. Logout in Tab 1
5. Refresh Tab 2
6. Should redirect to login (cookie cleared)

## Common Issues

### Issue: Cookie not set after login
- Check browser console for errors
- Verify auth service is healthy: `docker compose ps auth`
- Check auth service logs: `docker compose logs auth`

### Issue: 401 on API requests
- Verify cookie exists in DevTools
- Check cookie domain matches request domain
- Check cookie Path is `/`
- Verify token hasn't expired

### Issue: CORS errors
- Ensure requests are same-origin (http://localhost:8080)
- Check Network tab for CORS headers
- Verify `credentials: 'include'` in fetch options

### Issue: Admin features not working
- Verify user has admin role via `/auth/userinfo`
- Check JWT token claims in jwt.io
- Verify role assignment in auth database

## Security Checklist

After testing, verify:
- [ ] No auth tokens in localStorage (check browser storage)
- [ ] Cookies have HttpOnly flag (check DevTools)
- [ ] Cookies have SameSite=Lax (check DevTools)
- [ ] HTTPS uses Secure flag (production only)
- [ ] XSS cannot access token (test in console)
- [ ] CSRF attacks blocked (test cross-site POST)
- [ ] Token expiry works correctly
- [ ] Logout clears cookies
- [ ] API calls work with cookies
- [ ] Admin access control works
