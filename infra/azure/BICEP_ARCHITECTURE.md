<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Infrastructure Bicep Templates

This directory contains Bicep Infrastructure-as-Code (IaC) templates for deploying the Copilot for Consensus platform to Azure Container Apps.

## Architecture Overview

### Core Services

The infrastructure provisions the following Azure services:

- **Azure Container Apps**: Managed Kubernetes container runtime for 10 microservices
- **Azure Container Registry**: Private image repository
- **Azure Service Bus**: Message broker for asynchronous service communication
- **Azure Cosmos DB**: NoSQL document store with multi-region capability
- **Azure AI Search**: Vector database for semantic search and embeddings
- **Azure OpenAI**: LLM inference via managed service
- **Azure Key Vault**: Secrets and credential management
- **Application Insights**: Observability and distributed tracing
- **Azure Log Analytics**: Centralized logging

### Microservices

| Service | Purpose | Protocols |
|---------|---------|-----------|
| **auth** | JWT token generation and validation | HTTP/gRPC |
| **gateway** | API entry point with routing and authentication | HTTP/HTTPS |
| **parsing** | Document parsing (PDF, DOCX, etc.) | HTTP |
| **chunking** | Document segmentation for embedding | HTTP |
| **embedding** | Vector embeddings via Azure OpenAI | HTTP |
| **orchestrator** | Workflow coordination | HTTP |
| **summarization** | Document summarization | HTTP |
| **reporting** | API for query results and analytics | HTTP |
| **ingestion** | Data ingest from external sources | HTTP |
| **ui** | Web dashboard | HTTP/HTTPS |

## Network Architecture

### VNet Design (Non-Overlapping Address Spaces)

Each environment uses a distinct VNet address space to enable future VNet peering or hybrid connectivity without address conflicts:

```
Dev (westus)         10.0.0.0/16
├─ Subnet           10.0.0.0/23
├─ Available IPs:   512

Staging (eastus)    10.1.0.0/16
├─ Subnet           10.1.0.0/23
├─ Available IPs:   512

Prod (westus)       10.2.0.0/16
├─ Subnet           10.2.0.0/23
├─ Available IPs:   512
```

**Design Benefits:**
- **Isolation**: Address spaces don't overlap, so environments can be connected later
- **Scalability**: Each /23 subnet provides 512 IPs (sufficient for Container Apps + ancillary resources)
- **Flexibility**: Future hub-and-spoke topology or cross-region failover can use these spaces
- **Compliance**: Clear separation enables environment-level access controls

### Internal Service Communication

Container Apps communicate internally via DNS:

```
Service URL Pattern: http://<project>-<service>-<environment>:<port>

Example (Dev):
- Auth service:       http://copilot-auth-dev:8090
- Reporting service:  http://copilot-reporting-dev:8080
- Gateway:            http://copilot-gateway-dev:8080
```

### External Access

Only the **gateway** service is exposed externally via the Container Apps ingress. All other services are internal-only, accessible only from within the VNet.

```
Internet → Gateway (HTTPS) → Internal services (HTTP)
           ↓ (routes to)
           Auth, Reporting, Parsing, etc.
```

## Bicep Module Structure

### Module Organization

```
modules/
├── identity.bicep              # Managed identities for all services
├── keyvault.bicep              # Key Vault for secrets
├── cosmosdb.bicep              # Cosmos DB document store
├── servicebus.bicep            # Service Bus message broker
├── aisearch.bicep              # Azure AI Search vector store
├── openai.bicep                # Azure OpenAI deployment
├── monitoring.bicep            # Application Insights & Log Analytics
├── containerapps.bicep         # Container Apps environment & services
└── vnet.bicep                  # VNet and subnets
```

### Key Design Patterns

#### 1. **Managed Identities (Zero-Secrets Approach)**

All service-to-service communication uses **Azure Managed Identities** with RBAC:

```bicep
// In identity.bicep
resource embeddingIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectPrefix}-embedding-identity-${environment}'
  location: location
}

// In aisearch.bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: searchService
  name: guid(searchService.id, embeddingIdentity.id)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'c7f06df5-9f78-4436-8adb-a0e7c60c9a45')
    principalId: embeddingIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}
```

**Benefits:**
- No credentials stored in environment variables
- Automatic token rotation via Azure
- Fine-grained RBAC role assignments
- Audit trail of service access

#### 2. **Conditional Deployments Per Environment**

Services deployed conditionally based on environment flags:

```bicep
// Deploy Azure OpenAI only if deployAzureOpenAI is true
module openai 'modules/openai.bicep' = if (deployAzureOpenAI) {
  name: 'openai'
  scope: resourceGroup()
  params: {
    // ...
  }
}
```

#### 3. **Parameter Passing for Configuration**

Connection strings and endpoints passed as parameters, not hardcoded:

```bicep
param serviceBusNamespace string
param cosmosDbEndpoint string
param aiSearchEndpoint string

// Used in Container Apps environment variables
environmentVariables: [
  {
    name: 'SERVICE_BUS_NAMESPACE'
    value: serviceBusNamespace
  }
]
```

## Deployment Parameters

Each environment (dev, staging, prod) has a dedicated parameter file:

### parameters.dev.json
- **Location**: westus
- **VNet**: 10.0.0.0/16
- **Cosmos DB**: 400-1000 RU (autoscale, single-region)
- **Service Bus**: Standard tier
- **Deployed**: When working on new features

