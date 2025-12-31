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

@description('Principal ID of embedding service identity (for RBAC role assignment)')
param embeddingServicePrincipalId string

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

@description('Whether to enable semantic search capability')
param enableSemanticSearch bool = false

@description('Resource tags')
param tags object = {}

// Azure AI Search service (authentication via managed identities/RBAC only)
resource searchService 'Microsoft.Search/searchServices@2024-06-01-preview' = {
  name: serviceName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    disableLocalAuth: true  // Force RBAC-only authentication, disable API keys
    encryptionWithCmk: {
      enforcement: 'Unspecified'
    }
    semanticSearch: enableSemanticSearch ? 'free' : 'disabled'
  }
}

// Role: Search Index Data Contributor (allows read/write to search indexes)
// Role ID reference: https://learn.microsoft.com/en-us/azure/role-based-access-control/built-in-roles#search-index-data-contributor
var searchIndexDataContributorRoleId = '8ebe5a00-799e-43f5-93ac-243d3dce84a7'

// Assign embedding service identity the "Search Index Data Contributor" role
resource embeddingServiceRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, embeddingServicePrincipalId, searchIndexDataContributorRoleId)
  scope: searchService
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributorRoleId)
    principalId: embeddingServicePrincipalId
    principalType: 'ServicePrincipal'
  }
}

// Outputs
@description('Azure AI Search endpoint URL')
output endpoint string = 'https://${searchService.name}.search.windows.net'

@description('Azure AI Search service name')
output serviceName string = searchService.name

@description('Azure AI Search service resource ID')
output serviceId string = searchService.id
