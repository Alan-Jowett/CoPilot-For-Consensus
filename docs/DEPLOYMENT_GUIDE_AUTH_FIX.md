# Deployment Guide: Auth Service Managed Identity Fix

## Overview
This document provides step-by-step instructions for deploying the fix for the auth service managed identity authentication issue.

## Prerequisites
- Azure CLI installed and authenticated
- Access to the Azure subscription `4d9deeb6-93a1-4e1c-a09c-2908cb82fd69`
- Contributor or Owner role on the resource group `copilot-dev-1197027393`

## What This Fix Does
This fix adds the `AZURE_CLIENT_ID` environment variable to the auth service Container App, enabling the Azure SDK's `DefaultAzureCredential` to properly detect and use the user-assigned managed identity for accessing Azure Key Vault.

## Deployment Steps

### Step 1: Verify Current State
Before deploying, check the current auth service status:

```bash
# Check if auth service is running
az containerapp show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --query "properties.runningStatus"

# Check current environment variables
az containerapp show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --query "properties.template.containers[0].env" \
  --output table
```

### Step 2: Deploy the Updated Infrastructure

```bash
# Navigate to the infrastructure directory
cd infra/azure

# Deploy the updated Bicep templates
az deployment group create \
  --resource-group copilot-dev-1197027393 \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --verbose

# Note: Deployment may take 15-30 minutes due to RBAC propagation delays
# The JWT key generation script includes retry logic to handle this
```

### Step 3: Verify Deployment Success

```bash
# Check deployment status
az deployment group show \
  --resource-group copilot-dev-1197027393 \
  --name <deployment-name> \
  --query "properties.provisioningState"

# Verify AZURE_CLIENT_ID is now set
az containerapp show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --query "properties.template.containers[0].env[?name=='AZURE_CLIENT_ID']"
```

### Step 4: Monitor Auth Service Logs

```bash
# Stream logs from the auth service
az containerapp logs show \
  --name copilot-auth-dev \
  --resource-group copilot-dev-1197027393 \
  --follow

# Look for these success indicators:
# ✓ "Initialized Azure Key Vault provider for https://..."
# ✓ "JWT private key loaded and written to temp file"
# ✓ "JWT public key loaded and written to temp file"
# ✓ "Auth Service initialized with 0 providers"
```

### Step 5: Test Auth Service Health

```bash
# Get the gateway FQDN
GATEWAY_FQDN=$(az containerapp show \
  --name copilot-gateway-dev \
  --resource-group copilot-dev-1197027393 \
  --query "properties.configuration.ingress.fqdn" \
  --output tsv)

# Test auth service health endpoint (via gateway)
curl https://${GATEWAY_FQDN}/auth/health

# Expected response:
# {
#   "status": "healthy",
#   "service": "auth",
#   "version": "0.1.0",
#   ...
# }

# Test readiness endpoint
curl https://${GATEWAY_FQDN}/auth/readyz

# Expected response:
# {
#   "status": "ready"
# }
```

## Troubleshooting

### Issue: Deployment Script Timeout
**Symptom**: JWT key generation script times out after 15 minutes

**Solution**:
1. Check if RBAC permissions were assigned to the JWT keys identity:
   ```bash
   KEYVAULT_NAME=$(az keyvault list \
     --resource-group copilot-dev-1197027393 \
     --query "[0].name" -o tsv)
   
   JWT_IDENTITY_PRINCIPAL=$(az identity show \
     --name copilot-dev-jwtkeys-id \
     --resource-group copilot-dev-1197027393 \
     --query "principalId" -o tsv)
   
   az role assignment list \
     --scope /subscriptions/4d9deeb6-93a1-4e1c-a09c-2908cb82fd69/resourceGroups/copilot-dev-1197027393/providers/Microsoft.KeyVault/vaults/${KEYVAULT_NAME} \
     --assignee ${JWT_IDENTITY_PRINCIPAL}
   ```

2. Wait 5-10 minutes and retry the deployment

### Issue: Auth Service Still Failing After Deployment
**Symptom**: Auth service shows same error after deployment

**Solution**:
1. Verify AZURE_CLIENT_ID is set correctly:
   ```bash
   # Get the expected client ID
   EXPECTED_CLIENT_ID=$(az identity show \
     --name copilot-dev-auth-id \
     --resource-group copilot-dev-1197027393 \
     --query "clientId" -o tsv)
   
   # Get the actual client ID from container app
   ACTUAL_CLIENT_ID=$(az containerapp show \
     --name copilot-auth-dev \
     --resource-group copilot-dev-1197027393 \
     --query "properties.template.containers[0].env[?name=='AZURE_CLIENT_ID'].value" -o tsv)
   
   # Compare
   echo "Expected: ${EXPECTED_CLIENT_ID}"
   echo "Actual:   ${ACTUAL_CLIENT_ID}"
   ```

