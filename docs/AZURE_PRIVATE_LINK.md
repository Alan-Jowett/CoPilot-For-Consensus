<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Private Network Access with Private Link

## Overview

The Copilot-for-Consensus Azure infrastructure supports deployment-time configuration for private network access using Azure Private Link. This allows you to disable public network access and connect to Azure services privately through Private Endpoints within your Virtual Network.

## Why Private Network Access?

Private network access provides several security benefits:

- **No public internet exposure**: Resources are not accessible from the public internet
- **Traffic stays on Microsoft backbone**: Data doesn't traverse the public internet
- **Network isolation**: Resources are isolated within your VNet
- **Fine-grained network policies**: Use Network Security Groups (NSGs) and subnet-level controls
- **Compliance**: Meets compliance requirements for data residency and network isolation

## Supported Resources

The following Azure resources support Private Link configuration:

| Resource | Private Link Group ID | DNS Zone |
|----------|----------------------|----------|
| Azure Key Vault | `vault` | `privatelink.vaultcore.azure.net` |
| Azure Cosmos DB | `Sql` | `privatelink.documents.azure.com` |
| Azure Storage (Blob) | `blob` | `privatelink.blob.core.windows.net` (Azure Commercial) |
| Azure Service Bus | `namespace` | `privatelink.servicebus.windows.net` |
| Azure AI Search | `searchService` | `privatelink.search.windows.net` |
| Azure OpenAI | `account` | `privatelink.openai.azure.com` |

**Note**: DNS zone names are automatically adjusted for different Azure cloud environments (Commercial, Government, China).

## Configuration

### Parameter: `enablePrivateAccess`

The infrastructure uses a single boolean parameter `enablePrivateAccess` to control private network access:

- **`enablePrivateAccess=true`**: Disables public network access and creates Private Endpoints
- **`enablePrivateAccess=false`** (default): Uses public endpoints for easier development/testing

When `enablePrivateAccess=true`, the deployment automatically:

1. Disables public network access on all resources
2. Creates a dedicated subnet for Private Endpoints
3. Creates Private Endpoints for each resource
4. Creates Private DNS Zones for name resolution
5. Links Private DNS Zones to the VNet

### Environment Defaults

The default parameter files are configured as follows:

| Environment | enablePrivateAccess | Purpose |
|------------|-------------------|---------|
| Dev | `false` | Public access for easier local testing |
| Staging | `false` | Public access for pre-production validation |
| Prod | `true` | Private access for production security |

## Deployment

### Core Infrastructure (Azure OpenAI + Key Vault)

Deploy the Core infrastructure with private access:

```bash
# Production (Private Link enabled)
az deployment group create \
  --resource-group rg-core-ai \
  --template-file infra/azure/core.bicep \
  --parameters infra/azure/parameters.core.prod.json

# Development (Public access)
az deployment group create \
  --resource-group rg-core-ai \
  --template-file infra/azure/core.bicep \
  --parameters infra/azure/parameters.core.dev.json
```

### Environment Infrastructure (App Services)

Deploy the environment infrastructure with private access:

```bash
# Production (Private Link enabled)
az deployment group create \
  --resource-group rg-copilot-prod \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.prod.json

# Development (Public access)
az deployment group create \
  --resource-group rg-copilot-dev \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.dev.json
```

## Network Architecture

When `enablePrivateAccess=true`, the infrastructure creates the following network topology:

```
Virtual Network (e.g., 10.0.0.0/16)
├── Container Apps Subnet (10.0.0.0/23)
│   └── Container Apps Environment
│       ├── Ingestion Service
│       ├── Parsing Service
│       ├── Chunking Service
│       ├── Embedding Service
│       ├── Orchestrator Service
│       ├── Summarization Service
│       ├── Reporting Service
│       ├── Auth Service
│       ├── UI Service
│       └── Gateway Service
└── Private Endpoint Subnet (10.0.2.0/24)
    ├── Key Vault Private Endpoint
    ├── Cosmos DB Private Endpoint
    ├── Storage Account Private Endpoint
    ├── Service Bus Private Endpoint
    └── AI Search Private Endpoint (if using azure_ai_search)

Private DNS Zones (linked to VNet)
├── privatelink.vaultcore.azure.net
├── privatelink.documents.azure.com
├── privatelink.blob.core.windows.net
├── privatelink.servicebus.windows.net
├── privatelink.search.windows.net
└── privatelink.openai.azure.com
```

### VNet Integration

Container Apps are deployed with VNet integration, allowing them to:

- Access Private Endpoints within the VNet
- Resolve private DNS names automatically
- Communicate with resources without internet traversal

## DNS Resolution

Private DNS Zones ensure that Container Apps resolve Azure service FQDNs to private IP addresses:

| Service FQDN | Public Resolution | Private Resolution |
|-------------|------------------|-------------------|
| `mykeyvault.vault.azure.net` | Public IP | 10.0.2.4 (Private Endpoint) |
| `mycosmosdb.documents.azure.com` | Public IP | 10.0.2.5 (Private Endpoint) |
| `mystorage.blob.core.windows.net` | Public IP | 10.0.2.6 (Private Endpoint) |

Private DNS Zones are automatically linked to the VNet, so Container Apps resolve names correctly without additional configuration.

## Subnet Planning

When enabling Private Link, ensure your VNet address space accommodates both subnets:

