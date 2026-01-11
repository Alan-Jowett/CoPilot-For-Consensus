// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure DNS Zone and CNAME records for custom domains'
metadata author = 'Copilot-for-Consensus Team'

@description('Azure DNS Zone name (e.g., example.com)')
param dnsZoneName string

@description('Custom domain name for the gateway (e.g., copilot.example.com)')
param customDomainName string

@description('Gateway FQDN from Container Apps (e.g., copilot-dev-gateway.happyriver-12345678.westus.azurecontainerapps.io)')
param gatewayFqdn string

@description('Resource tags')
param tags object = {}

// Extract subdomain name from custom domain with validation
// e.g., "copilot.example.com" with zone "example.com" → "copilot"
var subdomainName = endsWith(customDomainName, dnsZoneName) && length(customDomainName) > length(dnsZoneName) + 1
  ? take(customDomainName, length(customDomainName) - length(dnsZoneName) - 1)
  : customDomainName

// Create or reference existing DNS Zone
resource dnsZone 'Microsoft.Network/dnsZones@2018-05-01' = {
  name: dnsZoneName
  location: 'global'
  tags: tags
}

// Create CNAME record pointing to Container Apps gateway
resource cnameRecord 'Microsoft.Network/dnsZones/CNAME@2018-05-01' = {
  parent: dnsZone
  name: subdomainName
  properties: {
    TTL: 3600
    CNAMERecord: {
      cname: gatewayFqdn
    }
  }
}

// Outputs
@description('DNS Zone resource ID')
output dnsZoneId string = dnsZone.id

@description('CNAME record resource ID')
output cnameRecordId string = cnameRecord.id

@description('FQDN of the custom domain')
output customDomainFqdn string = customDomainName

@description('Target CNAME value (Container Apps gateway FQDN)')
output cnameTarget string = gatewayFqdn
