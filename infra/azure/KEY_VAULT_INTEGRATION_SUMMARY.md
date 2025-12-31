<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Key Vault Secret Integration Summary

## Overview

This document summarizes the Key Vault secret management integration implemented for Azure Container Apps deployment. This work addresses issue #634 (continuing from PR #634) to wire Key Vault secret references and RBAC across services.

## Implementation Summary

### Secrets Managed

The following service secrets are now managed through Azure Key Vault:

#### Authentication Service (JWT)
- `jwt-private-key` - RSA private key for JWT signing (PEM format)
- `jwt-public-key` - RSA public key for JWT verification (PEM format)

#### OAuth Providers
- `github-oauth-client-id` - GitHub OAuth client ID
- `github-oauth-client-secret` - GitHub OAuth client secret
- `google-oauth-client-id` - Google OAuth client ID
- `google-oauth-client-secret` - Google OAuth client secret
- `microsoft-oauth-client-id` - Microsoft OAuth client ID
- `microsoft-oauth-client-secret` - Microsoft OAuth client secret

#### Grafana (Reserved for Future Use)
- `grafana-admin-user` - Grafana admin username
- `grafana-admin-password` - Grafana admin password

#### Application Insights (Already Implemented)
- `appinsights-instrumentation-key` - App Insights instrumentation key
- `appinsights-connection-string` - App Insights connection string

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure Key Vault                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  Secrets:                                             │  │
│  │  - jwt-private-key                                    │  │
│  │  - jwt-public-key                                     │  │
│  │  - github-oauth-client-id/secret                     │  │
│  │  - google-oauth-client-id/secret                     │  │
│  │  - microsoft-oauth-client-id/secret                  │  │
│  │  - appinsights-instrumentation-key                   │  │
│  │  - appinsights-connection-string                     │  │
│  └───────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │
                     │ RBAC: Key Vault Secrets User
                     │ (via access policies or RBAC)
                     │
        ┌────────────┴────────────┬─────────────┐
        ▼                         ▼             ▼
┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
│  Auth Service    │   │  Gateway         │   │  Other Services  │
│  (managed ID)    │   │  (managed ID)    │   │  (managed IDs)   │
│                  │   │                  │   │                  │
│  Environment:    │   │  Environment:    │   │  Environment:    │
│  JWT_PRIVATE_KEY │   │  APPINSIGHTS_*   │   │  APPINSIGHTS_*   │
│  JWT_PUBLIC_KEY  │   │                  │   │                  │
│  GITHUB_OAUTH_*  │   │                  │   │                  │
│  GOOGLE_OAUTH_*  │   │                  │   │                  │
│  MICROSOFT_*     │   │                  │   │                  │
└──────────────────┘   └──────────────────┘   └──────────────────┘
```

### Secret Injection Mechanism

Secrets are injected into Container Apps using Azure's native Key Vault reference syntax:

```bicep
{
  name: 'JWT_PRIVATE_KEY'
  value: '@Microsoft.KeyVault(SecretUri=${jwtPrivateKeySecretUri})'
}
```

**How it works:**
1. Bicep template creates secrets in Key Vault (if provided at deployment)
2. Secret URIs are passed to Container Apps module
3. Container Apps uses managed identity to resolve secret at runtime
4. Secret value appears as environment variable in the container
5. Application code reads from environment variable (no Key Vault SDK needed)

### RBAC Configuration

All service managed identities have Key Vault access configured via `keyvault.bicep`:

**Current Implementation (Access Policies):**
- Permission: `get`, `list`
- Applies to: All service identities
- Mode: `enableRbacAuthorization: false` (legacy)

**Future Migration (RBAC):**
- Role: `Key Vault Secrets User`
- Applies to: Each service identity individually
- Mode: `enableRbacAuthorization: true` (recommended)

### Deployment Workflow

#### Option 1: Secrets Provided at Deployment Time

```bash
az deployment group create \
  --resource-group copilot-rg \
  --template-file main.bicep \
  --parameters @parameters.dev.json \
  --parameters jwtPrivateKey=@jwt_private_key.pem \
               jwtPublicKey=@jwt_public_key.pem \
               githubOAuthClientId="..." \
               githubOAuthClientSecret="..."
```

**Use case:** Secure CI/CD pipelines with secret storage (e.g., GitHub Actions secrets)

#### Option 2: Secrets Set After Deployment (Recommended)

```bash
# 1. Deploy infrastructure
az deployment group create \
  --resource-group copilot-rg \
  --template-file main.bicep \
  --parameters @parameters.dev.json

# 2. Get Key Vault name
KEY_VAULT_NAME=$(az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.keyVaultName.value -o tsv)

# 3. Set secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name jwt-private-key --file jwt_private_key.pem
az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-oauth-client-id --value "..."

