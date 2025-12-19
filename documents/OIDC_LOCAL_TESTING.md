<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Local OIDC Testing Guide

This guide walks you through setting up and testing GitHub, Google, and Microsoft OAuth/OIDC providers with the auth service running locally on your machine.

## Prerequisites

- Auth service running at `http://localhost:8090`
- `./secrets/` directory exists with valid JWT keys:
  - `secrets/jwt_private_key` (RSA private key)
  - `secrets/jwt_public_key` (RSA public key)
- Docker Compose configured with secrets volume mounted to `/run/secrets`

## Overview

Each provider requires:
1. **Registration**: Create an OAuth app with the provider
2. **Credentials**: Obtain client ID and client secret
3. **Local Configuration**: Add client ID to env, store secret in `./secrets`
4. **Testing**: Navigate to auth service login endpoint and authorize

## GitHub OAuth Setup

### Step 1: Create GitHub OAuth App

1. Go to https://github.com/settings/developers
2. Click **New OAuth App**
3. Fill in:
   - **Application Name**: `Copilot-for-Consensus-Local` (or your choice)
   - **Homepage URL**: `http://localhost:8090`
   - **Authorization callback URL**: `http://localhost:8090/callback`
4. Click **Create OAuth app**
5. You'll see **Client ID** and **Client Secret**
   - Copy **Client ID** (you'll need it for env)
   - Copy **Client Secret** (you'll store it in `./secrets`)

### Step 2: Store Secrets Locally

```bash
# Create secrets directory if it doesn't exist
mkdir -p secrets

# Store the GitHub client secret (paste your actual secret below)
echo "your_github_client_secret_here" > secrets/github_oauth_client_secret
```

### Step 3: Configure Auth Service

Write the client ID to the secrets store mounted at `/run/secrets`:

```bash
echo "your_client_id_from_step_1" > secrets/github_oauth_client_id
```

### Step 4: Start Auth Service

```bash
# Rebuild auth to pick up new env vars
docker compose build auth

# Start auth service
docker compose up -d auth

# Verify it's healthy
docker compose ps auth
```

Check logs to confirm no errors:

```bash
docker compose logs auth --tail=20
```

### Step 5: Test GitHub Login

1. Open browser to: `http://localhost:8090/login?provider=github`
2. You'll be redirected to GitHub to authorize
3. After authorizing, GitHub redirects back to `http://localhost:8090/callback`
4. Auth service mints a JWT and responds with the token (check browser console or response body)

### Step 6: Verify JWT Token

Decode the JWT to verify claims:

```bash
# If token is in response, extract it and decode
python3 -c "
import jwt
import json

token = 'your_token_here'
decoded = jwt.decode(token, options={'verify_signature': False})
print(json.dumps(decoded, indent=2))
"
```

Expected fields:
- `sub`: GitHub username
- `aud`: Should match `AUTH_AUDIENCES` (default: copilot-orchestrator)
- `iss`: Should match `AUTH_ISSUER` (default: http://localhost:8090)
- `exp`: Token expiration timestamp

---

## Google OAuth Setup

### Step 1: Create Google OAuth Credentials

1. Go to https://console.cloud.google.com/
2. Create a new project or select existing (e.g., "Copilot-for-Consensus-Local")
3. Go to **APIs & Services** → **Credentials**
4. Click **+ Create Credentials** → **OAuth client ID**
5. Choose application type: **Web application**
6. Configure:
   - **Name**: `Copilot-for-Consensus-Local`
   - **Authorized redirect URIs**: Add `http://localhost:8090/callback`
7. Click **Create**
8. You'll see:
   - **Client ID**
   - **Client Secret**
   - Copy both

### Step 2: Store Secret Locally

```bash
# Store the Google client secret
echo "your_google_client_secret_here" > secrets/google_oauth_client_secret
```

### Step 3: Configure Auth Service

Set environment variable:

```bash
export AUTH_GOOGLE_CLIENT_ID="your_client_id_from_step_1"
```

Or in `.env`:

```env
AUTH_GOOGLE_CLIENT_ID=your_client_id_from_step_1
```

### Step 4: Start Auth Service

```bash
docker compose build auth
docker compose up -d auth
docker compose logs auth --tail=20
```

### Step 5: Test Google Login

1. Open browser to: `http://localhost:8090/login?provider=google`
2. You'll be redirected to Google login
3. Sign in and consent to scopes
4. Google redirects back to `http://localhost:8090/callback`
5. Auth service returns JWT

### Step 6: Verify JWT

Same as GitHub (decode and check `sub`, `aud`, `iss`, `exp`).

---

## Microsoft OAuth Setup

### Step 1: Create Microsoft Entra (Azure AD) OAuth App

1. Go to https://entra.microsoft.com/
2. Go to **Applications** → **App registrations**
3. Click **+ New registration**
4. Configure:
   - **Name**: `Copilot-for-Consensus-Local`
   - **Supported account types**: Choose based on your needs (e.g., "Accounts in this organizational directory only" or "Multitenant")
   - **Redirect URI**: Select **Web**, enter `http://localhost:8090/callback`
5. Click **Register**
6. You'll see **Application (client) ID**
   - Copy this (for env)
7. Go to **Certificates & secrets**
8. Click **+ New client secret**
9. Configure:
   - **Description**: `Local testing`
   - **Expires**: Choose expiration (e.g., 6 months)
10. Click **Add**
11. Copy the **Value** (the secret itself, not the ID)

### Step 2: Store Secret Locally

```bash
# Store the Microsoft client secret
echo "your_microsoft_client_secret_here" > secrets/microsoft_oauth_client_secret
```

### Step 3: Configure Auth Service

Set environment variables:

```bash
export AUTH_MS_CLIENT_ID="your_client_id_from_step_1"
export AUTH_MS_TENANT="common"  # or your specific tenant ID
```

Or in `.env`:

```env
AUTH_MS_CLIENT_ID=your_client_id_from_step_1
AUTH_MS_TENANT=common
```

### Step 4: Start Auth Service

```bash
docker compose build auth
docker compose up -d auth
docker compose logs auth --tail=20
```

### Step 5: Test Microsoft Login

1. Open browser to: `http://localhost:8090/login?provider=microsoft`
2. You'll be redirected to Microsoft login
3. Sign in with your account
4. Consent to scopes (if prompted)
5. Microsoft redirects back to `http://localhost:8090/callback`
6. Auth service returns JWT

### Step 6: Verify JWT

Same as GitHub/Google.

---

## Complete `.env` Template

Create a `.env` file in the repo root (or update your existing one) with core OIDC settings (client IDs now read from secrets files):

```env
# Auth Service OIDC Configuration
AUTH_ISSUER=http://localhost:8090
AUTH_AUDIENCES=copilot-orchestrator,copilot-reporting
JWT_ALGORITHM=RS256
JWT_KEY_ID=default
JWT_DEFAULT_EXPIRY=1800
AUTH_REQUIRE_PKCE=true
AUTH_REQUIRE_NONCE=true
AUTH_MAX_SKEW_SECONDS=90

# GitHub OAuth
AUTH_GITHUB_REDIRECT_URI=http://localhost:8090/callback

# Google OAuth
AUTH_GOOGLE_REDIRECT_URI=http://localhost:8090/callback

# Microsoft OAuth
AUTH_MS_TENANT=common
AUTH_MS_REDIRECT_URI=http://localhost:8090/callback

# Secret Provider Configuration
SECRET_PROVIDER_TYPE=local
SECRETS_BASE_PATH=/run/secrets
```

**Important**: Client IDs are pulled from `/run/secrets`; ensure the files exist before starting containers. Add `.env` to `.gitignore` if not already present.

---

## Secrets File Structure

After following all provider setup steps, your `./secrets` directory should look like:

```
secrets/
├── jwt_private_key                    # Generated by generate_keys.py
├── jwt_public_key                     # Generated by generate_keys.py
├── github_oauth_client_id             # From GitHub OAuth app
├── github_oauth_client_secret         # From GitHub OAuth app
├── google_oauth_client_id             # From Google console
├── google_oauth_client_secret         # From Google console
├── microsoft_oauth_client_id          # From Microsoft Entra
└── microsoft_oauth_client_secret      # From Microsoft Entra
```

All files are mounted as read-only to `/run/secrets` in the auth container.

---

## Testing Checklist

- [ ] GitHub OAuth app created and credentials obtained
- [ ] Google OAuth app created and credentials obtained
- [ ] Microsoft Entra app created and credentials obtained
- [ ] All three client IDs and secrets stored in `./secrets/`
- [ ] JWT keys present in `./secrets/`
- [ ] Auth service rebuilt and running (`docker compose ps auth` shows healthy)
- [ ] GitHub login flow tested: `http://localhost:8090/login?provider=github`
- [ ] Google login flow tested: `http://localhost:8090/login?provider=google`
- [ ] Microsoft login flow tested: `http://localhost:8090/login?provider=microsoft`
- [ ] All three flows return valid JWTs
- [ ] Tokens decode correctly with correct `sub`, `aud`, `iss` claims

---

## Troubleshooting

### "Redirect URI mismatch"
- Ensure the callback URL in your provider app registration **exactly** matches `http://localhost:8090/callback`
- Whitespace matters!

### "Client ID or secret invalid"
- Double-check that the client ID/secret files in `secrets/` match the values from the provider
- Verify the secret file contents (e.g., `cat secrets/github_oauth_client_id`)
- Rebuild auth after changing secrets: `docker compose build auth`

### Auth service not picking up secrets
- Ensure `docker compose build auth` was run after updating files in `secrets/`
- Confirm the secrets volume is mounted (`./secrets:/run/secrets:ro`)

### Token decode fails
- Ensure JWT_PRIVATE_KEY and JWT_PUBLIC_KEY are valid RSA keys
- Regenerate if needed: `python auth/generate_keys.py`

### Microsoft redirect fails with "AADSTS50011"
- This indicates redirect URI mismatch or tenant misconfiguration
- Verify redirect URI in Entra exactly matches callback
- Ensure `AUTH_MS_TENANT` is set correctly (use "common" for multi-tenant)

---

## Next Steps

Once all three providers are working:
1. Create an integration test that exercises each flow
2. Add provider-specific tests to the auth adapter test suite
3. Document any provider-specific behavior or quirks
4. Prepare for production deployment (HTTPS, production credentials, etc.)

See [auth/README.md](../auth/README.md) and [documents/AUTH_INTEGRATION_EXAMPLES.md](./AUTH_INTEGRATION_EXAMPLES.md) for more details.
