# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# GitHub OIDC Secret Automation

This guide explains how GitHub OIDC credentials are automatically deployed to Azure Key Vault during infrastructure deployment via Bicep.

## Overview

GitHub OIDC credentials (Client ID and Client Secret) are sensitive data that must be securely stored and managed. The deployment process automates uploading these secrets from the local `secrets/` directory to Azure Key Vault without requiring manual steps.

## File Structure

```
secrets/
├── github_oauth_client_id          # GitHub OAuth application client ID
└── github_oauth_client_secret      # GitHub OAuth application client secret

infra/azure/
├── deploy.ps1                      # Main deployment script (reads secrets and passes to Bicep)
├── main.bicep                       # Main infrastructure template (creates Key Vault and secret resources)
└── GITHUB_OIDC_SECRETS_AUTOMATION.md # This guide
```

## Deployment Flow

```
deploy.ps1
  ↓
  1. Reads secrets from ./secrets/ directory
  2. Validates Bicep template
  3. Deploys infrastructure (including Key Vault secret resources)
  4. Azure creates secrets in Key Vault during deployment
  ↓
Done - secrets are now in Key Vault
```

## How It Works

### 1. Prepare Local Secrets

Before deploying, create the secrets files in the repository (not tracked by git):

```bash
# GitHub OIDC Client ID
echo "your-github-client-id" > secrets/github_oauth_client_id

# GitHub OIDC Client Secret
echo "your-github-client-secret" > secrets/github_oauth_client_secret
```

**Important:** Ensure `secrets/` is in `.gitignore` to prevent accidental commits.

### 2. Run Deployment

```powershell
cd infra/azure

# Deploy infrastructure with secrets
.\deploy.ps1 -ResourceGroup "my-resource-group" -ProjectName "copilot"
```

### 3. Secrets Automatically Deployed via Bicep

The deployment flow:

1. **`deploy.ps1` reads secrets** from `./secrets/github_oauth_client_id` and `./secrets/github_oauth_client_secret`
2. **Passes them as Bicep parameters:** `githubOAuthClientId` and `githubOAuthClientSecret`
3. **`main.bicep` creates secrets** in Azure Key Vault as part of infrastructure deployment:
   - `github-oauth-client-id`
   - `github-oauth-client-secret`

Everything happens in the Bicep template—no separate scripts needed.

## Bicep Implementation

In `main.bicep`, parameters are defined:

```bicep
@description('GitHub OAuth application client ID (optional, stored in Key Vault)')
@secure()
param githubOAuthClientId string = ''

@description('GitHub OAuth application client secret (optional, stored in Key Vault)')
@secure()
param githubOAuthClientSecret string = ''
```

Secrets are created as Key Vault resources:

```bicep
resource githubOAuthClientIdSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (githubOAuthClientId != '') {
  name: '${keyVaultName}/github-oauth-client-id'
  properties: {
    value: githubOAuthClientId
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
}

resource githubOAuthClientSecretSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (githubOAuthClientSecret != '') {
  name: '${keyVaultName}/github-oauth-client-secret'
  properties: {
    value: githubOAuthClientSecret
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
}
```

## PowerShell Implementation

In `deploy.ps1`, secrets are read and passed to Bicep:

```powershell
# Read GitHub OIDC secrets if they exist
$SecretsDir = Join-Path $ScriptDir "../../secrets"
$githubClientId = ""
$githubClientSecret = ""

$clientIdFile = Join-Path $SecretsDir "github_oauth_client_id"
$clientSecretFile = Join-Path $SecretsDir "github_oauth_client_secret"

if (Test-Path $clientIdFile) {
    $githubClientId = (Get-Content $clientIdFile -Raw).Trim()
    Write-Info "Found GitHub OAuth client ID secret"
}

if (Test-Path $clientSecretFile) {
    $githubClientSecret = (Get-Content $clientSecretFile -Raw).Trim()
    Write-Info "Found GitHub OAuth client secret"
}

# Pass to Bicep during deployment
Invoke-AzCli deployment group create `
    --name $DeploymentName `
    --resource-group $ResourceGroup `
    --template-file $TemplatePath `
    --parameters "@$ParametersPath" ... `
        githubOAuthClientId="$githubClientId" `
        githubOAuthClientSecret="$githubClientSecret" | Out-Null
```

## Viewing Secrets in Key Vault

After deployment, verify secrets are in Key Vault:

```bash
# List all secrets
az keyvault secret list --vault-name copilot-kv-xxxxx --query "[].name"

# View a specific secret value (requires Key Vault read permissions)
az keyvault secret show --vault-name copilot-kv-xxxxx --name github-oauth-client-id
```

## Accessing Secrets from Applications

