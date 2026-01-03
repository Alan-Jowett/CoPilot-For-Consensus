<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Azure Managed Identity Troubleshooting

This document explains how to troubleshoot and fix Azure managed identity authentication issues in Container Apps.

## Problem: DefaultAzureCredential Authentication Failure

### Symptoms

Container Apps fail to start with errors like:
```
DefaultAzureCredential failed to retrieve a token from the included credentials.
ManagedIdentityCredential: App Service managed identity configuration not found in environment.
```

### Root Cause

The Azure SDK's `DefaultAzureCredential` uses multiple authentication methods in order:

1. **Environment variables** (`AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`)
2. **Managed identity** (system-assigned or user-assigned)
3. **Azure CLI credentials** (local development only)

For **user-assigned managed identities**, the SDK requires the `AZURE_CLIENT_ID` environment variable to identify which managed identity to use. Without this variable:
- The SDK cannot detect the user-assigned managed identity
- It falls back to looking for a system-assigned managed identity
- If no system-assigned identity exists, authentication fails

### Solution

Add the `AZURE_CLIENT_ID` environment variable to the Container App configuration with the value set to the managed identity's client ID.

#### Example Fix

**Before:**
```bicep
resource authApp 'Microsoft.App/containerApps@2024-03-01' = {
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.auth}': {}
    }
  }
  properties: {
    template: {
      containers: [
        {
          env: [
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            // Missing AZURE_CLIENT_ID!
          ]
        }
      ]
    }
  }
}
```

**After:**
```bicep
resource authApp 'Microsoft.App/containerApps@2024-03-01' = {
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.auth}': {}
    }
  }
  properties: {
    template: {
      containers: [
        {
          env: [
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.auth  // Client ID of the user-assigned managed identity
            }
          ]
        }
      ]
    }
  }
}
```

## Implementation in This Repository

### Changes Made

1. **`infra/azure/modules/identities.bicep`**
   - Added `identityClientIdsByName` output that provides client IDs for all service identities
   
2. **`infra/azure/main.bicep`**
   - Pass `identityClientIds` parameter to `containerAppsModule`
   
3. **`infra/azure/modules/containerapps.bicep`**
   - Added `identityClientIds` parameter
   - Set `AZURE_CLIENT_ID` environment variable for the auth service

### Services Affected

Currently, only the **auth service** directly accesses Azure Key Vault using SDK-based authentication and requires `AZURE_CLIENT_ID`.

Other services receive Key Vault secrets via the Container Apps platform's built-in Key Vault reference feature (`@Microsoft.KeyVault(SecretUri=...)`), which doesn't require explicit `AZURE_CLIENT_ID` configuration.

## Verification Steps

### 1. Check Managed Identity Configuration

**Linux/macOS (bash):**
```bash
# View the Container App's managed identity
az containerapp show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --query "identity"
```

**Windows (PowerShell):**
```powershell
# View the Container App's managed identity
az containerapp show `
  --name copilot-auth-dev `
  --resource-group copilot-dev-1197027393 `
  --query "identity"
```

Expected output should show:
```json
{
  "type": "UserAssigned",
  "userAssignedIdentities": {
    "/subscriptions/.../copilot-dev-auth-id": {
      "clientId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "principalId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    }
  }
}
```

### 2. Check Environment Variables

**Linux/macOS (bash):**
```bash
# View the Container App's environment variables
az containerapp show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --query "properties.template.containers[0].env"
```

**Windows (PowerShell):**
```powershell
# View the Container App's environment variables
az containerapp show `
  --name copilot-auth-dev `
  --resource-group copilot-dev-1197027393 `
  --query "properties.template.containers[0].env"
```

Verify that `AZURE_CLIENT_ID` is present and matches the `clientId` from step 1.

### 3. Check Key Vault Access

**Linux/macOS (bash):**
```bash
# Verify the managed identity has access to Key Vault
az keyvault show \
  --name <keyvault-name> \
  --query "properties.accessPolicies[?objectId=='<principal-id>']"
```

For RBAC-enabled Key Vaults:
```bash
# Check role assignments
az role assignment list \
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name> \
  --assignee <principal-id>
```

