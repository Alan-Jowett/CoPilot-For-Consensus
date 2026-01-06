<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Custom Domain Setup for Container Apps Gateway

This guide explains how to configure a custom domain (e.g., `copilot.example.com`) for the API Gateway in Azure Container Apps.

## Prerequisites

1. **Purchased Domain**: You must own a domain name (e.g., `example.com`)
2. **DNS Access**: Ability to create CNAME records in your domain's DNS settings
3. **Azure Subscription**: With permissions to deploy Container Apps and manage certificates

## Setup Steps

### 1. Create a Managed Certificate in Container Apps Environment

Before deploying with a custom domain, you need to create a managed certificate in the Container Apps environment:

```powershell
# Set variables
$resourceGroup = "cfc-dev-02-rg"
$containerEnvName = "copilot-dev-containerenv"
$customDomain = "copilot.example.com"

# Get the Container Apps environment resource ID
$envId = az containerapp env show `
  --name $containerEnvName `
  --resource-group $resourceGroup `
  --query id `
  --output tsv

# Create a managed certificate (requires DNS validation)
az containerapp env certificate create `
  --name $containerEnvName `
  --resource-group $resourceGroup `
  --certificate-name "${customDomain}-cert" `
  --hostname $customDomain `
  --validation-method CNAME

# Get the certificate resource ID for deployment
$certId = az containerapp env certificate list `
  --name $containerEnvName `
  --resource-group $resourceGroup `
  --query "[?properties.subjectName=='$customDomain'].id" `
  --output tsv
```

**Important**: You will receive a DNS TXT record that must be added to your domain for validation. The certificate creation will wait until validation completes.

### 2. Configure DNS CNAME Record

Add a CNAME record in your DNS provider pointing to the default Container Apps FQDN:

1. Get the default gateway FQDN from your deployment outputs
2. Create a CNAME record:
   - **Name**: `copilot` (or your subdomain)
   - **Type**: CNAME
   - **Value**: `<default-container-app-fqdn>` (e.g., `copilot-dev-gateway.happyriver-12345678.westus.azurecontainerapps.io`)
   - **TTL**: 3600 (or your DNS provider's default)

### 3. Deploy with Custom Domain Parameters

Update your deployment to include the custom domain parameters:

**Using parameter files** (`parameters.dev.json`, `parameters.staging.json`, `parameters.prod.json`):

```json
{
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "customDomainName": {
      "value": "copilot.example.com"
    },
    "customDomainCertificateId": {
      "value": "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.App/managedEnvironments/<env-name>/managedCertificates/<cert-name>"
    }
  }
}
```

**Using Azure CLI with inline parameters**:

```powershell
$customDomain = "copilot.example.com"
$certId = "<certificate-resource-id-from-step-1>"

az deployment group create `
  --resource-group cfc-dev-02-rg `
  --template-file infra/azure/main.bicep `
  --parameters infra/azure/parameters.dev.json `
  --parameters customDomainName=$customDomain customDomainCertificateId=$certId
```

### 4. Verify Custom Domain Configuration

After deployment completes:

1. **Check DNS propagation** (may take 5-60 minutes):
   ```powershell
   nslookup copilot.example.com
   ```

2. **Test HTTPS access**:
   ```powershell
   Invoke-WebRequest -UseBasicParsing https://copilot.example.com/health
   ```

3. **Verify certificate**:
   ```powershell
   # Should show your custom domain in Subject Alternative Name
   az containerapp show `
     --name copilot-dev-gateway `
     --resource-group cfc-dev-02-rg `
     --query properties.configuration.ingress.customDomains
   ```

## OAuth Configuration Update

If using GitHub OAuth or Entra ID authentication, update your OAuth application redirect URIs:

**GitHub OAuth**:
1. Go to GitHub → Settings → Developer settings → OAuth Apps → Your App
2. Update **Authorization callback URL** to: `https://copilot.example.com/ui/callback`

**Microsoft Entra ID**:
1. Go to Azure Portal → Microsoft Entra ID → App registrations → Your App
2. Update **Redirect URIs** to: `https://copilot.example.com/ui/callback`

The deployment automatically outputs the correct redirect URI based on your custom domain configuration.

## Troubleshooting

### Certificate Validation Fails

**Problem**: Managed certificate creation times out or fails validation.

**Solution**:
1. Verify the DNS TXT record for validation is correctly added
2. Wait for DNS propagation (use `nslookup -type=TXT _acme-challenge.copilot.example.com`)
3. Certificate creation can take 10-15 minutes after DNS validation

### CNAME Not Resolving

**Problem**: Custom domain doesn't resolve to Container App.

**Solution**:
1. Verify CNAME record points to the **default Container App FQDN** (not the custom domain)
2. Check DNS propagation: `nslookup copilot.example.com`
3. Wait 5-60 minutes for global DNS propagation

### SSL Certificate Errors

**Problem**: Browser shows SSL certificate errors.

**Solution**:
1. Verify the certificate was created successfully: `az containerapp env certificate list`
2. Ensure `customDomainCertificateId` matches the created certificate's resource ID
3. Check certificate subject name matches your domain: `az containerapp env certificate show`

### Deployment Fails with Custom Domain

**Problem**: Deployment fails when adding custom domain parameters.

**Solution**:
1. Ensure certificate is created and validated **before** deployment
2. Verify certificate resource ID is correct (use `az containerapp env certificate list`)
3. Check the certificate belongs to the same Container Apps environment

## Removing Custom Domain

To remove the custom domain configuration and revert to default Container Apps domain:

1. **Redeploy without custom domain parameters**:
   ```powershell
   az deployment group create `
     --resource-group cfc-dev-02-rg `
     --template-file infra/azure/main.bicep `
     --parameters infra/azure/parameters.dev.json `
     --parameters customDomainName='' customDomainCertificateId=''
   ```

2. **Delete the managed certificate** (optional):
   ```powershell
   az containerapp env certificate delete `
     --name copilot-dev-containerenv `
     --resource-group cfc-dev-02-rg `
     --certificate-name "${customDomain}-cert"
   ```

3. **Remove DNS CNAME record** from your DNS provider

## Cost Considerations

- **Managed Certificates**: Free with Azure Container Apps
- **Custom Domains**: No additional cost
- **DNS Hosting**: Cost depends on your DNS provider

## Security Recommendations

1. **Always use HTTPS**: Custom domains automatically enforce HTTPS with managed certificates
2. **Monitor certificate renewal**: Azure automatically renews managed certificates 45 days before expiration
3. **Update OAuth redirect URIs**: Ensure all OAuth applications use the custom domain
4. **DNS Security**: Consider enabling DNSSEC if your DNS provider supports it

## References

- [Azure Container Apps Custom Domains](https://learn.microsoft.com/azure/container-apps/custom-domains-managed-certificates)
- [Managed Certificates in Container Apps](https://learn.microsoft.com/azure/container-apps/custom-domains-managed-certificates#managed-certificates)
- [DNS Configuration for Azure Services](https://learn.microsoft.com/azure/dns/dns-overview)
