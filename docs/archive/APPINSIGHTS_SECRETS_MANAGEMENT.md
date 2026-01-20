<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Application Insights Secrets Management

## Problem

Previously, Application Insights instrumentation keys and connection strings were:
- Exposed as plaintext outputs from the `appinsights` module
- Passed as plaintext parameters to the Container Apps module
- Stored as plaintext environment variables in Container App definitions

This violates the **zero-secrets approach** and increases the risk of credential exposure in:
- ARM template outputs
- Container App logs
- Deployment history
- Monitoring systems that capture environment variables

## Solution

### Key Vault Storage

All Application Insights credentials are now stored securely in Azure Key Vault:

```bicep
// appinsights-instrumentation-key
resource appInsightsInstrKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = ...

// appinsights-connection-string
resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = ...
```

### Key Vault References in Container Apps

Container Apps reference the secrets via Key Vault URI using the `@Microsoft.KeyVault()` syntax:

```bicep
{
  name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
  value: appInsightsKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsKeySecretUri})' : ''
}

{
  name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
  value: appInsightsConnectionStringSecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsConnectionStringSecretUri})' : ''
}
```

**How it works:**
1. Azure Container Apps detects the `@Microsoft.KeyVault()` reference
2. At runtime, it automatically resolves the secret from Key Vault
3. The secret is **not** stored in the container App definition or logs
4. The managed identity of each Container App is granted read access to the specific secrets

### Managed Identity Access

Each Container App has a user-assigned managed identity with access to Key Vault secrets:

```bicep
identity: {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${identityResourceIds.<service>}': {}
  }
}
```

The Key Vault access policy grants each service's managed identity `get` permission on secrets (no `list` permission for enumeration).

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Application Insights                               │
│  - Instrumentation Key                              │
│  - Connection String                                │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
         ┌─────────────────────┐
         │   Azure Key Vault   │
         │                     │
         │ • appinsights-key   │
         │ • appinsights-conn  │
         └──────────┬──────────┘
                    │
                    ▼
     ┌──────────────────────────────┐
     │  Container Apps Environment  │
     │                              │
     │  Service A (with identity)   │◄────┐
     │  Service B (with identity)   │     │
     │  Service C (with identity)   │     │
     │         ...                  │     │
     │                              │     │
     │  References secrets via:     │     │
     │  @Microsoft.KeyVault(...)    │────┘
     │                              │
     └──────────────────────────────┘
            (Managed Identities)
```

## Security Benefits

1. **No Plaintext Credentials**: Secrets are never exposed in:
   - ARM templates
   - Deployment outputs
   - Container App definitions
   - Environment variables visible via CLI/Portal

2. **Automatic Token Rotation**: Azure manages credential rotation automatically

3. **Audit Trail**: All secret access is logged in Azure Monitor/Key Vault audit logs

4. **Fine-Grained Access**: Each service's managed identity can only read the specific secrets it needs

5. **Separation of Concerns**: Credentials are managed separately from application configuration

## Legacy: Log Analytics Shared Key

The **Log Analytics workspace shared key** was previously used when deploying Container Apps environments configured to send platform logs to Log Analytics.

**Current default:** This repo's Azure templates no longer deploy or depend on Log Analytics (cost savings). Container Apps logs are archived to Blob Storage via Diagnostic Settings instead.

The snippet below is retained for historical context only.

```bicep
appLogsConfiguration: {
  destination: 'log-analytics'
  logAnalyticsConfiguration: {
    customerId: logAnalyticsCustomerId
    sharedKey: listKeys(logAnalyticsWorkspaceId, '2021-12-01-preview').primarySharedKey
  }
}
```

## Implementation Details

### Bicep Modules Updated

1. **appinsights.bicep**
   - Updated output descriptions to clarify secrets should be stored in Key Vault
   - Outputs still available for storage but not passed as plaintext to services

2. **main.bicep**
   - Creates Key Vault secrets for Application Insights credentials
   - Generates secret URIs for Container Apps to reference
   - Removed plaintext secret outputs

3. **containerapps.bicep**
   - Accepts Key Vault secret URIs instead of plaintext secrets
   - Uses `@Microsoft.KeyVault()` syntax in environment variables
   - All 10 services updated with consistent secret reference pattern

### Deployment Flow

```
1. Deploy Application Insights module
   ↓
2. Create Key Vault secrets from Application Insights outputs
   ↓
3. Generate secret URIs (with version info)
   ↓
4. Pass secret URIs to Container Apps module
   ↓
5. Container Apps environment creates services with Key Vault references
   ↓
6. At runtime, managed identities resolve secrets from Key Vault
```

## Verification

To verify secrets are stored securely:

```powershell
# List secrets in Key Vault
az keyvault secret list --vault-name <key-vault-name> --query "[].[name]"

# Check secret metadata (value not displayed)
az keyvault secret show --vault-name <key-vault-name> --name appinsights-instrumentation-key

# View secret access logs
az monitor activity-log list --resource-group <rg> --query "[].[name,properties.statusMessage]"
```

## Migration Guide (Future)

If deploying to a new environment:

1. **Pre-deployment**: Ensure Key Vault exists and managed identities are created
2. **Deployment**: Run `az deployment` with updated Bicep templates
3. **Verification**: Confirm Container Apps are healthy and logging is working

## Testing

### Local Testing

Secrets are resolved at runtime by Container Apps, not during deployment. To test:

```powershell
# Deploy test environment
az deployment group create --resource-group test-rg --template-file main.bicep --parameters parameters.dev.json

# Check Container App environment variables (secrets should show Key Vault reference, not actual value)
az containerapp show --name copilot-auth-dev --resource-group test-rg --query "properties.template.containers[0].env"

# Verify logs are available
# - Default (no Log Analytics): Container Apps logs are archived to Blob Storage via Diagnostic Settings
#   See: docs/operations/blob-logging.md
# - Optional (if you enabled Application Insights in your environment): query recent traces
az monitor app-insights query --app <app-insights-name> --resource-group <rg> --analytics-query "traces | take 10"
```

### Troubleshooting

**Symptoms**: Container App fails to start or logs show errors

**Likely causes**:
1. Managed identity not granted Key Vault access
2. Secret URI is malformed or expired
3. Key Vault secret doesn't exist

**Resolution**:
1. Verify role assignments: `az role assignment list --assignee <principal-id> --scope <keyvault-id>`
2. Check secret URI format matches Container Apps expectations
3. Confirm secrets exist: `az keyvault secret list --vault-name <name>`
4. Review Container App logs: `az containerapp logs show --name <app> --resource-group <rg>`

## Compliance

This implementation meets:
- **Azure Security Best Practices**: Secrets stored in Key Vault, not in configuration
- **SOC 2**: Audit logging of all secret access
- **PCI DSS**: Encryption and access controls for credential storage
- **HIPAA**: Secure credential handling for health data applications

## References

- [Azure Key Vault Documentation](https://learn.microsoft.com/en-us/azure/key-vault/)
- [Container Apps Key Vault References](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)
- [Managed Identities for Azure Resources](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/)
- [Application Insights Overview](https://learn.microsoft.com/en-us/azure/azure-monitor/app/app-insights-overview)