**Windows (PowerShell):**
```powershell
# Verify the managed identity has access to Key Vault
az keyvault show `
  --name <keyvault-name> `
  --query "properties.accessPolicies[?objectId=='<principal-id>']"
```

For RBAC-enabled Key Vaults:
```powershell
# Check role assignments
az role assignment list `
  --scope /subscriptions/<subscription-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name> `
  --assignee <principal-id>
```

### 4. Test JWT Key Access

Once deployed, check the Container App logs:

**Linux/macOS (bash):**
```bash
az containerapp logs show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --follow
```

**Windows (PowerShell):**
```powershell
az containerapp logs show `
  --name copilot-auth-dev `
  --resource-group copilot-dev-1197027393 `
  --follow
```

Look for successful key retrieval messages like:
```
INFO: JWT private key loaded and written to temp file
INFO: JWT public key loaded and written to temp file
INFO: Auth Service initialized with 0 providers
```

## Common Issues and Solutions

### Issue: "403 Forbidden" When Accessing Key Vault

**Cause:** The managed identity doesn't have permission to access Key Vault secrets.

**Solution:**
1. Enable RBAC authorization on Key Vault (recommended)
2. Grant the managed identity the "Key Vault Secrets User" role:

**Linux/macOS (bash):**
```bash
az role assignment create \
  --role "Key Vault Secrets User" \
  --assignee <principal-id> \
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name>
```

Or use access policies (legacy):
```bash
az keyvault set-policy \
  --name <vault-name> \
  --object-id <principal-id> \
  --secret-permissions get list
```

**Windows (PowerShell):**
```powershell
az role assignment create `
  --role "Key Vault Secrets User" `
  --assignee <principal-id> `
  --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<vault-name>
```

Or use access policies (legacy):
```powershell
az keyvault set-policy `
  --name <vault-name> `
  --object-id <principal-id> `
  --secret-permissions get list
```

### Issue: RBAC Permissions Not Propagating

**Cause:** Azure RBAC assignments can take up to 5 minutes to propagate.

**Solution:**
- The deployment script includes retry logic with a 30-second delay between attempts
- Wait for the deployment to complete (may take up to 15 minutes for full RBAC propagation)
- If still failing, manually restart the Container App after waiting 5-10 minutes

### Issue: "Secret Not Found" Errors

**Cause:** Mismatch between secret names used in code vs. names in Key Vault.

**Solution:**
- Key Vault uses **hyphen-separated names**: `jwt-private-key`, `jwt-public-key`
- Python code uses **underscore-separated names**: `jwt_private_key`, `jwt_public_key`
- The `AzureKeyVaultProvider` automatically converts underscores to hyphens
- Verify secrets exist in Key Vault:

**Linux/macOS (bash):**
```bash
az keyvault secret list --vault-name <vault-name> --query "[].name"
```

**Windows (PowerShell):**
```powershell
az keyvault secret list --vault-name <vault-name> --query "[].name"
```

## Best Practices

1. **Use RBAC instead of access policies**
   - Provides per-secret access control
   - Follows principle of least privilege
   - Set `enableRbacAuthorization: true` in Key Vault deployment

2. **Use user-assigned managed identities**
   - More flexible than system-assigned identities
   - Can be shared across multiple resources
   - Easier to manage permissions centrally

3. **Set AZURE_CLIENT_ID for all services using DefaultAzureCredential**
   - Even if you think it might work without it
   - Makes authentication explicit and deterministic
   - Improves startup time (skips other credential checks)

4. **Monitor Key Vault access logs**
   - Enable diagnostic settings on Key Vault
   - Send logs to Log Analytics workspace
   - Set up alerts for authentication failures

## References

- [Azure SDK DefaultAzureCredential](https://learn.microsoft.com/en-us/dotnet/api/azure.identity.defaultazurecredential)
- [Managed Identity Best Practices](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/managed-identity-best-practice-recommendations)
- [Azure Container Apps Managed Identity](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity)
- [Azure Key Vault RBAC](https://learn.microsoft.com/en-us/azure/key-vault/general/rbac-guide)
