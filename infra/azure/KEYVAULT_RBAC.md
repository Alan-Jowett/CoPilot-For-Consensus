<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Key Vault Per-Secret RBAC Access Control

This document explains the Azure Key Vault per-secret RBAC access control implementation that addresses security issue #664.

## Overview

**Problem:** Previously, all service managed identities received vault-wide `get` permission to Azure Key Vault. While `list` permission was removed to prevent enumeration, services could still read ANY secret if they knew its name. This created a critical lateral movement vulnerability.

**Solution:** Implement per-secret RBAC role assignments that grant each service access ONLY to the specific secrets it needs.

## Architecture

### RBAC Model

The implementation uses Azure's built-in **Key Vault Secrets User** role (ID: `4633458b-17de-408a-b874-0445c86b69e6`) with secret-scoped assignments:

- **Secret-scoped assignments**: For secrets known at deployment time (JWT keys, App Insights, OpenAI API key)
- **Manual post-deployment configuration required**: OAuth secrets (see "Configuring OAuth Secret Access" section below)

### Access Matrix

| Service | Secrets Accessed | Scope | Justification |
|---------|-----------------|-------|---------------|
| **auth** | `jwt-private-key` | Secret | Sign JWT tokens |
| **auth** | `jwt-public-key` | Secret | Verify JWT tokens |
| **auth** | OAuth secrets* | Manual | Read OAuth credentials (requires manual RBAC after secret creation) |
| **openai** | `azure-openai-api-key` | Secret | Call Azure OpenAI API |
| **All services** | `appinsights-instrumentation-key` | Secret | Send telemetry |
| **All services** | `appinsights-connection-string` | Secret | Send telemetry |
| **Container Apps** | `grafana-admin-*` | Platform | Grafana container startup |

\* OAuth secrets: `github-oauth-client-id`, `github-oauth-client-secret`, `google-oauth-client-id`, `google-oauth-client-secret`, `microsoft-oauth-client-id`, `microsoft-oauth-client-secret`, `entra-oauth-client-id`, `entra-oauth-client-secret`

**IMPORTANT:** OAuth secrets are created manually after deployment and require manual RBAC configuration. The auth service does NOT receive vault-wide access to maintain least-privilege security.

### Implementation Files

- **`infra/azure/modules/keyvault.bicep`**: Creates Key Vault with RBAC authorization enabled
- **`infra/azure/modules/keyvault-rbac.bicep`**: Configures per-secret role assignments
- **`infra/azure/main.bicep`**: Orchestrates deployment and sets `enableRbacAuthorization: true` by default

## Security Benefits

### Blast Radius Reduction

| Scenario | Before (Vault-Wide Access) | After (Per-Secret RBAC) |
|----------|---------------------------|-------------------------|
| **Auth service compromise** | Can read all secrets (JWT keys, OpenAI key, OAuth, DB credentials) | Can only read JWT keys (OAuth requires separate manual RBAC) |
| **OpenAI service compromise** | Can read all secrets (including JWT private key → forge tokens) | Can only read OpenAI API key |
| **Other service compromise** | Can read all secrets (including JWT private key → full takeover) | Can only read App Insights secrets |
| **Secrets exposed per breach** | 10-15 secrets | 1-3 secrets |
| **Blast radius** | 100% (full environment) | 5-10% (service-specific) |

### Attack Path Prevention

#### Prevented Attack: JWT Key Theft → Full Takeover

**Before (Vulnerable):**
1. Attacker compromises parsing service (e.g., SSRF vulnerability)
2. Parsing service has vault-wide `get` permission
3. Attacker reads `jwt-private-key` from Key Vault
4. Attacker forges JWT tokens with any user identity/roles
5. Attacker impersonates admin, accesses all services
6. **Result:** Full environment compromise

**After (Mitigated):**
1. Attacker compromises parsing service (e.g., SSRF vulnerability)
2. Parsing service only has access to `appinsights-*` secrets
3. Attempt to read `jwt-private-key` → **Forbidden (403)**
4. Attacker cannot forge tokens
5. **Result:** Attack contained to App Insights telemetry (low impact)

#### Prevented Attack: OpenAI Key Exfiltration

**Before (Vulnerable):**
1. Attacker compromises reporting service
2. Reporting service has vault-wide `get` permission
3. Attacker reads `azure-openai-api-key`
4. Attacker uses stolen key for unauthorized OpenAI usage (cost, data exfiltration)
5. **Result:** Unauthorized access to AI resources

