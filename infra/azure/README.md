<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Deployment Guide for Copilot for Consensus

This guide provides instructions for deploying Copilot for Consensus to Azure using Azure Resource Manager (ARM) templates with managed identity support.

## Table of Contents

- [Overview](#overview)
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

## Overview

The ARM template (`azuredeploy.json`) automates the deployment of the entire Copilot for Consensus architecture to Azure, including:

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

- **Azure CLI** (version 2.50.0 or later)
  - Install: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli
- **Azure PowerShell** (Az module, version 10.0.0 or later) - for PowerShell deployment
  - Install: `Install-Module -Name Az -AllowClobber -Scope CurrentUser`
- **Bash** (for Linux/macOS/WSL) or **PowerShell** (for Windows)

### Azure Resources

- **Active Azure Subscription** with permissions to:
  - Create resource groups
  - Deploy resources (Contributor role or higher)
  - Assign RBAC roles (User Access Administrator or Owner)
- **Azure Cosmos DB for MongoDB** or **Azure Database for MongoDB** (or provide external MongoDB connection string)
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

Edit `azuredeploy.parameters.json` to set your configuration:

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
  --template-file azuredeploy.json \
  --parameters @azuredeploy.parameters.json

# Deploy
az deployment group create \
  --name copilot-deployment \
  --resource-group copilot-rg \
  --template-file azuredeploy.json \
  --parameters @azuredeploy.parameters.json
```

## Configuration

### Required Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `mongoDbConnectionString` | securestring | MongoDB or Cosmos DB connection string |
| `serviceBusConnectionString` | securestring | Azure Service Bus connection string |
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
| `vnetAddressPrefix` | string | `10.0.0.0/16` | Virtual network address prefix |
| `subnetAddressPrefix` | string | `10.0.0.0/23` | Container Apps subnet prefix |

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

Update `azuredeploy.parameters.json` with the connection strings obtained in Step 1.

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
- [Copilot for Consensus Architecture](../../docs/architecture/overview.md)
- [Copilot for Consensus Contributing Guide](../../CONTRIBUTING.md)

## Support

For issues or questions:
- Open an issue: https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues
- Consult documentation: https://github.com/Alan-Jowett/CoPilot-For-Consensus/tree/main/documents

---

**License**: MIT  
**Copyright**: © 2025 Copilot-for-Consensus contributors