### parameters.staging.json
- **Location**: eastus
- **VNet**: 10.1.0.0/16
- **Cosmos DB**: 1000-2000 RU (autoscale, single-region)
- **Service Bus**: Standard tier
- **Deployed**: Before production validation

### parameters.prod.json
- **Location**: westus
- **VNet**: 10.2.0.0/16
- **Cosmos DB**: 2000-4000 RU (autoscale, multi-region)
- **Service Bus**: Premium tier
- **Deployed**: For production workloads

## Security Considerations

### 1. **TLS Enforcement**

Gateway ingress enforces HTTPS-only:

```bicep
allowInsecure: false  // No HTTP fallback
```

### 2. **API Key Removal**

Azure AI Search disables local authentication:

```bicep
disableLocalAuth: true  // RBAC-only, no API keys
```

### 3. **Role-Based Access Control (RBAC)**

Each service has minimal required permissions:

| Service | Roles |
|---------|-------|
| Embedding | Service Bus Sender, AI Search Index Data Contributor |
| Orchestrator | Service Bus Sender/Receiver, Cosmos DB Data Contributor |
| Ingestion | Service Bus Sender, Cosmos DB Data Contributor |
| Reporting | Service Bus Receiver, Cosmos DB Data Contributor |
| Gateway | Service Bus Sender (for audit logging) |

### 4. **Private Endpoints (Recommended for Prod)**

Future enhancement: Deploy private endpoints for Key Vault, Cosmos DB, Service Bus to restrict public access.

## Bicep Validation

Before deployment, validate Bicep templates:

```powershell
# Windows PowerShell
az bicep build --file main.bicep

# Output: main.json (ARM template)
```

Expected warnings:
- **BCP318**: Conditional module references (expected for dev/staging/prod conditionals)

No errors should occur.

## Deployment Workflow

### Prerequisites

1. **Azure CLI 2.50+**
   ```powershell
   az --version
   az bicep version
   ```

2. **Service Principal or User Auth**
   ```powershell
   az login
   az account set --subscription <subscription-id>
   ```

3. **Resource Groups Pre-created**
   ```powershell
   az group create --name copilot-dev-rg --location westus
   ```

### Deploy

```powershell
# Dev environment
az deployment group create `
  --resource-group copilot-dev-rg `
  --template-file main.bicep `
  --parameters parameters.dev.json

# Staging environment
az deployment group create `
  --resource-group copilot-staging-rg `
  --template-file main.bicep `
  --parameters parameters.staging.json

# Prod environment (Premium SB, multi-region Cosmos, etc.)
az deployment group create `
  --resource-group copilot-prod-rg `
  --template-file main.bicep `
  --parameters parameters.prod.json
```

### Post-Deployment Validation

1. **Container Apps Health**
   ```powershell
   az containerapp show --name copilot-auth-dev -g copilot-dev-rg
   az containerapp logs show --name copilot-auth-dev -g copilot-dev-rg
   ```

2. **Service Communication**
   ```powershell
   # Test gateway endpoint
   curl https://<gateway-fqdn>/health
   ```

3. **Managed Identity Roles**
   ```powershell
   # List role assignments for a service identity
   az role assignment list --assignee <service-principal-id>
   ```

## Troubleshooting

### Service Cannot Resolve Peer Service

**Symptom**: Service A cannot connect to Service B

**Check**:
1. Verify DNS name: Should be `copilot-<service>-<environment>`, not short name
2. Verify port is correct (check `servicePorts` in containerapps.bicep)
3. Verify both services are in the same Container Apps environment

**Fix**: Update UPSTREAM_* environment variable in gateway or service discovery configuration

### Managed Identity Permission Denied

**Symptom**: "Unauthorized" error when accessing Cosmos DB / Service Bus

**Check**:
1. Verify identity is assigned to the service: `az containerapp identity show`
2. Verify role is assigned: `az role assignment list --assignee <principalId>`
3. Verify role is correct for the resource (e.g., "Cosmos DB Built-in Data Contributor")

**Fix**: Add role assignment via `az role assignment create` or update Bicep module

### Slow Container Startup

**Symptom**: Container Apps taking 2-5 minutes to become "Healthy"

**Expected**: Normal for first deployment; health checks have startup probe delay

**Solution**: Monitor logs via `az containerapp logs show` or Azure Portal

## Cost Estimation

### Monthly Costs (Approximate)

| Component | Dev | Staging | Prod |
|-----------|-----|---------|------|
| **Container Apps** | $50-100 | $100-200 | $200-500 |
| **Cosmos DB** | $50-150 | $150-300 | $300-800 |
| **Service Bus** | $25 | $25 | $60 |
| **AI Search** | $150 | $150 | $300 |
| **Azure OpenAI** | $150 | $150 | $200 |
| **Application Insights** | $10-50 | $50-100 | $100-200 |
| **Total** | ~$435-495 | ~$625-825 | ~$1,160-1,860 |

## References

- [Bicep Documentation](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/)
- [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Managed Identities](https://learn.microsoft.com/en-us/azure/active-directory/managed-identities-azure-resources/)
- [RBAC in Azure](https://learn.microsoft.com/en-us/azure/role-based-access-control/)
