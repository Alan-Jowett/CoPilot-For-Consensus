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

---

## Subscription-Level Contributor Access

**Current Implementation:**
- GitHub OIDC service principal has `Contributor` role on entire subscription
- Required for CI/CD to create resource groups and validate deployments

**Risk:**
- **Overly broad permissions**: Compromised GitHub workflow could affect unrelated resource groups
- **Attack surface**: Any PR with malicious Bicep templates could deploy resources anywhere in subscription

**Mitigation Options:**

1. **Scope to Resource Group** (Recommended for Production)
   - Assign `Contributor` only to specific RG used for validation
   - Requires pre-creating RG before CI/CD runs
   - Best practice: `az role assignment create --scope /subscriptions/.../resourceGroups/copilot-validation-rg`

2. **Custom RBAC Role** (Most Secure)
   - Create custom role with only required permissions:
     - `Microsoft.Resources/deployments/*`
     - `Microsoft.Resources/subscriptions/resourceGroups/read`
     - `Microsoft.ManagedIdentity/*` (for validation only)
     - `Microsoft.KeyVault/vaults/read` (for validation only)
   - Deny actual resource creation except in specific RGs

3. **Branch Protection + Manual Review** (Process Control)
   - Require manual approval for Bicep changes before CI runs
   - Use GitHub Environments with required reviewers
   - Reduces risk of malicious PR abuse

**Status:** Known tradeoff in PR #1. Suitable for dev/test subscriptions. Recommend scoping for production deployments.

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
