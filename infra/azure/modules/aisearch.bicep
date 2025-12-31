// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure AI Search service for vector store'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for the resource')
param location string

@description('Azure AI Search service name (must be globally unique and lowercase)')
param serviceName string

@description('SKU for Azure AI Search (free, basic, standard, standard2, standard3, storage_optimized_l1, storage_optimized_l2)')
@allowed(['free', 'basic', 'standard', 'standard2', 'standard3', 'storage_optimized_l1', 'storage_optimized_l2'])
param sku string = 'basic'

@description('User-assigned managed identity resource ID for RBAC')
param identityResourceId string

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

@description('Whether to enable semantic search capability')
param enableSemanticSearch bool = false

@description('Resource tags')
param tags object = {}

// Azure AI Search service
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: serviceName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    encryptionWithCmk: {
      enforcement: 'Unspecified'
    }
    semanticSearch: enableSemanticSearch ? 'free' : 'disabled'
  }
}

// Get API keys for authentication (note: admin keys are secrets and should be stored in Key Vault)
resource searchServiceKeys 'Microsoft.Search/searchServices/listAdminKeys@2024-06-01-preview' = {
  parent: searchService
  name: 'default'
}

// Outputs
@description('Azure AI Search endpoint URL')
output endpoint string = 'https://${searchService.name}.search.windows.net'

@description('Azure AI Search service name')
output serviceName string = searchService.name

@description('Azure AI Search service resource ID')
output serviceId string = searchService.id

@secure()
@description('Primary admin API key (secure - store in Key Vault, do not expose in plain outputs)')
output adminApiKey string = searchServiceKeys.listAdminKeys().primaryKey

@secure()
@description('Query API key (lower-privilege key for client applications, store in Key Vault)')
output queryApiKey string = searchServiceKeys.listAdminKeys().secondaryKey
