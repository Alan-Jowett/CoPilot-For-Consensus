<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Microsoft Entra App Registration Automation

## Overview

This guide explains how to use the automated Microsoft Entra (Azure AD) app registration provisioning for OAuth authentication in Copilot for Consensus. The Bicep template can automatically create and configure an Entra app registration with the correct redirect URIs, client secrets, and API permissions.

## Table of Contents

- [Prerequisites](#prerequisites)
- [How It Works](#how-it-works)
- [Deployment](#deployment)
- [Configuration](#configuration)
- [Secret Rotation](#secret-rotation)
- [Troubleshooting](#troubleshooting)
- [Manual Setup (Alternative)](#manual-setup-alternative)

## Prerequisites

### 1. Microsoft Graph API Permissions

The deployment identity (user or service principal) must have the following **Microsoft Graph application permissions** (not delegated):

- `Application.ReadWrite.All` - Required to create and update app registrations
- `Directory.ReadWrite.All` - Required to create service principals

These permissions must be granted by a **Global Administrator** or **Privileged Role Administrator**.

### 2. Grant Permissions to Deployment Identity

#### Option A: User Identity (Interactive Deployment)

If deploying manually with your user account:

1. Your user must be assigned one of these roles:
   - **Global Administrator** (not recommended for production)
   - **Application Administrator** (recommended)
   - **Cloud Application Administrator** (recommended)

2. For users without admin roles, the deployment will require a dedicated managed identity with Graph API permissions (see Option B below).

#### Option B: Service Principal (CI/CD Deployment)

For GitHub Actions or automated deployments using a service principal:

1. Create a service principal for deployment (if you don't have one):

```bash
# Create service principal
az ad sp create-for-rbac \
  --name "copilot-deployment-sp" \
  --role Contributor \
  --scopes /subscriptions/<subscription-id>/resourceGroups/<resource-group>
```

2. Grant Graph API permissions to the service principal:

```bash
# Get the service principal object ID
SP_OBJECT_ID=$(az ad sp list --display-name "copilot-deployment-sp" --query "[0].id" -o tsv)

# Get the Microsoft Graph app ID
GRAPH_APP_ID="00000003-0000-0000-c000-000000000000"

# Get the role IDs
APP_ROLE_ID="1bfefb4e-e0b5-418b-a88f-73c46d2cc8e9"  # Application.ReadWrite.All
DIR_ROLE_ID="19dbc75e-c2e2-444c-a770-ec69d8559fc7"   # Directory.ReadWrite.All

# Get Microsoft Graph service principal resource ID
GRAPH_SP_RESOURCE_ID=$(az ad sp list --filter "appId eq '$GRAPH_APP_ID'" --query "[0].id" -o tsv)

# Grant Application.ReadWrite.All
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_OBJECT_ID/appRoleAssignments" \
  --headers "Content-Type=application/json" \
  --body "{
    \"principalId\": \"$SP_OBJECT_ID\",
    \"resourceId\": \"$GRAPH_SP_RESOURCE_ID\",
    \"appRoleId\": \"$APP_ROLE_ID\"
  }"

# Grant Directory.ReadWrite.All
az rest --method POST \
  --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$SP_OBJECT_ID/appRoleAssignments" \
  --headers "Content-Type=application/json" \
  --body "{
    \"principalId\": \"$SP_OBJECT_ID\",
    \"resourceId\": \"$GRAPH_SP_RESOURCE_ID\",
    \"appRoleId\": \"$DIR_ROLE_ID\"
  }"
```

### 3. Azure Subscription Access

The deployment identity must also have:
- **Contributor** role on the target resource group (to create Azure resources)
- **User Access Administrator** or **Owner** role (to assign RBAC permissions to managed identities)

## How It Works

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Bicep Deployment (main.bicep)                          │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 1. Deploy Container Apps (including Gateway)      │  │
│  │    - Gateway gets auto-generated FQDN             │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 2. Calculate Redirect URIs                        │  │
│  │    - User-provided OR                             │  │
│  │    - Must be provided via oauthRedirectUris       │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 3. Create Entra App (entra-app.bicep)            │  │
│  │    - Deployment Script calls az ad app commands   │  │
│  │    - Creates app registration                     │  │
│  │    - Sets redirect URIs                           │  │
│  │    - Generates client secret                      │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 4. Store Secrets in Key Vault                     │  │
│  │    - microsoft-oauth-client-id                    │  │
│  │    - microsoft-oauth-client-secret                │  │
│  └───────────────────────────────────────────────────┘  │
│                        ↓                                 │
│  ┌───────────────────────────────────────────────────┐  │
│  │ 5. Auth Service Loads Secrets                     │  │
│  │    - Uses managed identity + Key Vault            │  │
│  │    - Configures Microsoft OAuth provider          │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Deployment Script

The Entra app is created using an Azure **deploymentScript** resource that executes Azure CLI commands:

1. Checks if app with the same display name already exists
2. Creates new app or updates existing app with redirect URIs
3. Creates service principal (if not exists)
4. Generates a client secret with configurable expiration
5. Outputs app details (client ID, tenant ID, secret) for storage in Key Vault

## Deployment

### Step 1: Obtain Gateway FQDN (First Deployment)

For the first deployment, you need to deploy without Entra app automation to get the gateway FQDN:

```bash
# Deploy with Entra app disabled
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters deployEntraApp=false
  
# Get the gateway FQDN from outputs
GATEWAY_FQDN=$(az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs.gatewayFqdn.value -o tsv)

echo "Gateway FQDN: https://$GATEWAY_FQDN"
```

### Step 2: Deploy with Entra App (Subsequent Deployment)

Now deploy again with the redirect URI:

```bash
# Deploy with Entra app enabled and redirect URI
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters deployEntraApp=true \
  --parameters oauthRedirectUris="[\"https://$GATEWAY_FQDN/auth/callback\"]"
```

### Step 3: Verify Deployment

Check the outputs:

```bash
az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs
```

Expected outputs:
- `entraAppClientId` - The application (client) ID
- `entraAppTenantId` - The tenant ID
- `oauthRedirectUris` - Configured redirect URIs

### Step 4: Test OAuth Login

Access the auth service and initiate login:

```bash
# Get gateway FQDN
GATEWAY_FQDN=$(az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs.gatewayFqdn.value -o tsv)

# Open login page
echo "Login URL: https://$GATEWAY_FQDN/auth/login?provider=microsoft"
```

## Configuration

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `deployEntraApp` | bool | `true` | Enable/disable automatic Entra app creation |
| `entraTenantId` | string | `subscription().tenantId` | Microsoft Entra tenant ID |
| `oauthRedirectUris` | array | `[]` | Override redirect URIs (required for first deployment) |
| `oauthSecretExpirationDays` | int | `365` | Client secret expiration in days (30-730) |

### Environment-Specific Configuration

#### Development (`parameters.dev.json`)

```json
{
  "deployEntraApp": { "value": true },
  "oauthRedirectUris": { "value": ["https://your-dev-gateway.azurecontainerapps.io/auth/callback"] },
  "oauthSecretExpirationDays": { "value": 180 }
}
```

#### Production (`parameters.prod.json`)

```json
{
  "deployEntraApp": { "value": true },
  "oauthRedirectUris": { "value": [
    "https://your-prod-gateway.azurecontainerapps.io/auth/callback",
    "https://custom-domain.example.com/auth/callback"
  ]},
  "oauthSecretExpirationDays": { "value": 365 }
}
```

### Multiple Redirect URIs

You can configure multiple redirect URIs for different environments or custom domains:

```json
{
  "oauthRedirectUris": {
    "value": [
      "https://prod-gateway.azurecontainerapps.io/auth/callback",
      "https://auth.example.com/auth/callback",
      "http://localhost:8090/callback"  // For local development
    ]
  }
}
```

## Secret Rotation

### Automatic Rotation

Client secrets are automatically rotated during redeployment:

```bash
# Redeploy with new secret expiration
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters oauthSecretExpirationDays=365
```

The deployment script will:
1. Call `az ad app credential reset` to generate a new secret
2. Update the Key Vault secret with the new value
3. Auth service will automatically pick up the new secret on next restart

### Manual Secret Rotation

If you need to rotate the secret outside of deployment:

```bash
# Generate new secret
NEW_SECRET=$(az ad app credential reset \
  --id <app-id> \
  --display-name "Manual Rotation $(date +%Y-%m-%d)" \
  --query password -o tsv)

# Update Key Vault
KEY_VAULT_NAME=$(az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs.keyVaultName.value -o tsv)

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name microsoft-oauth-client-secret \
  --value "$NEW_SECRET"

# Restart auth service
az containerapp restart \
  --name copilot-auth-dev \
  --resource-group copilot-dev-rg
```

### Secret Expiration Monitoring

Set up Azure Monitor alerts for secret expiration:

```bash
# Create alert rule
az monitor metrics alert create \
  --name "Entra App Secret Expiring" \
  --resource-group copilot-dev-rg \
  --scopes /subscriptions/<subscription-id> \
  --condition "total passwordCredentials.endDateTime < 30" \
  --description "Alert when Entra app secret expires in less than 30 days"
```

## Troubleshooting

### Issue: Deployment fails with "Insufficient privileges"

**Error:**
```
Insufficient privileges to complete the operation.
```

**Solution:**
- Verify the deployment identity has `Application.ReadWrite.All` and `Directory.ReadWrite.All` Graph API permissions
- Ensure admin consent has been granted for these permissions
- Check that the identity has the necessary Azure AD roles (Application Administrator or Cloud Application Administrator)

### Issue: App already exists with same name

**Error:**
```
Another object with the same value for property displayName already exists.
```

**Solution:**
- The deployment script automatically updates existing apps with matching names
- If you want a separate app, change the `projectName` or `environment` parameter
- To manually delete the existing app:

```bash
az ad app delete --id <app-id>
```

### Issue: Redirect URI mismatch

**Error in auth service logs:**
```
The reply URL specified in the request does not match the reply URLs configured for the application.
```

**Solution:**
- Verify the `oauthRedirectUris` parameter matches the actual gateway FQDN
- Check deployment outputs to confirm configured redirect URIs:

```bash
az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs.oauthRedirectUris.value
```

- Update redirect URIs via redeployment or manually:

```bash
az ad app update \
  --id <app-id> \
  --web-redirect-uris "https://new-url.com/auth/callback"
```

### Issue: Secret not found in Key Vault

**Error:**
```
SecretNotFound: Secret microsoft-oauth-client-secret not found
```

**Solution:**
- Verify the Entra app module deployed successfully
- Check Key Vault for the secret:

```bash
az keyvault secret list \
  --vault-name <key-vault-name> \
  --query "[?name contains(@, 'microsoft-oauth')].name"
```

- Ensure the auth service managed identity has Key Vault Secrets User role
- Manually create the secret if needed (see [Manual Secret Rotation](#manual-secret-rotation))

### Issue: Deployment script times out

**Error:**
```
DeploymentScriptTimeout: The deployment script exceeded the maximum execution time.
```

**Solution:**
- This usually indicates network connectivity issues or Graph API throttling
- Check the deployment script logs:

```bash
az deployment-scripts show-log \
  --resource-group copilot-dev-rg \
  --name create-entra-app-dev
```

- Retry the deployment
- If persistent, consider using manual setup (see below)

## Manual Setup (Alternative)

If you prefer manual setup or encounter issues with automation:

### 1. Create App Registration

```bash
# Create app
APP_ID=$(az ad app create \
  --display-name "copilot-auth-dev" \
  --sign-in-audience AzureADMyOrg \
  --web-redirect-uris "https://<gateway-fqdn>/auth/callback" \
  --enable-id-token-issuance true \
  --query appId -o tsv)

echo "App ID: $APP_ID"
```

### 2. Create Service Principal

```bash
az ad sp create --id $APP_ID
```

### 3. Generate Client Secret

```bash
CLIENT_SECRET=$(az ad app credential reset \
  --id $APP_ID \
  --display-name "Primary Secret" \
  --query password -o tsv)

echo "Client Secret: $CLIENT_SECRET"
```

### 4. Store in Key Vault

```bash
KEY_VAULT_NAME=<your-key-vault>

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name microsoft-oauth-client-id \
  --value "$APP_ID"

az keyvault secret set \
  --vault-name $KEY_VAULT_NAME \
  --name microsoft-oauth-client-secret \
  --value "$CLIENT_SECRET"
```

### 5. Update Deployment Parameters

Disable Entra app automation in parameter file:

```json
{
  "deployEntraApp": { "value": false }
}
```

## Security Best Practices

1. **Least Privilege**: Grant only required Graph API permissions
2. **Secret Expiration**: Use short expiration periods for dev (180 days), longer for prod (365 days)
3. **Secret Rotation**: Rotate secrets before expiration
4. **Monitoring**: Set up alerts for secret expiration and deployment failures
5. **Audit Logs**: Enable Azure AD audit logging for app registration changes
6. **Conditional Access**: Consider enabling conditional access policies for the auth app
7. **Multi-Factor Authentication**: Require MFA for users authenticating via the app

## Additional Resources

- [Microsoft Entra ID Documentation](https://learn.microsoft.com/en-us/entra/identity-platform/)
- [Azure CLI App Registration Commands](https://learn.microsoft.com/en-us/cli/azure/ad/app)
- [Microsoft Graph API Permissions](https://learn.microsoft.com/en-us/graph/permissions-reference)
- [Copilot for Consensus Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Copilot for Consensus Security Considerations](SECURITY_CONSIDERATIONS.md)

---

**License**: MIT  
**Copyright**: © 2025 Copilot-for-Consensus contributors
