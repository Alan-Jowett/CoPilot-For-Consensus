// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Virtual Network for Container Apps integration'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for resources')
param location string

@description('Project name')
param projectName string

@description('Environment name')
param environment string

@description('VNet address space (CIDR notation)')
param vnetAddressSpace string = '10.0.0.0/16'

@description('Container Apps subnet address prefix (CIDR notation)')
param subnetAddressPrefix string = '10.0.0.0/23'

param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var vnetName = '${projectPrefix}-vnet-${environment}-${take(uniqueSuffix, 5)}'
var containerAppsSubnetName = '${projectPrefix}-ca-subnet-${environment}'

// Virtual Network
resource vnet 'Microsoft.Network/virtualNetworks@2024-01-01' = {
  name: vnetName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressSpace
      ]
    }
    subnets: [
      {
        name: containerAppsSubnetName
        properties: {
          addressPrefix: subnetAddressPrefix
          delegations: [
            {
              name: 'Microsoft.App.environments'
              properties: {
                serviceName: 'Microsoft.App/environments'
              }
            }
          ]
        }
      }
    ]
  }
}

// Outputs
@description('Virtual Network ID')
output vnetId string = vnet.id

@description('Container Apps Subnet ID')
output containerAppsSubnetId string = '${vnet.id}/subnets/${containerAppsSubnetName}'

@description('Virtual Network Name')
output vnetName string = vnet.name