Services access GitHub OIDC secrets from Key Vault using managed identity:

### Via Environment Variables (Container Apps)

Container Apps automatically inject secrets from Key Vault as environment variables:

```bicep
# In container app definition
environmentVariables: [
  {
    name: 'GITHUB_OAUTH_CLIENT_ID'
    secretRef: 'github-oauth-client-id'
  }
  {
    name: 'GITHUB_OAUTH_CLIENT_SECRET'
    secretRef: 'github-oauth-client-secret'
  }
]
```

### Via Application Code (Python)

Use Azure SDK to read secrets:

```python
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

# Authenticate with managed identity
credential = DefaultAzureCredential()
client = SecretClient(vault_url="https://copilot-kv-xxxxx.vault.azure.net/", credential=credential)

# Retrieve secrets
client_id = client.get_secret("github-oauth-client-id")
client_secret = client.get_secret("github-oauth-client-secret")
```

## Security Best Practices

### Local Development

1. **Never commit secrets** - Ensure `secrets/` is in `.gitignore`
2. **Use restricted file permissions** - Set `chmod 600` on secret files
3. **Rotate regularly** - Update GitHub OAuth app credentials periodically
4. **Use environment-specific values** - Different credentials for dev/staging/prod

### Azure Key Vault

1. **Enable Azure RBAC** - Use `enableRbacAuthorization: true` in Bicep (default)
2. **Least-privilege access** - Grant services access only to secrets they need
3. **Enable soft delete** - Allows recovery if secrets are accidentally deleted
4. **Monitor access** - Use Azure Monitor and Key Vault logging
5. **Use Private Link** - Set `enablePublicNetworkAccess: false` for production

### Bicep Templates

1. **Use `@secure()` decorator** - Masks parameter values in logs and outputs
2. **Conditional creation** - Secrets only created if parameter values are provided (`if (githubOAuthClientId != '')`)
3. **Depend on Key Vault** - Secret resources depend on Key Vault module

### CI/CD Integration (GitHub Actions)

To deploy from CI/CD without storing local files:

```yaml
# .github/workflows/deploy.yml
- name: Deploy to Azure
  run: |
    # Set up credentials from GitHub secrets
    echo "${{ secrets.GITHUB_OAUTH_CLIENT_ID }}" > secrets/github_oauth_client_id
    echo "${{ secrets.GITHUB_OAUTH_CLIENT_SECRET }}" > secrets/github_oauth_client_secret
    
    # Run deployment (secrets are read and passed to Bicep)
    cd infra/azure
    .\deploy.ps1 -ResourceGroup "${{ secrets.AZURE_RESOURCE_GROUP }}"
    
    # Clean up
    Remove-Item -Path secrets/github_oauth_client_id
    Remove-Item -Path secrets/github_oauth_client_secret
```

## Updating Secrets

To update GitHub OIDC credentials:

1. Update local secret files:
   ```bash
   echo "new-client-id" > secrets/github_oauth_client_id
   echo "new-client-secret" > secrets/github_oauth_client_secret
   ```

2. Re-run deployment:
   ```powershell
   .\deploy.ps1 -ResourceGroup "my-resource-group"
   ```

3. Azure will update the Key Vault secrets during deployment
4. Restart affected services (e.g., auth service) to pick up new values

## Troubleshooting

### Secrets Not Created

If secrets are not created in Key Vault:
- Verify secret files exist: `Test-Path secrets/github_oauth_client_id`
- Check deployment logs for errors
- Verify Key Vault was created successfully

### Authentication Fails

If deployment fails with authentication error:
- Ensure you're logged in to Azure: `az login`
- Verify you have subscription access: `az account show`

### Template Validation Fails

If template validation fails:
- Verify secrets parameters are being passed correctly
- Check for special characters in secret values that need escaping

### Secrets Not Injected in Services

If services can't access secrets:
- Verify service has managed identity enabled
- Check managed identity has Key Vault read permissions
- Verify secret names match (e.g., `github-oauth-client-id` not `GITHUB_OAUTH_CLIENT_ID`)

## Files Modified

- `infra/azure/main.bicep` - Added parameters and Key Vault secret resources
- `infra/azure/deploy.ps1` - Updated to read local secret files and pass values directly to Bicep parameters
- `infra/azure/GITHUB_OIDC_SECRETS_AUTOMATION.md` - This guide

## See Also

- [Azure Key Vault Documentation](https://learn.microsoft.com/en-us/azure/key-vault/)
- [Azure Managed Identity](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview)
- [GitHub OIDC Setup](./GITHUB_OIDC_SETUP.md)
- [Key Vault RBAC](./KEYVAULT_RBAC.md)
- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/overview)
