<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Authentication & Token Refresh

Canonical guide for the authentication stack: OIDC login, local JWT minting, gateway wiring, service middleware, UI integration, and token refresh behavior.

## Overview
- OIDC providers: GitHub, Google, Microsoft Entra ID.
- Auth service mints RS256 JWTs with kid + JWKS for validation.
- Gateway routes `/auth/*` to auth service, `/ui/*` to React app, `/reporting/*` and others to APIs.
- Services use `copilot_auth` middleware for JWT validation and role checks.
- UI reads tokens from localStorage in dev; automatic refresh handles 403s after role changes.

## Architecture
```
Browser/UI → Gateway (:8080) → Auth (:8090) ↔ OIDC Provider
                       ↓
                 Service APIs (JWKS-validated JWT)
```
- Token claims: `iss`, `sub` (`provider:user_id`), `aud`, `roles`, `email`, `name`, `affiliations`, `amr`, `exp`, `iat`, `nbf`, `jti`.
- JWKS served at `/auth/keys`; services cache and refresh keys automatically.

## Components
- Auth service (`auth/`): FastAPI app exposing login, callback, token, userinfo, keys, health/readyz; JWT signing via RSA keys in `/run/secrets` or env.
- Adapter (`adapters/copilot_auth`): `create_jwt_middleware()` for FastAPI; handles JWKS fetch, audience enforcement, role checks, public path exemptions, request state enrichment.
- UI (`ui/`): `/ui/login` OAuth launcher, `/ui/callback` handler stores token, `fetchWithAuth()` injects Authorization header from localStorage (dev) and drives token refresh on 403.

## Configuration Cheatsheet
Use env for non-secrets; mount provider secrets into `/run/secrets`.

```
# Auth service
AUTH_ISSUER=http://localhost:8090
AUTH_AUDIENCES=copilot-orchestrator,copilot-reporting
JWT_ALGORITHM=RS256
JWT_KEY_ID=default
JWT_DEFAULT_EXPIRY=1800
AUTH_REQUIRE_PKCE=true
AUTH_REQUIRE_NONCE=true
AUTH_MAX_SKEW_SECONDS=90
AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED=false  # keep disabled in prod

# Provider secrets (files under ./secrets → /run/secrets)
github_oauth_client_id
github_oauth_client_secret
# ... google/microsoft variants
```

## Endpoints
- `GET /auth/login?provider=<id>&aud=<aud>&redirect_uri=<uri>`: start OAuth flow.
- `GET /auth/callback`: exchanges code for JWT; redirects to UI callback.
- `POST /auth/token`: placeholder for S2S token exchange.
- `GET /auth/userinfo`: derive user info from JWT.
- `GET /auth/keys`: JWKS for public validation.
- `GET /auth/health`, `GET /auth/readyz`: diagnostics.

## Integration Patterns
**FastAPI services**
```python
from copilot_auth import create_jwt_middleware

app.add_middleware(create_jwt_middleware(
    auth_service_url="http://auth:8090",
    audience="my-service",
    required_roles=["reader"],
    public_paths=["/health", "/docs", "/openapi.json"],
))
```

**Service-to-service calls**
```python
import httpx

def call_reporting(token: str):
    return httpx.get(
        "http://reporting:8080/api/reports",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
```

**UI fetch helper (development storage)**
- Reads token from `localStorage` per request.
- On `401`: clears token and redirects to login.
- On first `403`: saves `postLoginUrl`, waits 500ms, redirects to `/auth/login?...callback?refresh=true` for silent re-auth; loop prevention via `lastRefreshToken` + per-request `_attemptedRefresh`.
- Callback uses `refresh=true` flag to restore original URL from `sessionStorage` and clean up.

## Token Refresh on 403 (Role Changes)
- Trigger: API returns 403 due to stale role claims.
- Flow: `fetchWithAuth()` detects first 403 → store current URL → redirect to OAuth with `refresh=true` → callback stores new token → redirect back → subsequent 403 with same token stops refresh and surfaces permission error.
- Logging: `[fetchWithAuth] First 403...`, `[Callback] Token refreshed, returning to: <url>`, `[fetchWithAuth] Token already refreshed, still 403 - user lacks permission`.

## Manual Verification
- Health: `curl http://localhost:8080/auth/health`, `curl http://localhost:8080/auth/keys`.
- OAuth smoke: browser to `http://localhost:8080/ui/login`, complete provider login, expect redirect to `/ui/reports` and API calls with `Has token: true` in console.
- Token refresh: grant new role after login, trigger 403, confirm automatic redirect and new token claims include new role; second 403 without new role should **not** loop.

## Security & Production Notes
- Keep `AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED=false` outside isolated bootstrap; if temporarily enabled, do so in an isolated window, promote admin once, then disable and restart.
- Store JWT keys in a secure vault for production; rotate via kid/JWKS, automate rotation.
- Migrate tokens to httpOnly Secure cookies (localStorage is dev-only); add CSRF protections (SameSite), PKCE enforcement, rate limiting, audit logging, session store (Redis), refresh tokens/DPoP as hardening backlog.

## File Map
- Auth service: `auth/main.py`, `auth/app/service.py`, `auth/app/config.py`, `auth/app/role_store.py`, `auth/app/middleware.py`, `auth/generate_keys.py`.
- Adapter: `adapters/copilot_auth/copilot_auth/*.py` (providers, JWT manager, middleware factory).
- UI: `ui/src/routes/Login.tsx`, `ui/src/routes/Callback.tsx`, `ui/src/contexts/AuthContext.tsx`, `ui/src/api.ts`.
- Infrastructure: `docker-compose.services.yml` (redirect URIs, secrets), `.env` overrides, gateway config in `docker-compose.yml`.

## Troubleshooting
- 401s despite login: ensure `ui/src/api.ts` uses localStorage reads (dev) and rebuild UI: `docker compose build ui --no-cache && docker compose restart ui`.
- Redirect URI mismatch: verify redirect URIs point to `/ui/callback` and `import.meta.env.BASE_URL` is `/ui/`.
- MongoDB role store errors: confirm secrets mounted and `auth/app/role_store.py` reads from `/run/secrets`.
- Refresh loops: check console for `Token already refreshed`; verify `lastRefreshToken` logic and that new token is issued.

## Future Work
- Automated tests for UI auth/refresh (Vitest/Jest).
- Silent refresh + proactive expiry handling.
- Admin UI for roles and key rotation.
- Production hardening tasks above.