**After (Mitigated):**
1. Attacker compromises reporting service
2. Reporting service only has access to `appinsights-*` secrets
3. Attempt to read `azure-openai-api-key` → **Forbidden (403)**
4. **Result:** Attack contained, OpenAI key protected

## Deployment

### Enable RBAC Mode (Default)

RBAC is enabled by default. Deploy normally:

```bash
az deployment group create \
  --resource-group copilot-prod-rg \
  --template-file infra/azure/main.bicep \
  --parameters environment=prod
```

The deployment will:
1. Create Key Vault with `enableRbacAuthorization: true`
2. Deploy all secrets
3. Configure per-secret RBAC role assignments via `keyvault-rbac.bicep`

### Verify RBAC Configuration

After deployment, check the output:

```bash
az deployment group show \
  --resource-group copilot-prod-rg \
  --name main \
  --query properties.outputs.keyVaultRbacSummary.value
```

Expected output:
```
✅ Per-secret RBAC role assignments configured:
- JWT private key: auth service only (secret-scoped)
- JWT public key: auth service only (secret-scoped)
- App Insights secrets: all services (secret-scoped for telemetry)
- Azure OpenAI API key: openai service only (secret-scoped)
- OAuth secrets: NOT CONFIGURED - must be manually assigned post-deployment
- Grafana credentials: accessed via Container Apps platform (no service access needed)

⚠️  IMPORTANT: OAuth secrets require manual RBAC configuration after creation.
```

### Configuring OAuth Secret Access (Post-Deployment)

OAuth secrets (GitHub, Google, Microsoft, Entra) are created manually after initial deployment. To grant the auth service access to these secrets:

**Step 1: Create the OAuth secret in Key Vault**
```bash
# Example: Create GitHub OAuth client ID
az keyvault secret set \
  --vault-name <key-vault-name> \
  --name github-oauth-client-id \
  --value "YOUR_GITHUB_CLIENT_ID"
```

**Step 2: Grant auth service access to the specific secret**
```bash
# Get the auth service principal ID
AUTH_PRINCIPAL_ID=$(az identity show \
  --name copilot-<env>-auth-id \
  --resource-group <resource-group> \
  --query principalId -o tsv)

# Get the secret resource ID
SECRET_ID=$(az keyvault secret show \
  --vault-name <key-vault-name> \
  --name github-oauth-client-id \
  --query id -o tsv)

# Grant "Key Vault Secrets User" role to auth service for this specific secret
az role assignment create \
  --assignee $AUTH_PRINCIPAL_ID \
  --role "Key Vault Secrets User" \
  --scope $SECRET_ID
```

**Step 3: Repeat for all OAuth secrets**
```bash
# Repeat steps above for:
# - github-oauth-client-secret
# - google-oauth-client-id
# - google-oauth-client-secret
# - microsoft-oauth-client-id
# - microsoft-oauth-client-secret
# - entra-oauth-client-id
# - entra-oauth-client-secret
```

**Security Note:** This approach maintains strict least-privilege principles. The auth service receives access ONLY to the specific OAuth secrets you explicitly configure, not vault-wide access to all secrets.

### Legacy Access Policy Mode (Not Recommended)

To use legacy access policies (vault-wide `get` permission):

```bash
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file infra/azure/main.bicep \
  --parameters environment=dev enableRbacAuthorization=false
```

**WARNING:** This mode is NOT RECOMMENDED for production. All services will have vault-wide access to secrets.

## Testing

### Verify Service Access (Positive Test)

Test that the auth service can read JWT keys:

```bash
# Get auth service identity
AUTH_PRINCIPAL_ID=$(az identity show \
  --name copilot-prod-auth-id \
  --resource-group copilot-prod-rg \
  --query principalId -o tsv)

# Check role assignments for JWT private key
az role assignment list \
  --scope "/subscriptions/{subscription-id}/resourceGroups/copilot-prod-rg/providers/Microsoft.KeyVault/vaults/{vault-name}/secrets/jwt-private-key" \
  --assignee $AUTH_PRINCIPAL_ID
```

Expected: Role assignment with `Key Vault Secrets User` role should exist.

### Verify Access Denial (Negative Test)

Test that the parsing service CANNOT read JWT private key:

```bash
# Get parsing service identity
PARSING_PRINCIPAL_ID=$(az identity show \
  --name copilot-prod-parsing-id \
  --resource-group copilot-prod-rg \
  --query principalId -o tsv)

# Check role assignments for JWT private key
az role assignment list \
  --scope "/subscriptions/{subscription-id}/resourceGroups/copilot-prod-rg/providers/Microsoft.KeyVault/vaults/{vault-name}/secrets/jwt-private-key" \
  --assignee $PARSING_PRINCIPAL_ID
```

