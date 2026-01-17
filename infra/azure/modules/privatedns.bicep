// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Private DNS Zones and link them to a VNet'
metadata author = 'Copilot-for-Consensus Team'

@description('Location (used for resource group reference, DNS zones are global)')
param location string

@description('Virtual Network ID to link the private DNS zones to')
param vnetId string

@description('Resource tags')
param tags object = {}

// Define Private DNS Zone names for Azure services
// Reference: https://learn.microsoft.com/en-us/azure/private-link/private-endpoint-dns
// Note: Blob storage DNS zone uses environment().suffixes.storage for cloud-specific suffix
// OpenAI Private Endpoints are not currently created (OpenAI is in Core RG without VNet)
var privateDnsZoneNames = {
  keyVault: 'privatelink.vaultcore.azure.net'
  cosmosDb: 'privatelink.documents.azure.com'
  cosmosDbSql: 'privatelink.documents.azure.com'
  blob: 'privatelink.blob.${environment().suffixes.storage}'  // Resolves to 'core.windows.net' in Azure Commercial
  serviceBus: 'privatelink.servicebus.windows.net'
  aiSearch: 'privatelink.search.windows.net'
}

// Create Private DNS Zones
resource keyVaultDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneNames.keyVault
  location: 'global'
  tags: tags
}

resource cosmosDbDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneNames.cosmosDb
  location: 'global'
  tags: tags
}

resource blobDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneNames.blob
  location: 'global'
  tags: tags
}

resource serviceBusDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneNames.serviceBus
  location: 'global'
  tags: tags
}

resource aiSearchDnsZone 'Microsoft.Network/privateDnsZones@2020-06-01' = {
  name: privateDnsZoneNames.aiSearch
  location: 'global'
  tags: tags
}

// Link Private DNS Zones to VNet
resource keyVaultDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: keyVaultDnsZone
  name: 'keyvault-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource cosmosDbDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: cosmosDbDnsZone
  name: 'cosmosdb-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource blobDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: blobDnsZone
  name: 'blob-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource serviceBusDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: serviceBusDnsZone
  name: 'servicebus-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

resource aiSearchDnsZoneLink 'Microsoft.Network/privateDnsZones/virtualNetworkLinks@2020-06-01' = {
  parent: aiSearchDnsZone
  name: 'aisearch-link'
  location: 'global'
  properties: {
    registrationEnabled: false
    virtualNetwork: {
      id: vnetId
    }
  }
}

// Outputs
@description('Private DNS Zone resource IDs keyed by service type')
output privateDnsZoneIds object = {
  keyVault: keyVaultDnsZone.id
  cosmosDb: cosmosDbDnsZone.id
  blob: blobDnsZone.id
  serviceBus: serviceBusDnsZone.id
  aiSearch: aiSearchDnsZone.id
}

@description('Private DNS Zone names keyed by service type')
output privateDnsZoneNames object = privateDnsZoneNames
