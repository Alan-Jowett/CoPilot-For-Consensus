<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Security Considerations for Azure Infrastructure

This document outlines known security considerations and recommended improvements for the Azure deployment.

## Current Security Posture (PR #1)

### Shared Key Vault with Broad Permissions

**Current Implementation:**
- All 10 microservice identities have `get` and `list` permissions on a single shared Key Vault
- Any compromised service identity can enumerate and read **all** secrets in the vault

**Risk:**
- **High lateral movement risk**: Compromise of one service leads to credential exposure for all services
- **Blast radius**: Single breach affects entire system

**Mitigation Options (for future PRs):**

1. **Separate Key Vaults per Service** (Most Secure)
   - Each service gets its own Key Vault
   - Requires more management overhead
   - Best for high-security production deployments

2. **Remove `list` Permission** (Quick Win)
   - Services can only read secrets they explicitly know about (by name)
   - Prevents enumeration attacks
   - Reduces blast radius without infrastructure changes

3. **Migrate to Azure RBAC** (Recommended)
   - Use `enableRbacAuthorization: true` on Key Vault
   - Assign granular RBAC roles per identity
   - Modern approach, better audit trails

**Status:** Known limitation in PR #1 (Foundation Layer). Will address in PR #5 (Container Apps) when secret names are defined.

### Access Authorization Approach: Legacy Access Policies vs. Azure RBAC

**Current Implementation (PR #1):**
- Uses legacy Access Policies for backward compatibility
- Parameter `enableRbacAuthorization: false` in `keyvault.bicep`

**Why Access Policies (Temporary):**
- Fastest validation path for PR #1 foundation layer
- Works with existing Bicep patterns
- Well-documented and proven approach

**Why RBAC is Better (Future):**
- **Modern**: Officially recommended by Microsoft
- **Audit**: Better integration with Azure Policy and activity logs
- **Granular**: Separate permissions per service via RBAC roles
- **Consistent**: Same authorization model as other Azure services

**Migration Plan (PRs #2-5):**
1. Set `enableRbacAuthorization: true` when PR #2 (Service Bus) is merged
2. Replace Access Policies with RBAC role assignments:
   - Service identities get `Key Vault Secrets User` role
   - Remove hardcoded secret access patterns
3. Remove `accessPoliciesArray` completely once migration done

**Status:** Access Policies in PR #1, RBAC migration starts in PR #2.

---

---

## Subscription-Level Contributor Access

**Current Implementation:**
- GitHub OIDC service principal has `Contributor` role on entire subscription
- Required for CI/CD to create resource groups and validate deployments
- Federated credentials grant access for BOTH main branch deployments AND pull requests

**Critical Risk - GitHub PR Execution:**
- ⚠️ **Pull requests from ANY contributor trigger CI/CD with full Contributor permissions**
- Includes PRs from forks and external contributors
- Malicious PR can deploy infrastructure, modify data, exfiltrate secrets
- Validation runs BEFORE merge approval, so risk applies to all PRs

**Why This Matters:**
- PR CI/CD runs before human review of the pull request content
- Bicep templates in PRs execute with full permissions (ARM validation, what-if analysis)
- Attacker doesn't need code merge approval to execute arbitrary deployments
- No way to distinguish between legitimate development PR and malicious PR at runtime

**Mitigation Options:**

### Option 1: **Scope to Validation-Only Resource Group** (RECOMMENDED)

**How it works:**
- Assign `Contributor` role to specific resource group (e.g., `copilot-bicep-validation-rg`)
- Pre-create this RG before enabling CI/CD
- All PR deployments happen in this isolated RG
- Validation still works, but blast radius is contained

**Implementation:**
```bash
# Create validation resource group
az group create --name copilot-bicep-validation-rg --location westus

# Scope service principal to this RG only
az role assignment create \
  --role "Contributor" \
  --assignee <service-principal-id> \
  --resource-group copilot-bicep-validation-rg
```

**Then remove subscription-level Contributor role:**
```bash
# List all role assignments for the service principal
az role assignment list --assignee <service-principal-id>

# Remove Contributor from subscription scope (keep only RG scope)
az role assignment delete \
  --assignee <service-principal-id> \
  --role "Contributor" \
  --scope "/subscriptions/<subscription-id>"
```

**Pros:**
- Simple to implement
- Isolates PR validation to specific RG
- Malicious PR can't affect production or other services
- Still allows full Bicep validation

**Cons:**
- CI/CD can only validate for specific RG (not production deployment)
- Requires manual promotion of validated changes to production

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

**RECOMMENDED ACTION FOR PR #1:**

✅ **Implement Option 1 immediately** (Scope to Validation RG):
1. Create resource group: `copilot-bicep-validation-rg`
2. Assign service principal Contributor role to **this RG only**
3. Remove subscription-level Contributor assignment
4. Update workflow to deploy validations to this RG
5. Document that production deployments require manual setup

This provides immediate security improvement while keeping CI/CD functional.

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