Expected: No role assignments (empty result). Parsing service cannot access JWT private key.

## Troubleshooting

### Service Cannot Access Required Secret

**Symptom:** Service logs show "Access denied" or "Forbidden" when reading a secret.

**Diagnosis:**
1. Check which identity the service is using:
   ```bash
   az containerapp show \
     --name copilot-prod-{service}-app \
     --resource-group copilot-prod-rg \
     --query identity.userAssignedIdentities
   ```

2. Verify role assignments for the secret:
   ```bash
   az role assignment list \
     --scope "/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.KeyVault/vaults/{vault}/secrets/{secret-name}"
   ```

**Resolution:**
- If identity is missing: Check that the service was deployed with the correct managed identity
- If role assignment is missing: Redeploy the `keyvault-rbac` module
- If secret doesn't exist: Create the secret first, then redeploy RBAC module

### OAuth Secrets Not Accessible by Auth Service

**Symptom:** Auth service cannot read OAuth secrets (GitHub, Google, Microsoft, Entra).

**Diagnosis:**
Check if secret-specific role assignments exist for the OAuth secret:

```bash
AUTH_PRINCIPAL_ID=$(az identity show --name copilot-prod-auth-id --resource-group copilot-prod-rg --query principalId -o tsv)
SECRET_ID=$(az keyvault secret show --vault-name {vault-name} --name github-oauth-client-id --query id -o tsv)

az role assignment list --scope $SECRET_ID --assignee $AUTH_PRINCIPAL_ID
```

**Resolution:**
OAuth secrets require manual RBAC configuration after creation (by design, to maintain least-privilege):

1. Ensure the OAuth secret has been created in Key Vault
2. Grant auth service access to the specific secret:
   ```bash
   az role assignment create \
     --assignee $AUTH_PRINCIPAL_ID \
     --role "Key Vault Secrets User" \
     --scope $SECRET_ID
   ```
3. Repeat for each OAuth secret the auth service needs to access
4. See "Configuring OAuth Secret Access" section above for complete instructions

**Security Note:** The auth service does NOT receive vault-wide access. Each OAuth secret must be explicitly granted access individually to maintain strict least-privilege security.

## Compliance

This implementation addresses the following compliance requirements:

- **NIST SP 800-53 AC-6**: Least Privilege - Each service has minimum permissions required
- **SOC2 CC6.3**: Logical Access Controls - Per-secret authorization enforced
- **ISO 27001 A.9.4**: System and Application Access Control - Fine-grained access matrix
- **PCI-DSS 7.1.2**: Need-to-Know Access - Services cannot access secrets they don't need

## References

- [Azure Key Vault Best Practices](https://learn.microsoft.com/en-us/azure/key-vault/general/best-practices)
- [Azure RBAC for Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide)
- [Key Vault Secrets User Role](https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#key-vault-secrets-user)
- [NIST SP 800-53 AC-6: Least Privilege](https://csrc.nist.gov/projects/cprt/catalog#/cprt/framework/version/SP_800_53_5_1_1/home?element=AC-6)

## Migration Notes

### From Legacy Access Policies

If you have an existing deployment using legacy access policies (`enableRbacAuthorization: false`):

1. **Plan maintenance window**: Brief service restarts may occur during role assignment propagation
2. **Update deployment**: Change `enableRbacAuthorization: true` in your parameters
3. **Redeploy**: Run deployment to create RBAC role assignments
4. **Verify**: Check `keyVaultRbacSummary` output confirms RBAC is active
5. **Monitor**: Watch service logs for any access denied errors
6. **Rollback plan**: Keep `enableRbacAuthorization: false` parameter available if issues arise

### Adding New Secrets

When adding new secrets that services need to access:

1. **Add secret**: Create the secret in Key Vault (via Bicep or CLI)
2. **Update `keyvault-rbac.bicep`**: Add role assignment resource for the new secret
3. **Redeploy**: Deploy the updated RBAC module
4. **Test**: Verify the service can access the new secret

### Adding New Services

When adding a new service that needs Key Vault access:

1. **Create managed identity**: Add to `identities.bicep`
2. **Update access matrix**: Determine which secrets the service needs
3. **Update `keyvault-rbac.bicep`**: Add role assignments for the new service
4. **Redeploy**: Deploy the updated RBAC module
5. **Test**: Verify the new service can access required secrets

---

**Last Updated:** 2026-01-01  
**Related Issues:** #664 (Critical: Key Vault access policies grant excessive permissions)  
**Related PRs:** [This PR implementing per-secret RBAC]
