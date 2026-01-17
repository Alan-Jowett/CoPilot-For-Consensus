// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Azure Private Endpoint for a service'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for the private endpoint')
param location string

@description('Name for the private endpoint')
param privateEndpointName string

@description('Subnet ID where the private endpoint will be created')
param subnetId string

@description('Resource ID of the service to create private endpoint for')
param serviceResourceId string

@description('Group IDs for the private endpoint (e.g., ["vault"] for Key Vault, ["Sql"] for Cosmos DB)')
param groupIds array

@description('Private DNS Zone IDs to link with this private endpoint')
param privateDnsZoneIds array = []

@description('Resource tags')
param tags object = {}

// Private Endpoint
resource privateEndpoint 'Microsoft.Network/privateEndpoints@2024-01-01' = {
  name: privateEndpointName
  location: location
  tags: tags
  properties: {
    subnet: {
      id: subnetId
    }
    privateLinkServiceConnections: [
      {
        name: privateEndpointName
        properties: {
          privateLinkServiceId: serviceResourceId
          groupIds: groupIds
        }
      }
    ]
  }
}

// Private DNS Zone Group (links private endpoint to DNS zones)
resource privateDnsZoneGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2024-01-01' = if (length(privateDnsZoneIds) > 0) {
  parent: privateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      for (zoneId, i) in privateDnsZoneIds: {
        name: 'config${i}'
        properties: {
          privateDnsZoneId: zoneId
        }
      }
    ]
  }
}

// Outputs
@description('Private Endpoint resource ID')
output privateEndpointId string = privateEndpoint.id

@description('Private Endpoint name')
output privateEndpointName string = privateEndpoint.name

@description('Private IP address assigned to the private endpoint')
output privateIpAddress string = privateEndpoint.properties.customDnsConfigs[0].ipAddresses[0]
