<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# VM-Based Gateway Architecture

## Overview

This document describes the VM-based gateway architecture introduced to eliminate Azure Load Balancer costs while maintaining all Container Apps functionality including scale-to-zero.

## Problem Statement

The previous architecture used Azure Container Apps with **external ingress enabled** on the gateway service. This configuration forced Azure to create a **Standard Load Balancer**, which incurs costs 24/7 (~$18+/month) even when all microservices are scaled to zero.

Since the system consists of nine demand-start microservices (all scale-to-zero capable) and a single gateway that routes traffic internally, the load balancer was the **largest daily cost** of the deployment even when idle.

## Solution: VM-Based Gateway

The new architecture moves the gateway to a small Linux VM running nginx, while keeping all microservices on Azure Container Apps:

- **Gateway VM**: Small B1ls VM (~$3-5/month) running nginx as reverse proxy
- **All Container Apps**: Internal-only ingress (no external ingress, no Load Balancer)
- **Scale-to-Zero**: Preserved via KEDA HTTP triggers on internal endpoints
- **Cost Savings**: ~$13-15/month reduction (75-83% savings on gateway costs)

## Architecture Diagram

```
Internet
    │
    ▼
┌─────────────────┐
│  Gateway VM     │  Standard_B1ls (~$3-5/mo)
│  (nginx)        │  Public IP + NSG
│  Port 80/443    │
└────────┬────────┘
         │
         │ VNet (10.0.0.0/16)
         │
         ▼
┌─────────────────────────────────────────────────────────┐
│  Container Apps Environment (Internal Ingress Only)     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │ reporting│  │ ingestion│  │ auth     │ ...         │
│  │ :443     │  │ :443     │  │ :443     │             │
│  └──────────┘  └──────────┘  └──────────┘             │
│                                                         │
│  Scale from 0 with KEDA HTTP + Service Bus triggers    │
└─────────────────────────────────────────────────────────┘
```

## Key Features

### ✅ Eliminates Load Balancer Costs

- No external ingress on Container Apps = No Load Balancer created
- VM costs $3-5/month vs Load Balancer $18+/month
- 75-83% cost reduction for gateway infrastructure

### ✅ Preserves Scale-to-Zero

- All Container Apps use internal-only ingress
- KEDA HTTP triggers work with internal endpoints
- Traffic from VM → ACA triggers scale-up exactly as before
- Services scale from 0 → N on demand

### ✅ Maintains Existing Architecture

- All 9 microservices remain on Container Apps
- Service mesh, autoscaling, and revision management unchanged
- Same routing patterns and API endpoints
- No application code changes required

### ✅ Security Benefits

- Reduced attack surface (single public entry point)
- NSG controls inbound/outbound traffic
- Internal ACA endpoints not directly accessible
- Simplified network security configuration

## Deployment Configuration

### VNet Subnets

The VNet is configured with three subnets:

| Subnet | CIDR | Purpose |
|--------|------|---------|
| Container Apps | 10.0.0.0/23 | ACA environment (requires /23 minimum) |
| Private Endpoints | 10.0.2.0/24 | Private Link endpoints (optional) |
| **Gateway VM** | **10.0.3.0/24** | **VM gateway subnet (new)** |

### VM Configuration

**Default VM Size**: `Standard_B1ls` (1 vCPU, 0.5 GB RAM)
- Recommended for dev/staging environments
- Cost: ~$3-5/month
- Sufficient for gateway workload (nginx reverse proxy)

**Production VM Size**: `Standard_B1s` or `Standard_B2s`
- More resources for higher traffic
- Cost: ~$7-10/month (B1s) or ~$15-20/month (B2s)
- Still significantly cheaper than Load Balancer

### Cloud-Init Configuration

The VM is automatically configured via cloud-init:

1. **Package Installation**: nginx, curl
2. **Nginx Configuration**: Reverse proxy rules for all 9 services
3. **Service FQDNs**: Injected at deployment time from Container Apps outputs
4. **Automatic Start**: nginx enabled and started on boot

### Nginx Routing

The VM nginx configuration includes:

```nginx
# Example routing for reporting service
location /reporting/ {
  proxy_pass https://reporting-internal.fqdn/;
  proxy_set_header Host reporting-internal.fqdn;
  proxy_ssl_server_name on;
  proxy_ssl_verify off;
}
```

