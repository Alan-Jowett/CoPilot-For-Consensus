<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Infrastructure Deployment Guide

## Overview

This directory contains Bicep Infrastructure-as-Code templates for deploying Copilot for Consensus to Azure. The infrastructure supports three environments: **dev**, **staging**, and **prod**, each with distinct configurations optimized for their respective use cases.

## Environment Configuration

### Network Address Spaces

Each environment uses a **non-overlapping VNet address space** to support future interconnection via VNet peering or hybrid connectivity (ExpressRoute). This design ensures environments can be connected without address conflicts:

| Environment | VNet CIDR   | Subnet CIDR  | Location | Region |
|-------------|-------------|-------------|----------|--------|
| **Dev**     | 10.0.0.0/16 | 10.0.0.0/23 | westus   | West US 2 |
| **Staging** | 10.1.0.0/16 | 10.1.0.0/23 | eastus   | East US  |
| **Prod**    | 10.2.0.0/16 | 10.2.0.0/23 | westus   | West US 2 |

**Design Rationale:**
- Non-overlapping address spaces (10.0, 10.1, 10.2) enable VNet peering between environments if needed for disaster recovery or hybrid scenarios
- Each environment is isolated by default (separate subscriptions recommended)
- Subnet /23 provides 512 IP addresses per environment, sufficient for Container Apps and ancillary resources
- Dev and Prod both use `westus` for cost efficiency; Staging uses `eastus` for geographic redundancy testing

### Service Tier Differences

| Component | Dev | Staging | Prod |
|-----------|-----|---------|------|
| **Cosmos DB** | 400-1000 RU (autoscale) | 1000-2000 RU (autoscale) | 2000-4000 RU (autoscale) + Multi-region |
| **Service Bus** | Standard | Standard | Premium |
| **Container Apps** | Consumption (minReplicas: 0) | Consumption (minReplicas: 1) | Consumption (minReplicas: 1) |
| **Azure AI Search** | Basic | Basic | Standard |
| **Azure OpenAI** | S0 Deployment | S0 Deployment | S0 Deployment (GlobalStandard for perf) |

## Deployment

### Prerequisites

1. **Azure CLI** with Bicep support:
   ```powershell
   az bicep version
   az bicep build --file main.bicep
   ```

2. **Subscription Access**: Ensure you have sufficient permissions to create resources in the target subscription

3. **Resource Groups**: Create a resource group per environment:
   ```powershell
   az group create --name copilot-dev-rg --location westus
   az group create --name copilot-staging-rg --location eastus
   az group create --name copilot-prod-rg --location westus
   ```

### Deploy Dev Environment

```powershell
az deployment group create `
  --resource-group copilot-dev-rg `
  --template-file main.bicep `
  --parameters parameters.dev.json
```

### Deploy Staging Environment

```powershell
az deployment group create `
  --resource-group copilot-staging-rg `
  --template-file main.bicep `
  --parameters parameters.staging.json
```

### Deploy Prod Environment

```powershell
az deployment group create `
  --resource-group copilot-prod-rg `
  --template-file main.bicep `
  --parameters parameters.prod.json
```

## Security Configuration

### Managed Identities

All Container Apps use **user-assigned managed identities** for service-to-service authentication:

- **Service Bus**: Services authenticate via managed identity with RBAC role assignments (Sender/Receiver)
- **Cosmos DB**: Services authenticate via managed identity with RBAC role assignments
- **Azure AI Search**: Services authenticate via managed identity with RBAC (Search Index Data Contributor)
- **Azure OpenAI**: Services authenticate via managed identity with RBAC (Cognitive Services User)

**No connection strings or API keys are stored in environment variables**, reducing blast radius of potential compromises.

### Network Security

- **VNet Integration**: Container Apps are deployed to a managed VNet for improved isolation
- **Gateway TLS**: Container Apps platform handles TLS termination; external ingress is HTTPS-only (443 → 8080 internally, `allowInsecure: false`)
- **Internal DNS**: Services communicate via internal DNS using full container app names (e.g., `copilot-auth-dev:8090`)
- **Private Network Access**: Recommended configuration for production:
  - Azure OpenAI: Public endpoint with IP allowlisting (configure `azureOpenAIAllowedCidrs`)
  - Key Vault: Private endpoint via VNet
  - Cosmos DB: Private endpoint via VNet
  - Service Bus: Private endpoint via VNet

## Observability

All services are configured with:

- **Application Insights**: Connection string passed via environment variable (`APPLICATIONINSIGHTS_CONNECTION_STRING`)
- **Log Analytics**: Container Apps environment logs to Log Analytics workspace
- **Azure Monitor**: Metrics and alerts can be configured post-deployment

## Troubleshooting

### Service-to-Service Communication Fails

**Symptom**: Services cannot resolve other internal services (e.g., reporting → auth)

**Cause**: DNS resolution uses full container app names, not short service names

**Solution**: Verify environment variables match the pattern:
```bicep
'http://${projectPrefix}-<service>-${environment}:<port>'
# Example: http://copilot-auth-dev:8090
```

### Managed Identity Permissions

**Symptom**: Service fails with "Unauthorized" accessing Cosmos DB or Service Bus

**Cause**: Managed identity not assigned the correct RBAC role

**Solution**: Verify role assignments in the Bicep modules:
- Service Bus: Sender/Receiver roles per service type
- Cosmos DB: Cosmos DB Built-in Data Contributor
- Azure AI Search: Search Index Data Contributor

### Container Apps Startup Delay

**Symptom**: Services take 2-5 minutes to become healthy

**Expected**: Normal for first deployment; health checks retry with exponential backoff

**Solution**: Monitor via `az containerapp logs show` or Azure Portal → Container Apps → Logs

## Cost Optimization

- **Dev**: Uses Standard Service Bus and autoscale Cosmos DB (400-1000 RU) for cost efficiency
- **Staging**: Balanced tier with Standard Service Bus and moderate Cosmos DB (1000-2000 RU)
- **Prod**: Premium Service Bus for SLA, higher Cosmos DB autoscale, and multi-region replication
- **Container Apps**: Consumption workload profile (pay-per-execution, no minimum cost)

### Scale-to-Zero in Dev Environment

**Dev environment** is configured with `minReplicas: 0` for all Container Apps to reduce idle costs:

**Benefits:**
- **Cost Savings**: Save ~$50-100/month on Container Apps during idle periods (nights, weekends)
- **Azure Consumption Plan**: Only charges when containers are actively running
- **Automatic Scaling**: Services automatically scale from 0 to 1+ replicas on demand

**Trade-offs:**
- **Cold Start Delay**: First request after idle period takes 10-60 seconds to complete
- **Acceptable for Dev**: Development workflows can tolerate the latency

**Affected Services:**
- **HTTP-triggered**: auth, gateway, reporting, ui, ingestion (wake on HTTP traffic)
- **Message-bus-triggered**: parsing, chunking, embedding, orchestrator, summarization (wake on queue messages)

**Verification:**
```powershell
# Verify scale configuration for dev environment
az containerapp show --name copilot-auth-dev -g copilot-dev-rg --query properties.template.scale
# Expected output: {"minReplicas": 0, "maxReplicas": 2}

