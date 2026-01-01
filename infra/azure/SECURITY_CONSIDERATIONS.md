<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Security Considerations for Azure Infrastructure

This document outlines security considerations and improvements for the Azure deployment.

## ✅ RESOLVED: Key Vault Access Control (Issue #664)

### Per-Secret RBAC Implementation (IMPLEMENTED)

**Current Implementation (Post-Issue #664):**
- ✅ Azure RBAC enabled by default (`enableRbacAuthorization: true`)
- ✅ Per-secret role assignments via `keyvault-rbac.bicep` module
- ✅ Each service granted access ONLY to specific secrets it needs
- ✅ Significantly reduced lateral movement risk

**Access Matrix:**
- **Auth Service**: JWT keys (private/public), OAuth secrets (GitHub, Google, Microsoft, Entra)
- **OpenAI Service**: Azure OpenAI API key only
- **All Services**: App Insights secrets (telemetry)
- **No Services**: Grafana credentials (accessed via Container Apps platform)

**Security Improvement:**
- **Before**: All 11 services had vault-wide `get` permission to ALL secrets
  - Compromised service could read JWT keys, forge tokens, impersonate users
  - Attacker could exfiltrate OpenAI keys, OAuth secrets, database credentials
  - Full environment takeover from single service compromise
- **After**: Each service can only access specific secrets it needs
  - Auth service compromise: Cannot access OpenAI keys or service-specific secrets
  - OpenAI service compromise: Cannot access JWT keys or OAuth secrets
  - Other service compromise: Cannot access JWT private key or forge tokens
  - Blast radius reduced by ~90% (1-2 secrets per service vs. all secrets)

**Migration from Legacy Access Policies:**
- Default changed from `enableRbacAuthorization: false` to `true`
- Legacy access policies still available for backward compatibility
- To use legacy mode: Set `enableRbacAuthorization: false` in deployment parameters
- **NOT RECOMMENDED** for production: Legacy mode grants vault-wide access

**Status:** ✅ IMPLEMENTED (Issue #664). Per-secret RBAC is now the default authorization mode.

---

---

## Subscription-Level Contributor Access

**Current Implementation (FIXED):**
- GitHub OIDC service principal has `Contributor` role **SCOPED to validation resource group only**
- Service principal has `User Access Administrator` role **SCOPED to validation resource group only**
- Required for CI/CD to validate deployments in isolated environment
- Federated credentials grant access for BOTH main branch deployments AND pull requests, but with limited blast radius

**Security Improvement (Implemented):**
- ✅ **PR validations are LIMITED to `copilot-bicep-validation-rg` only**
- ✅ Malicious PRs CANNOT access or modify resources outside this resource group
- ✅ No subscription-level permissions granted
- ✅ Production deployments require manual setup with appropriate permissions

**Previous Risk (Now Mitigated):**
- ⚠️ Pull requests from ANY contributor previously had subscription-level Contributor permissions
- ⚠️ Could deploy infrastructure, modify data, exfiltrate secrets anywhere in subscription
- ✅ **NOW FIXED**: Permissions scoped to validation RG only

**How It Works:**
- `setup-github-oidc.sh` creates validation resource group if it doesn't exist
- Assigns `Contributor` role to the validation RG only (NOT subscription)
- All PR deployments happen in this isolated RG
- Validation still works, blast radius is contained

**Mitigation Options (For Reference):**

The following options were considered, and **Option 1 has been implemented** in the current setup:

### Option 1: **Scope to Validation-Only Resource Group** (✅ IMPLEMENTED)

**How it works:**
- Assign `Contributor` role to specific resource group (e.g., `copilot-bicep-validation-rg`)
- Pre-create this RG before enabling CI/CD
- All PR deployments happen in this isolated RG
- Validation still works, but blast radius is contained

**Implementation:**
```bash
# This is now handled automatically by setup-github-oidc.sh
# The script creates the validation RG if it doesn't exist
# and scopes all permissions to it automatically
./setup-github-oidc.sh
```

**Status: ✅ IMPLEMENTED**
- The `setup-github-oidc.sh` script now automatically creates the validation resource group
- Contributor and User Access Administrator roles are scoped to validation RG only
- No manual steps required - security is built-in by default

**Pros:**
- ✅ Simple to implement
- ✅ Isolates PR validation to specific RG
- ✅ Malicious PR can't affect production or other services
- ✅ Still allows full Bicep validation
- ✅ **NOW IMPLEMENTED BY DEFAULT**

**Cons:**
- CI/CD can only validate for specific RG (not production deployment)
- Requires manual promotion of validated changes to production (this is actually a security feature)

### Option 2: **Custom RBAC Role with Limited Permissions** (MOST SECURE)

Create custom role that allows ONLY validation operations:
```json
{
  "Name": "Bicep Validation Only",
  "IsCustom": true,
  "Permissions": [
    {
      "Actions": [
        "Microsoft.Resources/deployments/validate/action",
        "Microsoft.Resources/deployments/whatIf/action"
      ],
      "NotActions": [],
      "DataActions": [],
      "NotDataActions": []
    }
  ],
  "AssignableScopes": [
    "/subscriptions/<subscription-id>"
  ]
}
```

**Pros:**
- No unintended resource creation possible
- Validates templates without actual deployment
- Most restrictive

**Cons:**
- CI/CD cannot create temporary RGs for validation
- Still need some permissions to read existing infrastructure

### Option 3: **Disable PR Validation for Untrusted Forks** (PROCESS CONTROL)

Modify workflow to:
- Only run Tier 2 validation (what-if/deployment) on approved PRs
- PR validation from forks runs Tier 1 only (Bicep lint)
- Requires `pull_request_target` event with approval gates

**Pros:**
- Prevents automatic malicious deployments
- Still validates syntax for open-source contributors

**Cons:**
- Blocks legitimate contributor feedback
- Extra manual approval steps
- GitHub Actions matrix requires careful configuration

### Option 4: **Separate Service Principal for PR Validation** (HYBRID)

Create TWO service principals:
1. **PR Validation SP**: Limited permissions (validate/whatIf only)
2. **Production Deployment SP**: Full Contributor (for main branch only)

Use different credentials based on branch/event.

**Pros:**
- Granular control per workflow type
- Full functionality, limited blast radius

**Cons:**
- Operational complexity
- Two separate OIDC setups to maintain

---

## Public Network Access to Key Vault

**Current Implementation:**
- Key Vault has `publicNetworkAccess: Enabled` by default
- Accessible from public internet (though requires Azure AD authentication)

**Risk:**
- **External attack surface**: Brute-force or credential stuffing attacks possible
- **No network isolation**: No defense-in-depth layer

**Mitigation:**

**Implemented in PR #1:**
- Added `enablePublicNetworkAccess` parameter to `keyvault.bicep`
- Can be disabled per environment in parameter files

**Recommended for Production:**
```bicep
// In parameters.prod.json
"enablePublicNetworkAccess": {
  "value": false
}
```

Then configure Azure Private Link/Private Endpoints to restrict access to VNet only.

**Status:** Configurable. Safe for dev/test. Should be disabled for production with Private Link.

---

## Future Improvements (Upcoming PRs)

### PR #2: Service Bus
- Use managed identities for authentication (no connection strings)
- Apply least-privilege roles per service (e.g., `Azure Service Bus Data Sender` only for ingestion)

### PR #3: Cosmos DB
- Use managed identities with RBAC
- Scope data plane permissions per service (read-only vs read-write)

### PR #4: Azure OpenAI
- Use managed identities with `Cognitive Services User` role
- Avoid storing API keys in Key Vault

### PR #5: Container Apps
- Remove Key Vault `list` permission (use explicit secret names)
- Consider per-service Key Vault separation
- Implement network policies for pod-to-pod isolation

---

## Service Secrets and Key Vault Integration (Updated)

### Secrets Managed in Key Vault

The following secrets are managed through Azure Key Vault:

| Secret Name | Used By | Purpose | How Set |
|-------------|---------|---------|---------|
| `jwt-private-key` | Auth | JWT signing (RS256) | **Auto-generated** via deployment script |
| `jwt-public-key` | Auth | JWT verification (RS256) | **Auto-generated** via deployment script |
| `github-oauth-client-id` | Auth | GitHub OAuth authentication | Manual (post-deployment) |
| `github-oauth-client-secret` | Auth | GitHub OAuth authentication | Manual (post-deployment) |
| `google-oauth-client-id` | Auth | Google OAuth authentication | Manual (post-deployment) |
| `google-oauth-client-secret` | Auth | Google OAuth authentication | Manual (post-deployment) |
| `microsoft-oauth-client-id` | Auth | Microsoft OAuth authentication | Manual (post-deployment) |
| `microsoft-oauth-client-secret` | Auth | Microsoft OAuth authentication | Manual (post-deployment) |
| `grafana-admin-user` | Grafana | Grafana admin login | Manual (future use) |
| `grafana-admin-password` | Grafana | Grafana admin login | Manual (future use) |
| `appinsights-instrumentation-key` | All services | Application monitoring | Auto-created |
| `appinsights-connection-string` | All services | Application monitoring | Auto-created |

### Secret Access Mechanism

Services access secrets via the Azure Key Vault provider (SDK-based), not environment variable injection:

```python
# Auth service configuration
config = load_typed_config("auth")
# Automatically reads from Key Vault using managed identity
jwt_private_key = config.jwt_private_key
```

The `copilot_secrets` adapter with `AzureKeyVaultProvider`:
- Uses managed identity authentication (no credentials needed)
- Automatically normalizes secret names (underscores → hyphens)
- Caches secrets in memory for performance
- Works seamlessly with local file-based secrets in Docker Compose

**Security Benefits:**
- ✅ No secrets in environment variables (not exposed via `env` command)
- ✅ Secrets never stored in Bicep templates or Git
- ✅ Managed identity authentication (no credentials to rotate)
- ✅ All secret access logged in Key Vault audit logs
- ✅ Secrets encrypted at rest and in transit

### JWT Key Generation

JWT keys are automatically generated during each deployment via `jwtkeys.bicep`:
- Uses Azure CLI container with openssl to generate RSA 3072-bit keypair
- Stores keys directly in Key Vault using deployment script managed identity
- Keys persist across deployments unless `jwtForceUpdateTag` parameter changes
- No manual key generation or upload required

**To regenerate keys** (invalidates all active sessions):
```bash
az deployment group create \
  --parameters jwtForceUpdateTag="$(date +%s)"
```

### OAuth Secret Setup

OAuth secrets must be set manually after deployment:

```bash
KEY_VAULT_NAME=$(az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.keyVaultName.value -o tsv)

az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-oauth-client-id --value "YOUR_CLIENT_ID"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-oauth-client-secret --value "YOUR_CLIENT_SECRET"

# Restart auth service
az containerapp restart --name copilot-auth-dev --resource-group copilot-rg
```

See [README.md](README.md#post-deployment-configuration) for complete OAuth setup instructions.

---

## Security Testing (Recommended)

Once full deployment is complete:

1. **Penetration Testing**
   - Simulate compromised service identity
   - Verify blast radius is contained

2. **Azure Security Center**
   - Enable Defender for Cloud
   - Review security recommendations for Key Vault, identities, and networking

3. **Audit Logs**
   - Enable diagnostic settings on Key Vault
   - Monitor for unusual secret access patterns

---

## References

- [Azure Key Vault Security](https://learn.microsoft.com/azure/key-vault/general/security-features)
- [Managed Identity Best Practices](https://learn.microsoft.com/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)
- [Azure RBAC for Key Vault](https://learn.microsoft.com/azure/key-vault/general/rbac-guide)
- [Least Privilege Access](https://learn.microsoft.com/azure/security/fundamentals/identity-management-best-practices#enable-the-principle-of-least-privilege)