Similar routes exist for all services:
- `/reporting/` → reporting service
- `/ingestion/` → ingestion service
- `/auth/` → auth service
- `/ui/` → UI service
- `/orchestrator/`, `/summarization/`, `/parsing/`, `/chunking/`, `/embedding/`

### Network Security Group (NSG)

The VM has an NSG with the following rules:

**Inbound**:
- Port 80 (HTTP) - Allow from Internet
- Port 443 (HTTPS) - Allow from Internet
- Port 22 (SSH) - Allow from Internet (for admin access)

**Outbound**:
- All ports - Allow to Container Apps subnet
- All ports - Allow to Internet (for package updates)

## Deployment Parameters

### Required Parameters

Add these parameters to your `parameters.dev.json`, `parameters.staging.json`, and `parameters.prod.json`:

```json
{
  "gatewaySubnetPrefix": {
    "value": "10.0.3.0/24"
  },
  "deployGatewayVm": {
    "value": true
  },
  "gatewayVmSize": {
    "value": "Standard_B1ls"
  },
  "gatewayVmAdminUsername": {
    "value": "azureuser"
  },
  "gatewayVmSshPublicKey": {
    "value": "ssh-rsa YOUR-PUBLIC-SSH-KEY-HERE"
  },
  "gatewayVmEnablePublicIp": {
    "value": true
  }
}
```

### Generating SSH Key

If you don't have an SSH key, generate one:

```bash
# Generate new SSH key pair
ssh-keygen -t rsa -b 4096 -f ~/.ssh/azure-gateway-vm -C "gateway-vm-admin"

# Display public key (copy this to parameters file)
cat ~/.ssh/azure-gateway-vm.pub
```

## Deployment

### Full Deployment

```bash
# Deploy environment with VM gateway
cd infra/azure
./deploy.env.sh -g rg-env-dev -e dev
```

### Deploy Without VM Gateway (Optional)

To deploy with traditional external ingress (not recommended due to costs):

```json
{
  "deployGatewayVm": {
    "value": false
  }
}
```

This will deploy Container Apps gateway with external ingress and create a Load Balancer.

## Accessing the Deployment

### Gateway URL

After deployment, the gateway is accessible via:

**With VM Gateway**:
```
http://<vm-public-fqdn>
http://<vm-public-fqdn>/health  # Health check
http://<vm-public-fqdn>/reporting/
http://<vm-public-fqdn>/ui/
```

**VM FQDN Format**: `{projectPrefix}-gw-{environment}-{uniqueSuffix}.{region}.cloudapp.azure.com`

Example: `copilot-gw-dev-abc12.westus.cloudapp.azure.com`

### Deployment Outputs

The deployment provides these outputs:

```bash
# Get gateway URL
az deployment group show \
  --resource-group rg-env-dev \
  --name main \
  --query properties.outputs.gatewayVmPublicFqdn.value -o tsv

# Get health endpoint
az deployment group show \
  --resource-group rg-env-dev \
  --name main \
  --query properties.outputs.gatewayVmHealthEndpoint.value -o tsv
```

### SSH Access

Connect to the VM for troubleshooting:

```bash
# Get VM public FQDN
VM_FQDN=$(az deployment group show \
  --resource-group rg-env-dev \
  --name main \
  --query properties.outputs.gatewayVmPublicFqdn.value -o tsv)

# SSH to VM
ssh -i ~/.ssh/azure-gateway-vm azureuser@$VM_FQDN
```

## Validation

### Check Services

```bash
# Health check
curl http://<vm-fqdn>/health

# Check reporting service
curl http://<vm-fqdn>/reporting/health

# Check UI
curl -I http://<vm-fqdn>/ui/

# Test scale-from-zero
# Service should be at 0 replicas initially
az containerapp replica list \
  --resource-group rg-env-dev \
  --name copilot-reporting-dev \
  --query "length([])"

# Make request (triggers scale-up)
curl http://<vm-fqdn>/reporting/api/reports

# Check replicas again (should be > 0)
az containerapp replica list \
  --resource-group rg-env-dev \
  --name copilot-reporting-dev \
  --query "length([])"
```

### Verify No Load Balancer

```bash
# List load balancers in resource group
# Should return empty list with VM gateway
az network lb list \
  --resource-group rg-env-dev \
  --query "[].name" -o table
```