2. If they don't match or ACTUAL_CLIENT_ID is empty, restart the container app:
   ```bash
   az containerapp restart \
     --name copilot-auth-dev \
     --resource-group copilot-dev-1197027393
   ```

### Issue: JWT Keys Not Found in Key Vault
**Symptom**: Auth service reports "JWT keys not found in secrets store"

**Solution**:
1. Verify JWT keys exist in Key Vault:
   ```bash
   KEYVAULT_NAME=$(az keyvault list \
     --resource-group copilot-dev-1197027393 \
     --query "[0].name" -o tsv)
   
   az keyvault secret list \
     --vault-name ${KEYVAULT_NAME} \
     --query "[?name=='jwt-private-key' || name=='jwt-public-key'].{Name:name, Enabled:attributes.enabled}"
   ```

2. If keys don't exist, check deployment script logs:
   ```bash
   az deployment-scripts show \
     --resource-group copilot-dev-1197027393 \
     --name generate-jwt-keys \
     --query "properties.outputs"
   ```

### Issue: 403 Forbidden Errors in Logs
**Symptom**: Auth service logs show "403 Forbidden" when accessing Key Vault

**Solution**:
1. Verify the auth identity has Key Vault access:
   ```bash
   # For RBAC-enabled Key Vault
   az role assignment list \
     --scope /subscriptions/4d9deeb6-93a1-4e1c-a09c-2908cb82fd69/resourceGroups/copilot-dev-1197027393/providers/Microsoft.KeyVault/vaults/${KEYVAULT_NAME} \
     --assignee $(az identity show --name copilot-dev-auth-id --resource-group copilot-dev-1197027393 --query "principalId" -o tsv)
   ```

2. Grant access if missing:
   ```bash
   # Get auth identity principal ID
   AUTH_PRINCIPAL_ID=$(az identity show \
     --name copilot-dev-auth-id \
     --resource-group copilot-dev-1197027393 \
     --query "principalId" -o tsv)
   
   # Grant Key Vault Secrets User role
   az role assignment create \
     --role "Key Vault Secrets User" \
     --assignee ${AUTH_PRINCIPAL_ID} \
     --scope /subscriptions/4d9deeb6-93a1-4e1c-a09c-2908cb82fd69/resourceGroups/copilot-dev-1197027393/providers/Microsoft.KeyVault/vaults/${KEYVAULT_NAME}
   
   # Wait 5 minutes for propagation, then restart auth service
   sleep 300
   az containerapp restart --name copilot-auth-dev --resource-group copilot-dev-1197027393
   ```

## Rollback Procedure

If the deployment causes issues, you can rollback to the previous deployment:

```bash
# List recent deployments
az deployment group list \
  --resource-group copilot-dev-1197027393 \
  --query "[].{Name:name, State:properties.provisioningState, Timestamp:properties.timestamp}" \
  --output table

# Redeploy a previous successful deployment
az deployment group create \
  --resource-group copilot-dev-1197027393 \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --mode Incremental
```

**Note**: Rollback will remove the `AZURE_CLIENT_ID` environment variable, and the auth service will return to its previous failing state.

## Post-Deployment Verification Checklist

- [ ] Deployment completed successfully
- [ ] Auth service is in "Running" status
- [ ] AZURE_CLIENT_ID environment variable is set
- [ ] Auth service logs show successful JWT key loading
- [ ] Health endpoint returns "healthy" status
- [ ] Readiness endpoint returns "ready" status
- [ ] No error messages in auth service logs
- [ ] Other services (gateway, reporting, etc.) are still healthy

## Additional Resources

- [Azure Managed Identity Troubleshooting Guide](./AZURE_MANAGED_IDENTITY_TROUBLESHOOTING.md)
- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [DefaultAzureCredential Documentation](https://learn.microsoft.com/en-us/dotnet/api/azure.identity.defaultazurecredential)

## Support

If you encounter issues not covered in this guide:
1. Check the [Azure Managed Identity Troubleshooting Guide](./AZURE_MANAGED_IDENTITY_TROUBLESHOOTING.md)
2. Review Container Apps logs for error details
3. Contact the platform team with:
   - Deployment timestamp
   - Error messages from logs
   - Output of verification commands