| Subnet | Default CIDR | Adjustable Parameter | Purpose |
|--------|-------------|---------------------|---------|
| Container Apps | `10.0.0.0/23` | `subnetAddressPrefix` | Hosts Container Apps Environment |
| Private Endpoints | `10.0.2.0/24` | `privateEndpointSubnetPrefix` | Hosts Private Endpoints |

**Recommendation**: Use at least a `/16` VNet address space (e.g., `10.0.0.0/16`) to allow for future growth.

## Cost Considerations

Private Link has additional costs:

- **Private Endpoint**: ~$7.20/month per endpoint (~6 endpoints = ~$43/month)
- **Private DNS Zone**: ~$0.50/month per zone (~6 zones = ~$3/month)
- **Data processing**: $0.01/GB processed through Private Link

**Total additional cost**: ~$46-50/month for private network access in production.

## Migrating from Public to Private Access

To migrate an existing deployment from public to private access:

1. **Update parameter file**: Set `enablePrivateAccess=true`
2. **Deploy changes**: Run `az deployment group create` with updated parameters
3. **Validate connectivity**: Ensure Container Apps can reach resources via Private Endpoints
4. **Monitor**: Check for any connection errors in Application Insights

**Important**: Container Apps must have VNet integration for Private Link to work. This is enabled by default when `deployContainerApps=true`.

## Troubleshooting

### Container Apps Can't Reach Private Endpoints

**Symptoms**: Connection timeouts, DNS resolution failures

**Solution**:
1. Verify Container Apps are deployed in the VNet-integrated subnet
2. Check that Private DNS Zones are linked to the VNet
3. Verify Private Endpoints are in "Succeeded" state:
   ```bash
   az network private-endpoint list --resource-group <rg> --output table
   ```

### DNS Not Resolving Private IPs

**Symptoms**: Container Apps resolve public IPs instead of private IPs

**Solution**:
1. Verify Private DNS Zones are linked to the VNet:
   ```bash
   az network private-dns link vnet list --resource-group <rg> --zone-name privatelink.vaultcore.azure.net
   ```
2. Check Private DNS Zone Group configuration on Private Endpoints

### Public Access Still Enabled

**Symptoms**: Resources are still accessible from the public internet

**Solution**:
1. Verify `enablePrivateAccess=true` in parameter file
2. Check resource properties:
   ```bash
   az keyvault show --name <keyvault> --query properties.publicNetworkAccess
   az cosmosdb show --name <cosmosdb> --query publicNetworkAccess
   ```
3. Expected value: `Disabled`

## Security Best Practices

1. **Always enable Private Link for production**: Set `enablePrivateAccess=true`
2. **Use Network Security Groups**: Restrict traffic at the subnet level
3. **Enable Azure Firewall**: For additional network inspection and filtering
4. **Monitor access logs**: Enable diagnostic settings on all resources
5. **Use Azure Policy**: Enforce Private Link across subscriptions

## Related Documentation

- [Azure Private Link Overview](https://learn.microsoft.com/en-us/azure/private-link/private-link-overview)
- [Azure Private Link for Cosmos DB](https://learn.microsoft.com/en-us/azure/cosmos-db/how-to-configure-private-endpoints)
- [Azure Private Link for Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/general/private-link-service)
- [Azure Private Link for Storage](https://learn.microsoft.com/en-us/azure/storage/common/storage-private-endpoints)
- [Azure Private Link for Service Bus](https://learn.microsoft.com/en-us/azure/service-bus-messaging/private-link-service)
- [Container Apps VNet Integration](https://learn.microsoft.com/en-us/azure/container-apps/vnet-custom)

## Examples

### Deploying with Private Access

```bash
# Deploy Core infrastructure with Private Link (prod)
az deployment group create \
  --resource-group rg-core-ai \
  --template-file infra/azure/core.bicep \
  --parameters infra/azure/parameters.core.prod.json \
  --name core-deployment-$(date +%Y%m%d-%H%M%S)

# Deploy environment infrastructure with Private Link (prod)
az deployment group create \
  --resource-group rg-copilot-prod \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.prod.json \
  --name env-deployment-$(date +%Y%m%d-%H%M%S)
```

### Deploying with Public Access

```bash
# Deploy Core infrastructure with public access (dev)
az deployment group create \
  --resource-group rg-core-ai-dev \
  --template-file infra/azure/core.bicep \
  --parameters infra/azure/parameters.core.dev.json \
  --name core-dev-deployment-$(date +%Y%m%d-%H%M%S)

# Deploy environment infrastructure with public access (dev)
az deployment group create \
  --resource-group rg-copilot-dev \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/parameters.dev.json \
  --name env-dev-deployment-$(date +%Y%m%d-%H%M%S)
```

### Validating Private Endpoint Connectivity

```bash
# List all Private Endpoints
az network private-endpoint list \
  --resource-group rg-copilot-prod \
  --output table

# Check Private Endpoint connection state
az network private-endpoint show \
  --resource-group rg-copilot-prod \
  --name <pe-name> \
  --query 'privateLinkServiceConnections[0].privateLinkServiceConnectionState.status'

# Verify DNS resolution (from within VNet)
# This must be run from a VM or Container App inside the VNet
nslookup mykeyvault.vault.azure.net
# Should return 10.0.2.x (private IP), not a public IP
```

## Support

For issues or questions about Private Link configuration:

1. Check the [troubleshooting section](#troubleshooting) above
2. Review Azure Private Link documentation
3. Open an issue in the repository with deployment logs