With VM gateway: No load balancers should be listed.

Without VM gateway (external ingress): You'll see a load balancer for the Container Apps environment.

## Troubleshooting

### VM Not Responding

1. Check VM status:
   ```bash
   az vm get-instance-view \
     --resource-group rg-env-dev \
     --name copilot-gw-vm-dev \
     --query instanceView.statuses
   ```

2. Check NSG rules:
   ```bash
   az network nsg show \
     --resource-group rg-env-dev \
     --name copilot-gw-vm-dev-nsg \
     --query securityRules
   ```

3. SSH to VM and check nginx:
   ```bash
   ssh azureuser@<vm-fqdn>
   sudo systemctl status nginx
   sudo nginx -t
   sudo tail -f /var/log/nginx/access.log
   sudo tail -f /var/log/nginx/error.log
   ```

### Services Not Scaling

1. Check Container App scale configuration:
   ```bash
   az containerapp show \
     --resource-group rg-env-dev \
     --name copilot-reporting-dev \
     --query properties.template.scale
   ```

2. Verify ingress is internal:
   ```bash
   az containerapp show \
     --resource-group rg-env-dev \
     --name copilot-reporting-dev \
     --query properties.configuration.ingress.external
   ```
   Should return `false`.

3. Check nginx routing from VM:
   ```bash
   ssh azureuser@<vm-fqdn>
   curl -k https://<service-internal-fqdn>/health
   ```

### Cloud-Init Failures

Check cloud-init logs:
```bash
ssh azureuser@<vm-fqdn>
sudo cat /var/log/cloud-init.log
sudo cat /var/log/cloud-init-output.log
```

### Update Nginx Configuration

If you need to modify nginx configuration:
```bash
ssh azureuser@<vm-fqdn>
sudo nano /etc/nginx/sites-available/copilot-gateway
sudo nginx -t
sudo systemctl reload nginx
```

## Cost Comparison

### Before (External Ingress with Load Balancer)

| Resource | Monthly Cost |
|----------|--------------|
| Standard Load Balancer | ~$18 |
| Container Apps (scaled to 0) | $0 |
| **Total** | **~$18** |

### After (VM-Based Gateway)

| Resource | Monthly Cost |
|----------|--------------|
| Standard_B1ls VM | ~$3-5 |
| VM Public IP (Standard) | ~$3 |
| Container Apps (scaled to 0) | $0 |
| **Total** | **~$6-8** |

**Savings**: ~$10-15/month (55-83% reduction)

## Migration Guide

### From External Ingress to VM Gateway

1. **Update parameter files**: Add VM gateway parameters
2. **Generate SSH key**: Create and configure SSH key
3. **Deploy updated template**: Run `deploy.env.sh`
4. **Update DNS/endpoints**: Point to new VM FQDN
5. **Verify routing**: Test all service endpoints
6. **Delete old gateway** (optional): If gateway Container App no longer needed

### Rollback to External Ingress

If needed, you can rollback by setting:

```json
{
  "deployGatewayVm": {
    "value": false
  }
}
```

And updating the gateway Container App ingress to `external: true` in `containerapps.bicep`.

## Best Practices

1. **SSH Key Management**: Store SSH private key securely (Key Vault, GitHub Secrets)
2. **VM Monitoring**: Enable Azure Monitor for VM metrics
3. **Backup**: Snapshot the nginx configuration
4. **Updates**: Regularly update VM packages (`apt update && apt upgrade`)
5. **SSL/TLS**: Consider adding SSL certificates for HTTPS support
6. **Scaling**: For high traffic, use B1s/B2s or add multiple VMs with Load Balancer

## Future Enhancements

- **HTTPS Support**: Add SSL certificates via Let's Encrypt
- **Multiple VMs**: Deploy multiple VMs for HA with Azure Load Balancer
- **CDN Integration**: Add Azure CDN for static assets
- **WAF**: Add Web Application Firewall for security
- **Custom Domain**: Configure custom domain with DNS

## References

- [Container Apps Scale-to-Zero Configuration](SCALE_TO_ZERO_CONFIGURATION.md)
- [Azure Deployment Guide](README.md)
- [Bicep Architecture](BICEP_ARCHITECTURE.md)
- [Cost Optimization](OPENAI_CONFIGURATION.md#cost-optimization)