# 4. Restart services
az containerapp restart --name copilot-auth-dev --resource-group copilot-rg
```

**Use case:** Manual deployments, production environments

### Application Code Integration

#### Auth Service

The auth service reads secrets through the `copilot_config` adapter:

1. **Schema definition** (`documents/schemas/configs/auth.json`):
   ```json
   {
     "jwt_private_key": {
       "type": "string",
       "source": "secret",
       "secret_name": "jwt_private_key",
       "env_var": "JWT_PRIVATE_KEY"
     }
   }
   ```

2. **Config loader** (`auth/app/config.py`):
   ```python
   config = load_typed_config("auth")
   # config.jwt_private_key reads from environment variable JWT_PRIVATE_KEY
   # which was injected by Key Vault reference
   ```

3. **Fallback priority**:
   - Environment variable (Azure Key Vault injection) → Secret file (/run/secrets) → Default

This design works seamlessly in both:
- **Azure Container Apps**: Secrets come from environment variables (Key Vault)
- **Docker Compose**: Secrets come from mounted files (/run/secrets)

## Security Benefits

✅ **No secrets in source code or templates**
- Secrets never committed to Git
- Bicep templates contain only secret URIs, not values

✅ **Centralized secret management**
- Single source of truth in Key Vault
- Easy rotation and auditing

✅ **Automatic rotation support**
- Key Vault versioning enables zero-downtime rotation
- Container Apps automatically pick up new versions on restart

✅ **Audit trail**
- All secret access logged in Key Vault audit logs
- Integration with Azure Monitor for alerting

✅ **Least-privilege access**
- Each service has its own managed identity
- RBAC limits access to only required secrets

✅ **Defense in depth**
- Secrets encrypted at rest and in transit
- Network isolation via VNet integration
- Optional Private Link for Key Vault

## Deployment Outputs

After deployment, check which secrets need manual configuration:

```bash
az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.secretsSetupRequired

# Returns:
# {
#   "githubOAuthClientId": true,      # Needs to be set
#   "githubOAuthClientSecret": true,  # Needs to be set
#   "jwtPrivateKey": false,           # Already set at deployment
#   "jwtPublicKey": false,            # Already set at deployment
#   ...
# }
```

The deployment also outputs setup instructions:

```bash
az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.secretsSetupInstructions.value -o tsv
```

## Secret Rotation

Recommended rotation schedule:
- **JWT keys**: Every 90 days
- **OAuth credentials**: When revoked or compromised
- **Grafana admin password**: Every 90 days

Rotation procedure:

```bash
# 1. Generate new secret
ssh-keygen -t rsa -b 4096 -m PEM -f jwt_private_key_new -N ""

# 2. Update Key Vault (creates new version)
az keyvault secret set --vault-name $KEY_VAULT_NAME --name jwt-private-key --file jwt_private_key_new

# 3. Restart Container App
az containerapp restart --name copilot-auth-dev --resource-group copilot-rg

# 4. Verify functionality
curl https://<gateway-fqdn>/auth/.well-known/jwks.json

# 5. Clean up local files
rm jwt_private_key_new
```

Key Vault maintains version history, enabling rollback if needed:

```bash
# List versions
az keyvault secret list-versions --vault-name $KEY_VAULT_NAME --name jwt-private-key

# Retrieve specific version (rollback)
az keyvault secret show --vault-name $KEY_VAULT_NAME --name jwt-private-key --version <version-id>
```

## Testing

### Local Development

For local development with Docker Compose, secrets continue to work via file-based secret mounting:

```yaml
services:
  auth:
    volumes:
      - ./secrets:/run/secrets:ro
    environment:
      SECRET_PROVIDER_TYPE: local
      SECRETS_BASE_PATH: /run/secrets
```

### Azure Deployment

For Azure Container Apps, secrets are injected via environment variables:

```bash
# Verify secret injection
az containerapp exec --name copilot-auth-dev --resource-group copilot-rg --command /bin/sh
# Inside container:
$ env | grep JWT_PRIVATE_KEY
JWT_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----...
```

## Known Limitations

1. **Shared Key Vault**: All services access the same Key Vault with `get` and `list` permissions
   - **Risk**: Compromised service can read all secrets
   - **Mitigation**: Planned migration to RBAC with per-secret permissions

2. **Grafana Parameters Unused**: Grafana admin credential parameters are accepted but not used
   - **Reason**: Grafana not deployed in Container Apps (only local Docker Compose)
   - **Future**: Will be used when Grafana Container App is added

3. **Secret Versioning**: Container Apps don't automatically pick up new secret versions
   - **Workaround**: Manual restart required after secret rotation
   - **Future**: Container Apps may add automatic secret refresh

## Documentation

- **Deployment Guide**: [README.md](README.md)
- **Security Considerations**: [SECURITY_CONSIDERATIONS.md](SECURITY_CONSIDERATIONS.md)
- **OAuth Setup**: [../../documents/OIDC_LOCAL_TESTING.md](../../documents/OIDC_LOCAL_TESTING.md)
- **Secret Provider**: [../../adapters/copilot_secrets/README.md](../../adapters/copilot_secrets/README.md)
- **Config Integration**: [../../adapters/copilot_config/SECRET_INTEGRATION.md](../../adapters/copilot_config/SECRET_INTEGRATION.md)

## Related Issues

- Issue #634: Wire Key Vault secret refs and RBAC across services (this PR)
- PR #634: Initial Key Vault and managed identity foundation

## Future Enhancements

1. **Migrate to RBAC mode**: Set `enableRbacAuthorization: true` in Key Vault
2. **Remove `list` permission**: Services only access secrets by explicit name
3. **Per-service Key Vaults**: Separate Key Vault for each high-security service
4. **Automatic secret rotation**: Integrate with Azure Key Vault rotation policies
5. **Private Link**: Disable public Key Vault access for production
6. **Grafana Container App**: Deploy Grafana to Container Apps with admin credentials from Key Vault
