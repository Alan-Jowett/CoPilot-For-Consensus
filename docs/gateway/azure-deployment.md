<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Azure API Management Deployment

## Overview

Deploy Copilot-for-Consensus to Azure using API Management (APIM) for enterprise-grade API gateway features including developer portal, analytics, rate limiting, and Azure AD integration.

## Quick Start

```bash
# Generate Azure configuration
cd infra/gateway
./generate_gateway_config.py --provider azure --output ../../dist/gateway/azure

# Deploy to Azure
cd ../../dist/gateway/azure
az deployment group create \
  --resource-group <your-rg> \
  --template-file azure-apim-template.json \
  --parameters azure-apim-parameters.json
```

## Generated Files

| File | Description |
|------|-------------|
| `azure-apim-template.json` | ARM template for APIM service and API |
| `azure-apim-parameters.json` | Deployment parameters (customize before deploying) |
| `azure-apim.bicep` | Bicep template (alternative IaC format) |
| `policies/cors-policy.xml` | CORS policy configuration |
| `policies/rate-limit-policy.xml` | Rate limiting policy |
| `policies/jwt-validation-policy.xml` | JWT authentication policy |

## Prerequisites

- Azure CLI installed (`az`)
- Azure subscription with Owner or Contributor role
- Resource group created
- Backend services deployed to Azure (App Service, Container Apps, or AKS)

## Configuration

### 1. Customize Parameters

Edit `azure-apim-parameters.json`:

```json
{
  "parameters": {
    "apimServiceName": {
      "value": "copilot-apim-<unique-suffix>"
    },
    "publisherEmail": {
      "value": "your-email@example.com"
    },
    "publisherName": {
      "value": "Your Organization"
    },
    "backendReportingUrl": {
      "value": "https://copilot-reporting.azurewebsites.net"
    },
    "backendIngestionUrl": {
      "value": "https://copilot-ingestion.azurewebsites.net"
    },
    "backendAuthUrl": {
      "value": "https://copilot-auth.azurewebsites.net"
    }
  }
}
```

### 2. Validate Template

```bash
az deployment group validate \
  --resource-group <your-rg> \
  --template-file azure-apim-template.json \
  --parameters azure-apim-parameters.json
```

### 3. Deploy

```bash
az deployment group create \
  --resource-group <your-rg> \
  --template-file azure-apim-template.json \
  --parameters azure-apim-parameters.json \
  --name copilot-apim-deployment
```

**Note**: APIM provisioning takes 30-45 minutes.

### 4. Get Gateway URL

```bash
az apim show \
  --resource-group <your-rg> \
  --name <apimServiceName> \
  --query gatewayUrl -o tsv
```

### 5. Test

```bash
GATEWAY_URL=$(az apim show --resource-group <your-rg> --name <apimServiceName> --query gatewayUrl -o tsv)
curl $GATEWAY_URL/reporting/health
```

## Pricing Tiers

| Tier | Best For | Cost (Approx) |
|------|----------|---------------|
| Developer | Development, testing | ~$50/month |
| Basic | Small production | ~$200/month |
| Standard | Medium production | ~$800/month |
| Premium | Enterprise, multi-region | ~$3000/month |

See [Azure APIM Pricing](https://azure.microsoft.com/pricing/details/api-management/) for details.

## Security

### Authentication

Configure JWT validation in the APIM policy:

1. Navigate to Azure Portal → API Management → APIs
2. Select your API → Inbound processing → Add policy
3. Use the generated `policies/jwt-validation-policy.xml` as a template
4. Update issuer and audience to match your auth service

### Network Security

For production:

1. Place APIM in a Virtual Network
2. Use Private Endpoints for backend services
3. Enable Application Gateway with WAF for additional protection
4. Configure NSG rules to restrict access

### Managed Identity

Enable Managed Identity for APIM to access backend services:

```bash
az apim update \
  --resource-group <your-rg> \
  --name <apimServiceName> \
  --set identity.type=SystemAssigned
```

## Monitoring

### Enable Application Insights

```bash
az apim update \
  --resource-group <your-rg> \
  --name <apimServiceName> \
  --set diagnosticsSettings[0].enabled=true \
  --set diagnosticsSettings[0].logger.id=/subscriptions/<sub-id>/resourceGroups/<rg>/providers/Microsoft.Insights/components/<app-insights-name>
```

### View Metrics

- Navigate to Azure Portal → API Management → Analytics
- View request counts, latency, errors
- Set up alerts for critical thresholds

### Access Logs

Configure diagnostic settings to send logs to:
- Storage account (recommended)
- Event Hub
- Log Analytics workspace (optional/legacy)

## Custom Domain

### 1. Add Custom Domain

```bash
az apim update \
  --resource-group <your-rg> \
  --name <apimServiceName> \
  --set hostnameConfigurations[0].hostName=api.yourdomain.com \
  --set hostnameConfigurations[0].type=Proxy \
  --set hostnameConfigurations[0].certificateSource=Managed
```

### 2. Update DNS

Create CNAME record:
```
api.yourdomain.com -> <apimServiceName>.azure-api.net
```

## Developer Portal

APIM includes a developer portal at:
```
https://<apimServiceName>.developer.azure-api.net
```

Features:
- API documentation (from OpenAPI spec)
- Interactive API console
- Subscription management
- Code samples in multiple languages

## Cost Optimization

1. **Use Developer tier** for non-production environments
2. **Enable autoscaling** for Standard/Premium tiers
3. **Configure caching** to reduce backend calls
4. **Set up rate limiting** to prevent abuse
5. **Monitor and analyze** usage patterns

## Troubleshooting

### APIM Provisioning Failed

Check activity log:
```bash
az monitor activity-log list \
  --resource-group <your-rg> \
  --max-events 10
```

### Backend Service Not Reachable

Test backend connectivity from APIM:
```bash
# Check backend health via APIM test console
az apim api operation show \
  --resource-group <your-rg> \
  --service-name <apimServiceName> \
  --api-id <api-id> \
  --operation-id <operation-id>
```

### Policy Errors

View policy errors in logs:
1. Azure Portal → API Management → APIs
2. Select API → Test
3. Send test request and view trace

## Bicep Deployment (Alternative)

Using Bicep instead of ARM:

```bash
# Deploy with Bicep
az deployment group create \
  --resource-group <your-rg> \
  --template-file azure-apim.bicep \
  --parameters azure-apim-parameters.json
```

## Multi-Region Setup

For high availability:

1. Use Premium tier
2. Add additional regions:
   ```bash
   az apim update \
     --resource-group <your-rg> \
     --name <apimServiceName> \
     --add additionalLocations location=westeurope sku.name=Premium sku.capacity=1
   ```
3. Configure Traffic Manager for global load balancing

## Resources

- [Azure API Management Documentation](https://docs.microsoft.com/azure/api-management/)
- [APIM Policies Reference](https://docs.microsoft.com/azure/api-management/api-management-policies)
- [OpenAPI Specification](../../infra/gateway/openapi.yaml)
- [Generated Configuration](../../dist/gateway/azure/)

## Next Steps

- Configure custom policies for your endpoints
- Set up Azure AD authentication
- Enable Application Insights for detailed telemetry
- Create subscriptions for API consumers
- Customize developer portal branding
