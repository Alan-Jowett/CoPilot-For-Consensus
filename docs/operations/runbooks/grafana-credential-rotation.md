<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Grafana Admin Credential Rotation Runbook

This runbook describes how to rotate Grafana admin credentials for both local/docker-compose deployments and Azure Container Apps deployments.

## Table of Contents

- [Overview](#overview)
- [Local/Docker-Compose Rotation](#localdocker-compose-rotation)
- [Azure Container Apps Rotation](#azure-container-apps-rotation)
- [Verification Steps](#verification-steps)
- [Rollback Procedures](#rollback-procedures)
- [Troubleshooting](#troubleshooting)

## Overview

Grafana admin credentials should be rotated regularly as part of security best practices. The rotation process differs between local development environments and Azure deployments:

- **Local/Docker-Compose**: Uses file-based secrets in the `secrets/` directory
- **Azure Container Apps**: Uses Azure Key Vault for secure secret storage (when Grafana is deployed as a Container App)

**Recommended rotation frequency**: Every 90 days or when:
- A team member with admin access leaves the organization
- Credentials may have been compromised
- As part of regular security maintenance

## Local/Docker-Compose Rotation

### Prerequisites

- Access to the repository root directory
- Docker and Docker Compose installed
- Admin access to the current Grafana credentials (for verification)

### Rotation Steps

1. **Generate new credentials**

   Create strong credentials using a password manager or command-line tools:

   ```bash
   # Generate a new secure password (Linux/macOS)
   NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')
   echo "$NEW_PASSWORD"
   ```

   ```powershell
   # Generate a 24-character password using uppercase, lowercase, digits, and special characters (Windows PowerShell)
   # Character ranges: 65-90 (A-Z), 97-122 (a-z), 48-57 (0-9), special chars (!#$%&*+)
   $NEW_PASSWORD = -join ((65..90) + (97..122) + (48..57) + (33,35,36,37,38,42,43) | Get-Random -Count 24 | % {[char]$_})
   $NEW_PASSWORD
   ```

2. **Update the secret files**

   **Linux/macOS (bash):**
   ```bash
   # Update username (if needed)
   echo -n "admin" > secrets/grafana_admin_user

   # Update password
   echo -n "$NEW_PASSWORD" > secrets/grafana_admin_password

   # Or use your preferred method to edit the files
   ```

   **Windows (PowerShell):**
   ```powershell
   # Update username (if needed)
   "admin" | Out-File -FilePath secrets/grafana_admin_user -NoNewline

   # Update password
   $NEW_PASSWORD | Out-File -FilePath secrets/grafana_admin_password -NoNewline
   ```

3. **Restart Grafana and Gateway**

   Both services need to be restarted to pick up the new credentials:

   ```bash
   docker compose restart grafana gateway
   ```

   Wait for the services to become healthy:
   ```bash
   docker compose ps grafana gateway
   ```

4. **Verify the rotation** (See [Verification Steps](#verification-steps) below)

5. **Document the change**

   Record the credential rotation in your organization's security log or change management system.

### Important Notes

- **Both Grafana and Gateway must be restarted** to ensure the new credentials are loaded properly
- The Gateway service proxies requests to Grafana and may cache authentication credentials
- Existing Grafana sessions will remain valid until they expire or users log out
- After rotation, all users must log in with the new credentials

## Azure Container Apps Rotation

**Note**: As of the current implementation, Grafana is not yet deployed as a Container App in Azure. These instructions are prepared for when Grafana is added to the Azure deployment.

### Prerequisites

- Azure CLI installed and logged in (`az login`)
- Contributor or Owner role on the resource group
- Key Vault Secrets Officer role on the Key Vault

### Rotation Steps

1. **Identify the Key Vault**

   Find your Key Vault name from the deployment outputs:

   ```bash
   # List deployments and get the Key Vault name
   az deployment group show \
     --resource-group <resource-group-name> \
     --name <deployment-name> \
     --query properties.outputs.keyVaultName.value \
     -o tsv
   ```

   Or list Key Vaults in the resource group:
   ```bash
   az keyvault list --resource-group <resource-group-name> --query "[].name" -o tsv
   ```

2. **Update secrets in Key Vault**

   Set new values for the Grafana admin credentials:

   ```bash
   # Set the Key Vault name
   KV_NAME="<your-keyvault-name>"

   # Update admin username (if needed)
   az keyvault secret set \
     --vault-name "$KV_NAME" \
     --name grafana-admin-user \
     --value "admin"

   # Update admin password with a strong random password
   NEW_PASSWORD=$(openssl rand -base64 32 | tr -d '\n')
   az keyvault secret set \
     --vault-name "$KV_NAME" \
     --name grafana-admin-password \
     --value "$NEW_PASSWORD"

   # Save the password securely for verification
   echo "New Grafana admin password: $NEW_PASSWORD"
   ```

   **PowerShell (Windows):**
   ```powershell
   $KV_NAME = "<your-keyvault-name>"

   # Generate a 24-character password using uppercase, lowercase, digits, and special characters
   # Character ranges: 65-90 (A-Z), 97-122 (a-z), 48-57 (0-9), special chars (!#$%&*+)
   $NEW_PASSWORD = -join ((65..90) + (97..122) + (48..57) + (33,35,36,37,38,42,43) | Get-Random -Count 24 | % {[char]$_})
   az keyvault secret set --vault-name $KV_NAME --name grafana-admin-user --value "admin"
   az keyvault secret set --vault-name $KV_NAME --name grafana-admin-password --value $NEW_PASSWORD

   Write-Host "New Grafana admin password: $NEW_PASSWORD"
   ```

3. **Restart the Grafana Container App**

   The Container App needs to create a new revision to resolve the updated Key Vault secrets:

   ```bash
   # Get the Container App name
   GRAFANA_APP_NAME=$(az containerapp list \
     --resource-group <resource-group-name> \
     --query "[?contains(name, 'grafana')].name" -o tsv)

   # Restart the Container App to create a new revision
   az containerapp revision restart \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME"
   ```

   Alternatively, you can create a new revision:
   ```bash
   az containerapp update \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME"
   ```

4. **Verify the rotation** (See [Verification Steps](#verification-steps) below)

5. **Document the change**

   Record the credential rotation including:
   - Date and time of rotation
   - Key Vault secret versions used
   - Person who performed the rotation
   - Verification results

### Secret Version Management

Azure Key Vault maintains a version history of secrets. To use a specific version:

```bash
# List all versions of a secret
az keyvault secret list-versions \
  --vault-name "$KV_NAME" \
  --name grafana-admin-password \
  --query "[].{version:id,created:attributes.created}" -o table

# Reference a specific version in Container App (if needed for rollback)
az containerapp update \
  --resource-group <resource-group-name> \
  --name "$GRAFANA_APP_NAME" \
  --set-env-secrets grafana-admin-password=<secret-uri-with-version>
```

## Verification Steps

After rotating credentials, verify that the new credentials work correctly:

### 1. Test Login

**Local/Docker-Compose:**
```bash
# Open Grafana in browser
open http://localhost:8080/grafana/
# Or for Linux: xdg-open http://localhost:8080/grafana/
```

**Azure Container Apps:**
```bash
# Get the Gateway FQDN
GATEWAY_FQDN=$(az containerapp show \
  --resource-group <resource-group-name> \
  --name <gateway-app-name> \
  --query properties.configuration.ingress.fqdn -o tsv)

# Open in browser
echo "https://$GATEWAY_FQDN/grafana/"
```

Log in using the new admin credentials.

### 2. Verify Admin Access

Once logged in:
1. Click on the user icon in the bottom-left corner
2. Verify your role shows as "Admin"
3. Navigate to **Configuration** > **Users** to confirm admin privileges
4. Test accessing a dashboard to ensure functionality

### 3. Check Service Health

**Local/Docker-Compose:**
```bash
# Check service status
docker compose ps grafana gateway

# Check logs for errors
docker compose logs grafana --tail=50
```

**Azure Container Apps:**
```bash
# Check Container App status
az containerapp show \
  --resource-group <resource-group-name> \
  --name "$GRAFANA_APP_NAME" \
  --query "properties.runningStatus" -o tsv

# View recent logs
az containerapp logs show \
  --resource-group <resource-group-name> \
  --name "$GRAFANA_APP_NAME" \
  --tail 50
```

## Rollback Procedures

If issues occur after credential rotation, you can rollback to previous credentials.

### Local/Docker-Compose Rollback

1. **Restore previous credential files**

   If you have backups:
   ```bash
   # Restore from backup
   cp secrets/grafana_admin_user.backup secrets/grafana_admin_user
   cp secrets/grafana_admin_password.backup secrets/grafana_admin_password
   ```

2. **Restart services**
   ```bash
   docker compose restart grafana gateway
   ```

### Azure Container Apps Rollback

Azure Key Vault maintains version history, making rollback straightforward:

1. **List secret versions**

   ```bash
   # Get the previous version URI
   az keyvault secret list-versions \
     --vault-name "$KV_NAME" \
     --name grafana-admin-password \
     --query "[1].id" -o tsv
   ```

2. **Update Container App to use previous version**

   ```bash
   PREVIOUS_SECRET_URI="<previous-version-uri-from-step-1>"

   # Update to use specific secret version
   az containerapp update \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME" \
     --set-env-secrets "grafana-admin-password=secretref:$PREVIOUS_SECRET_URI"
   ```

3. **Restart Container App**
   ```bash
   az containerapp revision restart \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME"
   ```

## Troubleshooting

### Issue: Cannot log in with new credentials

**Symptoms**: Login fails with "Invalid username or password" error

**Solutions**:
1. Verify the secrets were updated correctly:
   ```bash
   # Local
   cat secrets/grafana_admin_user
   cat secrets/grafana_admin_password

   # Azure
   az keyvault secret show --vault-name "$KV_NAME" --name grafana-admin-user --query value -o tsv
   ```

2. Ensure services were restarted after credential update
3. Check for extra whitespace or newlines in secret files
4. Review logs for authentication errors

### Issue: Gateway returns 502 Bad Gateway

**Symptoms**: Cannot access Grafana through the gateway

**Solutions**:
1. Check that both Grafana and Gateway were restarted:
   ```bash
   docker compose ps grafana gateway
   ```

2. Verify Grafana is healthy:
   ```bash
   docker compose exec grafana wget -q -O- http://localhost:3000/api/health
   ```

3. Check Gateway logs for connection errors:
   ```bash
   docker compose logs gateway --tail=50
   ```

### Issue: Key Vault access denied (Azure)

**Symptoms**: Container App cannot retrieve secrets from Key Vault

**Solutions**:
1. Verify the Container App's managed identity has Key Vault access:
   ```bash
   # Check role assignments
   az role assignment list \
     --assignee <managed-identity-principal-id> \
     --scope /subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.KeyVault/vaults/<kv-name>
   ```

2. Ensure the identity has "Key Vault Secrets User" role
3. Check Key Vault network access rules if using Private Link

### Issue: Secrets not updating in Container App

**Symptoms**: New credentials don't take effect after Key Vault update

**Solutions**:
1. Container Apps cache Key Vault secret values. Create a new revision:
   ```bash
   az containerapp update \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME"
   ```

2. Verify the secret URI is using the latest version (or don't specify a version to always use latest):
   ```bash
   # Should end in /secrets/<secret-name> not /secrets/<secret-name>/<version>
   az containerapp show \
     --resource-group <resource-group-name> \
     --name "$GRAFANA_APP_NAME" \
     --query "properties.template.containers[0].env[?name=='GF_SECURITY_ADMIN_PASSWORD'].value"
   ```

## Additional Resources

- [Grafana Configuration Documentation](https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/)
- [Azure Key Vault Documentation](https://learn.microsoft.com/en-us/azure/key-vault/)
- [Azure Container Apps Secrets Management](https://learn.microsoft.com/en-us/azure/container-apps/manage-secrets)
- [Project Documentation](../../README.md)