# Check all services at once
$services = @('auth', 'gateway', 'reporting', 'ui', 'ingestion', 'parsing', 'chunking', 'embedding', 'orchestrator', 'summarization')
foreach ($svc in $services) {
  $config = az containerapp show --name "copilot-$svc-dev" -g copilot-dev-rg --query properties.template.scale -o json | ConvertFrom-Json
  Write-Host "$svc : minReplicas=$($config.minReplicas), maxReplicas=$($config.maxReplicas)"
}
```

**Testing Cold Starts:**
```powershell
# Wait for services to scale to zero (after ~5 minutes of no traffic)
az containerapp replica list --name copilot-auth-dev -g copilot-dev-rg
# When idle, this should show 0 replicas

# Trigger a cold start by sending a request
Invoke-WebRequest -Uri "https://<gateway-fqdn>/health" -UseBasicParsing
# First request will take 10-30 seconds; subsequent requests will be fast
```

**Staging/Prod:** Always maintain `minReplicas: 1` for immediate response times.

## OAuth Authentication with Microsoft Entra

The deployment includes automated provisioning of Microsoft Entra (Azure AD) app registrations for OAuth authentication. This feature automates the manual steps typically required to set up OAuth.

### Automated Entra App Setup

The Bicep template can automatically:
- Create or update a Microsoft Entra app registration
- Configure redirect URIs for the auth service callback
- Generate and securely store client secrets in Key Vault
- Set up required Microsoft Graph API permissions

### Prerequisites

The deployment identity must have Microsoft Graph API permissions:
- `Application.ReadWrite.All` - To create/update app registrations
- `Directory.ReadWrite.All` - To create service principals

These permissions must be granted by a Global Administrator. See [ENTRA_APP_AUTOMATION.md](ENTRA_APP_AUTOMATION.md) for detailed setup instructions.

### Deployment Workflow

Since the gateway FQDN is only known after Container Apps deployment, use a two-stage approach:

**Stage 1: Deploy infrastructure without Entra app**
```bash
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters deployEntraApp=false

# Get gateway FQDN
GATEWAY_FQDN=$(az deployment group show \
  --name <deployment-name> \
  --resource-group copilot-dev-rg \
  --query properties.outputs.gatewayFqdn.value -o tsv)
```

**Stage 2: Deploy with Entra app and redirect URI**
```bash
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters deployEntraApp=true \
  --parameters oauthRedirectUris="[\"https://$GATEWAY_FQDN/auth/callback\"]"
```

### Testing OAuth Login

```bash
# Access the login page
echo "Login URL: https://$GATEWAY_FQDN/auth/login?provider=microsoft"
```

### Secret Rotation

Client secrets can be automatically rotated by redeploying:

```bash
# Redeploy with new secret expiration (default 365 days)
az deployment group create \
  --resource-group copilot-dev-rg \
  --template-file main.bicep \
  --parameters parameters.dev.json \
  --parameters oauthSecretExpirationDays=180
```

For more details, troubleshooting, and manual setup alternatives, see [ENTRA_APP_AUTOMATION.md](ENTRA_APP_AUTOMATION.md).

## Future Enhancements

- [ ] Add Private Endpoints for Key Vault, Cosmos DB, Service Bus (prod only)
- [ ] Configure VNet peering between staging and prod for hybrid scenarios
- [ ] Implement ExpressRoute for on-premises connectivity
- [ ] Add WAF (Web Application Firewall) in front of gateway
- [ ] Implement CI/CD pipeline for automated deployments
- [ ] Configure disaster recovery with cross-region failover

## References

- [Azure Container Apps Documentation](https://learn.microsoft.com/en-us/azure/container-apps/)
- [Bicep Language Reference](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/file)
- [Azure Security Best Practices](https://learn.microsoft.com/en-us/azure/security/fundamentals/security-principles)
