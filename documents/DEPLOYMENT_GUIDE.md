<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Deployment Guide: Initial Admin Setup

This guide covers setting up the initial administrator account when deploying Copilot-for-Consensus for the first time.

## Overview

The system uses a **one-time bootstrap token** mechanism to create the initial admin user without requiring pre-existing authentication. This is necessary because:
- No users exist yet (OAuth hasn't happened)
- Admin endpoints require authentication
- You need a way to bootstrap the system on first deployment

## Deployment Procedure

### Phase 1: Generate Bootstrap Token

When deploying to a new environment, generate a secure random bootstrap token:

```bash
# Generate 32-character random token (using OpenSSL)
BOOTSTRAP_TOKEN=$(openssl rand -hex 16)
echo "Bootstrap token: $BOOTSTRAP_TOKEN"
# Output: Bootstrap token: a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Save this token securely - you'll need it in Phase 3
```

**Important**: This token should be:
- Generated at deployment time (not hardcoded in code)
- Stored securely (vault, secrets manager, secure note)
- Used only once
- Revoked immediately after use

### Phase 2: Configure Environment

Set the `BOOTSTRAP_TOKEN` environment variable before starting services:

#### Option A: Docker Compose (Development)
Add to `.env` file:
```bash
BOOTSTRAP_TOKEN=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6
```

Or pass at startup:
```bash
BOOTSTRAP_TOKEN="a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" docker compose up -d
```

#### Option B: Kubernetes (Production)
Create a secret:
```bash
kubectl create secret generic auth-bootstrap \
  --from-literal=token=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6 \
  -n copilot-consensus
```

Mount in deployment:
```yaml
env:
  - name: BOOTSTRAP_TOKEN
    valueFrom:
      secretKeyRef:
        name: auth-bootstrap
        key: token
```

#### Option C: Docker Secrets (Swarm)
```bash
echo "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6" | docker secret create bootstrap_token -
```

Mount in compose:
```yaml
auth:
  secrets:
    - bootstrap_token
  environment:
    BOOTSTRAP_TOKEN_FILE: /run/secrets/bootstrap_token
```

### Phase 3: Start Services

```bash
# Start all services
docker compose up -d

# Wait for auth service to be healthy
docker compose ps auth
# Should show: ... (healthy)
```

Verify auth service is running:
```bash
curl http://localhost:8080/auth/health
# Expected: {"status":"healthy",...}
```

### Phase 4: Create Initial Admin

Call the bootstrap endpoint with your admin user information:

```bash
curl -X POST http://localhost:8080/auth/bootstrap/admin \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "github|alanjo",
    "email": "alan@example.com",
    "bootstrap_token": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6"
  }'
```

**Notes:**
- `user_id`: Use format `{provider}|{username}` (e.g., `github|alanjo`, `google|alan@gmail.com`)
- `email`: Email address of the admin user
- `bootstrap_token`: The token you generated in Phase 1

Expected response (HTTP 201):
```json
{
  "user_id": "github|alanjo",
  "email": "alan@example.com",
  "roles": ["admin"],
  "message": "Admin user created successfully. Bootstrap token should now be revoked."
}
```

### Phase 5: Revoke Bootstrap Token

**Immediately** after creating the admin, revoke the bootstrap token:

#### Option A: Remove from .env
```bash
# Edit .env and remove/comment out:
# BOOTSTRAP_TOKEN=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6

# Restart auth service
docker compose restart auth
```

#### Option B: Change Token
```bash
# Generate new random token
NEW_TOKEN=$(openssl rand -hex 16)

# Update environment
docker compose exec -e BOOTSTRAP_TOKEN="$NEW_TOKEN" auth restart
```

#### Option C: Kubernetes
```bash
# Delete or update the secret
kubectl delete secret auth-bootstrap -n copilot-consensus
# Restart pod
kubectl rollout restart deployment/auth -n copilot-consensus
```

### Phase 6: Verify System is Secured

Test that bootstrap endpoint is now disabled:

```bash
curl -X POST http://localhost:8080/auth/bootstrap/admin \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "github|attacker",
    "email": "attacker@example.com",
    "bootstrap_token": "any-token"
  }'
```

Expected response (HTTP 403):
```json
{"detail": "Bootstrap not configured"}
```

Or if someone tries with the old token:
```json
{"detail": "Invalid bootstrap token"}
```

## Complete Deployment Script

Here's a complete example for automated deployment:

```bash
#!/bin/bash
set -euo pipefail

echo "=== Copilot-for-Consensus Deployment ==="

# Phase 1: Generate bootstrap token
BOOTSTRAP_TOKEN=$(openssl rand -hex 16)
echo "Generated bootstrap token: $BOOTSTRAP_TOKEN"

# Save to secure location (e.g., vault)
echo "TODO: Store token securely for Phase 4"

# Phase 2: Configure
export BOOTSTRAP_TOKEN
export JWT_AUTH_ENABLED="true"
export LLM_BACKEND="mock"  # Change to real LLM in production

# Phase 3: Start services
echo "Starting services..."
docker compose up -d
echo "Waiting for services to be healthy..."
sleep 30

# Phase 4: Create admin
echo "Creating initial admin user..."
ADMIN_USER="${ADMIN_USER:-github|yourname}"
ADMIN_EMAIL="${ADMIN_EMAIL:-you@example.com}"

curl -X POST http://localhost:8080/auth/bootstrap/admin \
  -H "Content-Type: application/json" \
  -d "{
    \"user_id\": \"$ADMIN_USER\",
    \"email\": \"$ADMIN_EMAIL\",
    \"bootstrap_token\": \"$BOOTSTRAP_TOKEN\"
  }"

echo "✓ Admin user created"

# Phase 5: Revoke token
echo "Revoking bootstrap token..."
unset BOOTSTRAP_TOKEN
docker compose restart auth
sleep 10

echo "✓ Bootstrap token revoked"

# Phase 6: Verify
echo "Verifying security..."
curl -X POST http://localhost:8080/auth/bootstrap/admin \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","email":"test@example.com","bootstrap_token":"invalid"}' \
  | grep -q "Bootstrap not configured" && echo "✓ Bootstrap endpoint secured"

echo "=== Deployment Complete ==="
echo "Admin user: $ADMIN_USER"
echo "You can now log in via OAuth"
```

## Troubleshooting

### Problem: Bootstrap endpoint returns 503 (Service not initialized)
**Cause**: Auth service hasn't started or failed to initialize

**Solution**:
```bash
# Check service is running
docker compose ps auth

# Check logs
docker compose logs auth --tail=50

# Wait for service to be healthy
docker compose ps auth | grep healthy
```

### Problem: Bootstrap token rejected
**Cause**: Token doesn't match `BOOTSTRAP_TOKEN` environment variable

**Solution**:
```bash
# Verify token is set in environment
docker compose exec auth printenv BOOTSTRAP_TOKEN

# Generate new token and try again
BOOTSTRAP_TOKEN=$(openssl rand -hex 16)
docker compose exec -e BOOTSTRAP_TOKEN="$BOOTSTRAP_TOKEN" auth restart
```

### Problem: Bootstrap returns 409 (System already initialized)
**Cause**: Admin user already exists

**Solution**: System is already initialized. Use regular admin endpoints:
```bash
# Assign roles to another user (requires being authenticated as admin)
curl -X POST http://localhost:8080/auth/admin/users/github|newuser/roles \
  -H "Authorization: Bearer <YOUR_JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["admin"]}'
```

### Problem: Bootstrap endpoint returns 403 (Bootstrap not configured)
**This is expected!** It means:
- The bootstrap token has been revoked (security working as intended)
- Use admin endpoints instead to manage other users

## Post-Deployment: Managing Users

After initial setup, manage users through authenticated admin endpoints:

### List all users with roles
```bash
curl http://localhost:8080/auth/admin/users \
  -H "Authorization: Bearer <ADMIN_JWT>"
```

### Assign admin role to another user
```bash
curl -X POST http://localhost:8080/auth/admin/users/github|username/roles \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["admin", "moderator"]}'
```

### Revoke roles
```bash
curl -X DELETE http://localhost:8080/auth/admin/users/github|username/roles \
  -H "Authorization: Bearer <ADMIN_JWT>" \
  -H "Content-Type: application/json" \
  -d '{"roles": ["admin"]}'
```

## Security Checklist

Before going to production:

- [ ] Generate a strong random `BOOTSTRAP_TOKEN` (32+ characters)
- [ ] Store token securely (vault, KMS, secure note - NOT in code)
- [ ] Bootstrap endpoint only called once
- [ ] `BOOTSTRAP_TOKEN` removed/changed immediately after Phase 4
- [ ] Auth service restarted after token revocation
- [ ] Verify bootstrap endpoint returns 403 after revocation
- [ ] Use HTTPS for all auth endpoints in production
- [ ] JWT signing keys securely stored (Azure Key Vault recommended)
- [ ] OAuth provider credentials in secrets management
- [ ] MongoDB credentials use strong passwords
- [ ] Regular admin access auditing enabled

## References

- [OAuth Testing Guide](OAUTH_TESTING_GUIDE.md) - Testing OAuth flows after deployment
- [Auth Implementation Summary](AUTH_IMPLEMENTATION_SUMMARY.md) - Architecture and components
- [LOCAL_DEVELOPMENT.md](LOCAL_DEVELOPMENT.md) - Local dev setup

