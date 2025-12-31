<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Deployment Guide for Copilot for Consensus

This guide provides instructions for deploying Copilot for Consensus to Azure using Azure Resource Manager (ARM) templates with managed identity support.

## Table of Contents

- [Overview](#overview)
- [CI/CD Validation](#cicd-validation)
- [Prerequisites](#prerequisites)
- [Architecture](#architecture)
- [Deployment Modes](#deployment-modes)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Deployment Steps](#deployment-steps)
- [Post-Deployment Configuration](#post-deployment-configuration)
- [Monitoring and Observability](#monitoring-and-observability)
- [Troubleshooting](#troubleshooting)
- [Cost Estimation](#cost-estimation)
- [Security Best Practices](#security-best-practices)

## CI/CD Validation

All pull requests that modify files in `infra/azure/` are automatically validated by GitHub Actions.

### Validation Stages

1. **Bicep Lint & Build** (always runs)
  - Compiles `.bicep` templates to ARM JSON
  - Runs linter for best-practice checks
  - Fast feedback, no Azure access required

2. **ARM Template Validation** (requires Azure secrets)
  - Validates generated ARM templates against Azure
  - Runs what-if analysis to preview resource changes
  - Uses GitHub OIDC (see [GITHUB_OIDC_SETUP.md](GITHUB_OIDC_SETUP.md)) and targets a pre-created validation resource group (`copilot-bicep-validation-rg`)

#### Validation Resource Group (one-time)

Create the long-lived validation resource group once per subscription before relying on CI:

```bash
az group create --name copilot-bicep-validation-rg --location westus
```

The GitHub Actions workflow will fail fast with guidance if this group is missing. No teardown step runs in CI because the group is reused across runs.

### One-Time Setup: GitHub OIDC

To enable full validation with Azure integration:

```bash
cd infra/azure
chmod +x setup-github-oidc.sh
./setup-github-oidc.sh
```

Then add the resulting secrets to GitHub repository settings. See [GITHUB_OIDC_SETUP.md](GITHUB_OIDC_SETUP.md) for details.

### Validation Results

- ✅ Validation results are posted as comments on pull requests
- ⚠️ Failed validations **can** block PR merge (requires branch protection configuration)
- ✅ All validation is auditable in GitHub Actions tab

### Configuring Branch Protection (Recommended)

To automatically block PR merges when validation fails, configure branch protection rules:

1. Go to **Settings > Branches > Branch protection rules**
2. Click **Add rule**
3. Branch name pattern: `main`
4. Enable:
   - ✅ **Require a pull request before merging**
   - ✅ **Require status checks to pass before merging**
   - ✅ **Require branches to be up to date before merging**
5. Select required status checks:
   - `bicep-lint` (Bicep Lint & Build)
   - `validate-template` (ARM Template Validation)
   - `comment-results` (PR comment posting)
6. Click **Create** or **Save changes**

**Result**: Pull requests to `main` will require all Bicep validation checks to pass before merge is allowed.

**Note**: Branch protection requires the validation workflow to have completed successfully. If you haven't configured GitHub OIDC yet (see [One-Time Setup: GitHub OIDC](#one-time-setup-github-oidc)), the ARM validation step will be skipped, so you may want to only require the `bicep-lint` job initially.

## Building ARM Templates from Bicep

This repository uses **Bicep** (not raw ARM JSON) as the infrastructure-as-code language. Bicep is more readable and maintainable than ARM JSON.

### Generated Files

- **`main.json`** is automatically generated from `main.bicep`
- Do NOT edit `main.json` directly — always edit the `.bicep` files
- Generated files are excluded from version control (see `.gitignore`)

### Build Locally

To regenerate ARM templates from Bicep source:

```bash
# Build main template
az bicep build --file infra/azure/main.bicep

# Build individual modules
az bicep build --file infra/azure/modules/identities.bicep
az bicep build --file infra/azure/modules/keyvault.bicep
```

The generated `.json` files will be written to the same directory as the `.bicep` files.

### CI/CD Integration

The GitHub Actions workflow (`.github/workflows/bicep-validate.yml`) automatically:
1. Compiles Bicep to ARM templates
2. Validates ARM syntax
3. Runs linter checks
4. Performs what-if analysis

You don't need to manually commit generated files — they're built on-demand.



The Bicep template (`main.bicep`) automates the deployment of the entire Copilot for Consensus architecture to Azure, including:

- **Azure Container Apps** for all microservices (ingestion, parsing, chunking, embedding, orchestrator, summarization, reporting, auth, UI, gateway)
- **User-Assigned Managed Identities** for each service with least-privilege access
- **Azure Key Vault** for secrets management
- **Azure Storage Account** for blob storage
- **Application Insights** for monitoring and diagnostics
- **Log Analytics Workspace** for centralized logging
- **Virtual Network** with subnet for Container Apps
- **Role-Based Access Control (RBAC)** assignments for secure resource access

## Prerequisites

### Required Tools

- **Azure CLI** (version 2.50.0 or later) with Bicep support (`az bicep install`)
  - Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
- **Azure PowerShell** (Az module, version 10.0.0 or later) - for PowerShell deployment
  - Install: `Install-Module -Name Az -AllowClobber -Scope CurrentUser`
- **Bash** (for Linux/macOS/WSL) or **PowerShell** (for Windows)

### Azure Resources

- **Active Azure Subscription** with permissions to:
  - Create resource groups
  - Deploy resources (Contributor role or higher)
  - Assign RBAC roles (User Access Administrator or Owner)
- **Azure Cosmos DB for SQL API** (provisioned by this template) or external MongoDB connection string if you override defaults
- **Azure Service Bus** namespace (Standard or Premium tier)
- **Azure OpenAI** service (if using `llmBackend: azure`)
- **Container images** published to a GitHub Container Registry (GHCR) that your deployment can pull from. You can either:
  - Use the existing images published by the repository owner at `ghcr.io/alan-jowett/copilot-for-consensus` (this is the default used by the ARM template).
  - Publish your own images to your GHCR namespace using the [`publish-docker-images.yml`](../../.github/workflows/publish-docker-images.yml) workflow and set the `containerRegistryName` ARM template parameter to your registry.
  - Allow your CI to publish images automatically by running the Docker Compose CI workflow ([`docker-compose-ci.yml`](../../.github/workflows/docker-compose-ci.yml)) to successful completion on the branch or tag you are deploying.

### Network Requirements

- Outbound internet access for pulling container images from GHCR
- Access to Azure services (Key Vault, Storage, Service Bus, etc.)

## Architecture

The deployment creates the following Azure resources:

```
┌─────────────────────────────────────────────────────────────┐
│                     Azure Resource Group                     │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │         Container Apps Environment (VNet)               │ │
│  ├────────────────────────────────────────────────────────┤ │
│  │  Container Apps:                                        │ │
│  │  - ingestion (w/ managed identity)                     │ │
│  │  - parsing (w/ managed identity)                       │ │
│  │  - chunking (w/ managed identity)                      │ │
│  │  - embedding (w/ managed identity)                     │ │
│  │  - orchestrator (w/ managed identity)                  │ │
│  │  - summarization (w/ managed identity)                 │ │
│  │  - reporting (w/ managed identity)                     │ │
│  │  - auth (w/ managed identity)                          │ │
│  │  - ui (w/ managed identity)                            │ │
│  │  - gateway (w/ managed identity)                       │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│  │  Key Vault     │  │  Storage     │  │  App Insights   │ │
│  │  (secrets)     │  │  (blobs)     │  │  (monitoring)   │ │
│  └────────────────┘  └──────────────┘  └─────────────────┘ │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐│
│  │         Log Analytics Workspace (logs)                  ││
│  └─────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  Cosmos DB/MongoDB   Azure Service Bus    Azure OpenAI
  (external)          (external)           (external)
```

Each Container App has its own user-assigned managed identity with RBAC permissions to access only the resources it needs:
- **Key Vault**: Secrets User role (read secrets)
- **Storage Account**: Blob Data Contributor role (read/write blobs)
- **Service Bus**: Data Sender/Receiver roles (send/receive messages)
- **Azure OpenAI**: Cognitive Services User role (use OpenAI endpoints)

## Deployment Modes

The template supports two deployment modes:

### 1. Admin Mode (Default)

- Deployment initiated manually by an administrator via Azure CLI or Portal
- Requires admin credentials and permissions
- Best for initial setup and testing

### 2. Managed Identity Mode

- Deployment initiated by a CI/CD pipeline or automation service using a managed identity
- The identity must have sufficient permissions to:
  - Create resources (Contributor role)
  - Assign RBAC roles (User Access Administrator or Owner role)
- Best for automated deployments and GitOps workflows

Set the `deploymentMode` parameter to `admin` or `managedIdentity` accordingly.

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Alan-Jowett/CoPilot-For-Consensus.git
cd CoPilot-For-Consensus/infra/azure
```

### 2. Configure Parameters

Edit the environment parameter file (e.g., `parameters.dev.json`) to set your configuration:

```json
{
  "projectName": { "value": "copilot" },
  "environment": { "value": "dev" },
  "mongoDbConnectionString": { "value": "YOUR_MONGODB_CONNECTION_STRING" },
  "serviceBusConnectionString": { "value": "YOUR_SERVICEBUS_CONNECTION_STRING" },
  "storageAccountConnectionString": { "value": "YOUR_STORAGE_CONNECTION_STRING" },
  "azureOpenAIEndpoint": { "value": "YOUR_AZURE_OPENAI_ENDPOINT" },
  "azureOpenAIKey": { "value": "YOUR_AZURE_OPENAI_KEY" }
}
```

**Security Note**: For production, use Azure Key Vault references instead of plain text secrets:

```json
{
  "mongoDbConnectionString": {
    "reference": {
      "keyVault": {
        "id": "/subscriptions/.../resourceGroups/.../providers/Microsoft.KeyVault/vaults/my-keyvault"
      },
      "secretName": "mongodb-connection-string"
    }
  }
}
```

### 3. Deploy Using Bash Script (Linux/macOS/WSL)

```bash
# Login to Azure
az login

# Deploy
./deploy.sh -g copilot-rg -l eastus -e dev -t latest
```

### 4. Deploy Using PowerShell (Windows)

```powershell
# Login to Azure
Connect-AzAccount

# Deploy
.\deploy.ps1 -ResourceGroup "copilot-rg" -Location "eastus" -Environment "dev" -ImageTag "latest"
```

### 5. Deploy Using Azure CLI Directly

```bash
# Login to Azure
az login

# Create resource group
az group create --name copilot-rg --location eastus

# Validate template
az deployment group validate \
  --resource-group copilot-rg \
  --template-file main.bicep \
  --parameters @parameters.dev.json

# Deploy
az deployment group create \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --template-file main.bicep \
  --parameters @parameters.dev.json
```

## Configuration

### Environment Parameter Files

The repository includes pre-configured parameter files for each environment:

- **`parameters.dev.json`** - Development environment (low cost)
  - Uses minimal SKUs (Standard Service Bus, 1000-2000 RU Cosmos autoscale)
  - Single-region deployment
  - Public network access enabled (for quick testing)

- **`parameters.staging.json`** - Staging/pre-production environment (balanced)
  - Medium SKUs (Standard Service Bus, 1000-2000 RU Cosmos autoscale)
  - Single-region deployment
  - For pre-release testing

- **`parameters.prod.json`** - Production environment (high availability)
  - Premium SKUs (Premium Service Bus, higher Cosmos RU limits)
  - Multi-region deployment (optional, via `enableMultiRegionCosmos`)
  - Public network access disabled (requires Private Link)

**Alignment:** Environment names (`dev`, `staging`, `prod`) align with existing deployment conventions across Bicep and documentation.

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `mongoDbConnectionString` | securestring | MongoDB or Cosmos DB connection string |
| `storageAccountConnectionString` | securestring | Azure Storage connection string |

### Optional Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `projectName` | string | `copilot` | Prefix for resource names (3-15 chars) |
| `environment` | string | `dev` | Environment: dev, staging, or prod |
| `location` | string | Resource group location | Azure region for resources |
| `deploymentMode` | string | `admin` | Deployment mode: admin or managedIdentity |
| `containerRegistryName` | string | `ghcr.io/alan-jowett/copilot-for-consensus` | Container registry URL |
| `containerImageTag` | string | `latest` | Container image tag |
| `createNewIdentities` | bool | `true` | Create new managed identities or use existing |
| `existingIdentityResourceIds` | object | `{}` | Existing identity resource IDs (if createNewIdentities is false) |
| `llmBackend` | string | `azure` | LLM backend: local, azure, or mock |
| `azureOpenAIEndpoint` | string | `` | Azure OpenAI endpoint URL (required if llmBackend is azure) |
| `azureOpenAIKey` | securestring | `` | Azure OpenAI API key (required if llmBackend is azure) |
| `deployContainerApps` | bool | `true` | Deploy Container Apps environment and all microservices |
| `vnetAddressSpace` | string | `10.0.0.0/16` | VNet address space for Container Apps (CIDR notation) |
| `subnetAddressPrefix` | string | `10.0.0.0/23` | Container Apps subnet address prefix (CIDR notation) |

#### VNet Configuration

When deploying Container Apps (`deployContainerApps: true`), the template creates a Virtual Network with the following configurable parameters:

- **`vnetAddressSpace`**: The address space for the entire VNet (default: `10.0.0.0/16`, providing 65,536 IP addresses)
- **`subnetAddressPrefix`**: The address prefix for the Container Apps subnet (default: `10.0.0.0/23`, providing 512 IP addresses)

**Non-Overlapping Address Spaces by Environment:**
- **Dev**: `10.0.0.0/16` (subnet: `10.0.0.0/23`)
- **Staging**: `10.1.0.0/16` (subnet: `10.1.0.0/23`)
- **Prod**: `10.2.0.0/16` (subnet: `10.2.0.0/23`)

This design enables future VNet peering or hybrid connectivity scenarios without address conflicts. If your environments are fully isolated (separate subscriptions), you can use the same address space across all environments.

> **Note**: Service Bus and Cosmos DB access now rely on managed identities; connection strings are no longer passed into the Container Apps module. The Container Apps environment logs are sent to Log Analytics using the workspace shared key (platform requirement).

### Using Existing Managed Identities

If you have pre-created managed identities, set `createNewIdentities` to `false` and provide their resource IDs:

```json
{
  "createNewIdentities": { "value": false },
  "existingIdentityResourceIds": {
    "value": {
      "ingestion": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/ingestion-identity",
      "parsing": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/parsing-identity",
      "chunking": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/chunking-identity",
      "embedding": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/embedding-identity",
      "orchestrator": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/orchestrator-identity",
      "summarization": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/summarization-identity",
      "reporting": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/reporting-identity",
      "auth": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/auth-identity",
      "ui": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/ui-identity",
      "gateway": "/subscriptions/.../resourceGroups/.../providers/Microsoft.ManagedIdentity/userAssignedIdentities/gateway-identity"
    }
  }
}
```

**Important:** When using existing identities, you **must** provide resource IDs for **all** services listed above. If any service is missing from the `existingIdentityResourceIds` object, deployment will fail. The template does not support partial existing identities.

## Deployment Steps

### Step 1: Prepare External Dependencies

Before deploying, create these external Azure resources (or use existing ones):

#### 1.1 Create Azure Cosmos DB for MongoDB

```bash
# Create Cosmos DB account with MongoDB API
az cosmosdb create \
  --name copilot-cosmosdb \
  --resource-group copilot-rg \
  --kind MongoDB \
  --server-version 4.2 \
  --locations regionName=eastus

# Get connection string
az cosmosdb keys list \
  --name copilot-cosmosdb \
  --resource-group copilot-rg \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" -o tsv
```

#### 1.2 Create Azure Service Bus

```bash
# Create Service Bus namespace (Standard tier minimum)
az servicebus namespace create \
  --name copilot-servicebus \
  --resource-group copilot-rg \
  --location eastus \
  --sku Standard

# Get connection string
az servicebus namespace authorization-rule keys list \
  --namespace-name copilot-servicebus \
  --resource-group copilot-rg \
  --name RootManageSharedAccessKey \
  --query primaryConnectionString -o tsv
```

#### 1.3 Create Azure Storage Account (for archives)

```bash
# Create storage account
az storage account create \
  --name copilotst \
  --resource-group copilot-rg \
  --location eastus \
  --sku Standard_LRS

# Get connection string
az storage account show-connection-string \
  --name copilotst \
  --resource-group copilot-rg \
  --query connectionString -o tsv
```

#### 1.4 Create Azure OpenAI Service (Optional)

```bash
# Create Azure OpenAI resource
az cognitiveservices account create \
  --name copilot-openai \
  --resource-group copilot-rg \
  --location eastus \
  --kind OpenAI \
  --sku S0

# Get endpoint
az cognitiveservices account show \
  --name copilot-openai \
  --resource-group copilot-rg \
  --query properties.endpoint -o tsv

# Get key
az cognitiveservices account keys list \
  --name copilot-openai \
  --resource-group copilot-rg \
  --query key1 -o tsv
```

### Step 2: Update Parameters File

Update the appropriate environment parameters file (e.g., `parameters.dev.json`) with the connection strings obtained in Step 1.

### Step 3: Deploy Using Script

Run the deployment script (see Quick Start section).

### Step 4: Verify Deployment

```bash
# Check deployment status
az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.provisioningState

# List deployed resources
az resource list --resource-group copilot-rg --output table

# Get deployment outputs
az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs
```

## Post-Deployment Configuration

### 1. Configure OAuth Providers (for Auth Service)

Store OAuth credentials in Key Vault:

```bash
# Get Key Vault name from deployment outputs
KEY_VAULT_NAME=$(az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.keyVaultUri.value -o tsv | sed 's|https://||' | sed 's|.vault.azure.net/||')

# Add GitHub OAuth secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-oauth-client-id --value "YOUR_GITHUB_CLIENT_ID"
az keyvault secret set --vault-name $KEY_VAULT_NAME --name github-oauth-client-secret --value "YOUR_GITHUB_CLIENT_SECRET"

# Add Google OAuth secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name google-oauth-client-secret --value "YOUR_GOOGLE_CLIENT_SECRET"

# Add Microsoft OAuth secrets
az keyvault secret set --vault-name $KEY_VAULT_NAME --name microsoft-oauth-client-secret --value "YOUR_MICROSOFT_CLIENT_SECRET"
```

**Important**: After adding secrets to Key Vault, you must update your deployment parameters to reference them:

1. Get the secret URIs from Key Vault:
   ```bash
   # Get GitHub OAuth secret URIs
   GITHUB_CLIENT_ID_URI=$(az keyvault secret show \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-id \
     --query id -o tsv)
   
   GITHUB_CLIENT_SECRET_URI=$(az keyvault secret show \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret \
     --query id -o tsv)
   
   echo "GitHub Client ID URI: $GITHUB_CLIENT_ID_URI"
   echo "GitHub Client Secret URI: $GITHUB_CLIENT_SECRET_URI"
   ```

2. Update your parameter file (e.g., `parameters.dev.json`):
   ```json
   {
     "githubOAuthClientIdSecretUri": {
       "value": "https://your-keyvault.vault.azure.net/secrets/github-oauth-client-id/abc123..."
     },
     "githubOAuthClientSecretSecretUri": {
       "value": "https://your-keyvault.vault.azure.net/secrets/github-oauth-client-secret/def456..."
     }
   }
   ```

3. Redeploy the infrastructure to wire the secrets into the auth Container App:
   ```bash
   ./deploy.sh -g copilot-rg -l eastus -e dev -t latest
   ```

#### Rotating GitHub OAuth Secrets

To rotate GitHub OAuth credentials (recommended every 90 days):

1. **Create new OAuth credentials** in GitHub:
   - Go to your GitHub OAuth App settings
   - Generate a new client secret
   - Keep both old and new credentials temporarily

2. **Update Key Vault with new secrets**:
   ```bash
   # Set new secret values in Key Vault
   az keyvault secret set --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-id --value "NEW_GITHUB_CLIENT_ID"
   
   az keyvault secret set --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret --value "NEW_GITHUB_CLIENT_SECRET"
   ```
   
   This creates new versions of the secrets in Key Vault.

3. **Redeploy or restart the auth Container App**:
   
   Container Apps resolve Key Vault references when a new revision is created. To pick up the new secret versions:
   
   **Option A - Create new revision (recommended)**:
   ```bash
   # Trigger a new deployment to create a new revision
   ./deploy.sh -g copilot-rg -l eastus -e dev -t latest
   ```
   
   **Option B - Restart existing revision**:
   ```bash
   # Find the auth container app name
   AUTH_APP=$(az containerapp list -g copilot-rg \
     --query "[?contains(name, 'auth')].name" -o tsv)
   
   # Restart to create new revision
   az containerapp revision restart \
     --name $AUTH_APP \
     --resource-group copilot-rg \
     --revision $(az containerapp revision list \
       --name $AUTH_APP \
       --resource-group copilot-rg \
       --query "[0].name" -o tsv)
   ```

4. **Verify the auth service picks up new credentials**:
   ```bash
   # Check auth service logs
   az containerapp logs show \
     --name $AUTH_APP \
     --resource-group copilot-rg \
     --follow
   
   # Test GitHub OAuth login flow
   curl https://$GATEWAY_URL/auth/providers
   ```

5. **Remove old GitHub OAuth credentials** after verifying the new ones work.

#### Rollback Guidance

If you need to rollback to previous GitHub OAuth credentials:

1. **Restore previous secret version** in Key Vault:
   ```bash
   # List all versions of a secret
   az keyvault secret list-versions \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret \
     --query "[].{Version:id, Created:attributes.created}" -o table
   
   # Get a specific version
   PREVIOUS_VERSION="abc123..."  # Version ID from list above
   az keyvault secret show \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret \
     --version $PREVIOUS_VERSION
   
   # Set current secret to previous value
   PREVIOUS_VALUE=$(az keyvault secret show \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret \
     --version $PREVIOUS_VERSION \
     --query value -o tsv)
   
   az keyvault secret set \
     --vault-name $KEY_VAULT_NAME \
     --name github-oauth-client-secret \
     --value "$PREVIOUS_VALUE"
   ```

2. **Restart the auth Container App** (see step 3 above)

**Note**: Container Apps cache Key Vault references per revision. Always create a new revision or restart after changing secrets in Key Vault.

### 2. Generate JWT Keys

Generate JWT signing keys for the auth service:

```bash
# Generate RSA key pair
python auth/generate_keys.py

# Upload to Key Vault
az keyvault secret set --vault-name $KEY_VAULT_NAME --name jwt-private-key --file secrets/jwt_private_key
az keyvault secret set --vault-name $KEY_VAULT_NAME --name jwt-public-key --file secrets/jwt_public_key
```

### 3. Test the Deployment

Get the gateway URL from deployment outputs:

```bash
GATEWAY_URL=$(az deployment group show \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --query properties.outputs.gatewayUrl.value -o tsv)

echo "Gateway URL: https://$GATEWAY_URL"

# Test health endpoints
curl https://$GATEWAY_URL/reporting/health
curl https://$GATEWAY_URL/auth/health
```

### 4. Configure Monitoring Alerts

Set up alerts in Application Insights for:
- High error rates
- Service availability
- Performance degradation

```bash
# Example: Create alert for failed requests
az monitor metrics alert create \
  --name "High Error Rate" \
  --resource-group copilot-rg \
  --scopes $(az monitor app-insights component show --app copilot-insights-* --resource-group copilot-rg --query id -o tsv) \
  --condition "count requests/failed > 10" \
  --window-size 5m \
  --evaluation-frequency 1m
```

## Monitoring and Observability

### Application Insights

All Container Apps automatically send telemetry to Application Insights:

- **Traces**: Application logs
- **Metrics**: Performance counters, custom metrics
- **Exceptions**: Unhandled errors
- **Dependencies**: Database and external service calls

Access Application Insights in Azure Portal:
1. Navigate to your resource group
2. Open the Application Insights resource
3. Use "Logs" for KQL queries, "Metrics" for dashboards

### Log Analytics

All container logs are aggregated in Log Analytics:

```kusto
// Query logs from all services
ContainerAppConsoleLogs_CL
| where TimeGenerated > ago(1h)
| project TimeGenerated, ContainerAppName_s, Log_s
| order by TimeGenerated desc
```

### Pre-Built Dashboards

The deployment includes Application Insights dashboards for:
- Service health and availability
- Request throughput and latency
- Error rates and exceptions
- Resource utilization

## Troubleshooting

### Common Issues

#### 1. Deployment Validation Fails

**Error**: "Template validation failed"

**Solution**: Check that all required parameters are provided and connection strings are valid.

#### 2. Container Apps Fail to Start

**Error**: "Container failed to pull image"

**Solution**: 
- Verify GHCR images exist at `ghcr.io/alan-jowett/copilot-for-consensus`
- Check if Container Apps have outbound internet access
- Ensure images are public or provide registry credentials

#### 3. Services Can't Access Key Vault

**Error**: "Forbidden: Access denied to Key Vault"

**Solution**:
- Verify managed identities were created and assigned
- Check RBAC role assignments (Key Vault Secrets User)
- Ensure Key Vault has RBAC authorization enabled

#### 4. MongoDB Connection Fails

**Error**: "Failed to connect to MongoDB"

**Solution**:
- Verify connection string format
- Check Cosmos DB firewall rules (allow Container Apps subnet or enable public access)
- Ensure Cosmos DB is running and accessible

### Debugging Container Apps

View logs from a specific service:

```bash
az containerapp logs show \
  --name copilot-ingestion \
  --resource-group copilot-rg \
  --follow
```

Execute commands in a running container:

```bash
az containerapp exec \
  --name copilot-ingestion \
  --resource-group copilot-rg \
  --command /bin/bash
```

## Cost Estimation

Approximate monthly costs for a development deployment (prices vary by region):

| Resource | SKU | Estimated Cost |
|----------|-----|----------------|
| Container Apps Environment | Consumption | ~$50/month |
| Container Apps (10 services) | 0.5-1.0 vCPU, 1-2GB RAM | ~$200-400/month |
| Cosmos DB for MongoDB | 400 RU/s | ~$25/month |
| Azure Service Bus | Standard | ~$10/month |
| Storage Account | Standard LRS, 100GB | ~$2/month |
| Application Insights | Basic, 5GB/month | ~$10/month |
| Log Analytics | 5GB ingestion | ~$15/month |
| Key Vault | Standard | ~$1/month |
| Azure OpenAI | GPT-4, 1M tokens | ~$30/month |

**Total Estimated Cost**: ~$350-550/month for development

For production, costs will scale with:
- Container Apps autoscaling (more replicas)
- Cosmos DB throughput (higher RU/s)
- Service Bus messaging volume
- Application Insights data retention

Use the [Azure Pricing Calculator](https://azure.microsoft.com/en-us/pricing/calculator/) for detailed estimates.

## Security Best Practices

### 1. Use Managed Identities

- ✅ All services use user-assigned managed identities
- ✅ No connection strings or passwords in application code
- ✅ RBAC-based access to Azure resources

### 2. Secure Secrets in Key Vault

- ✅ All secrets stored in Azure Key Vault
- ✅ Key Vault uses RBAC (not access policies)
- ✅ Soft delete enabled for accidental deletion protection

### 3. Network Security

- ✅ Container Apps deployed in VNet
- ✅ Private endpoints for Cosmos DB, Service Bus, Storage (recommended for production)
- ✅ Network Security Groups (NSGs) for subnet-level firewall rules

### 4. Enable Azure Defender

```bash
# Enable Defender for Container Apps
az security pricing create \
  --name Containers \
  --tier Standard
```

### 5. Monitor and Audit

- ✅ Application Insights for telemetry
- ✅ Azure Monitor alerts for anomalies
- ✅ Azure Activity Log for control plane operations
- ✅ Key Vault audit logs for secret access

### 6. Least Privilege RBAC

Each managed identity has only the permissions it needs:
- **ingestion**: Blob Data Contributor, Service Bus Data Sender
- **parsing**: Blob Data Reader, Service Bus Data Sender/Receiver
- **auth**: Key Vault Secrets User
- **reporting**: Blob Data Reader

### 7. Keep Containers Updated

- Use specific image tags (not `latest`) for production
- Regularly update base images and dependencies
- Scan images for vulnerabilities using Trivy or Azure Defender

## Additional Resources

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Azure Managed Identities](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/overview)
- [Azure RBAC Documentation](https://learn.microsoft.com/en-us/azure/role-based-access-control/)
- [Copilot for Consensus Architecture](../../documents/ARCHITECTURE.md)
- [Copilot for Consensus Contributing Guide](../../CONTRIBUTING.md)

## Support

For issues or questions:
- Open an issue: https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues
- Consult documentation: https://github.com/Alan-Jowett/CoPilot-For-Consensus/tree/main/documents

---

**License**: MIT  
**Copyright**: © 2025 Copilot-for-Consensus contributors
