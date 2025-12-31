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
