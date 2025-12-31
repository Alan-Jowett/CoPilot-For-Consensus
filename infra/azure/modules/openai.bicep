// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure OpenAI Service with GPT-4o and related model deployments'
metadata author = 'Copilot-for-Consensus Team'

@description('Azure region for the OpenAI resource')
param location string

@description('OpenAI account name (3-64 characters, lowercase alphanumeric and hyphens only)')
param accountName string

@allowed(['S0'])
@description('SKU for Azure OpenAI Service (currently only S0 is supported)')
param sku string = 'S0'

@allowed([
  '2024-05-13'
  '2024-08-06'
  '2024-11-20'
])
@description('Model version to deploy for gpt-4o (2024-11-20 is latest GA)')
param modelVersion string = '2024-11-20'

@allowed(['Standard', 'GlobalStandard'])
@description('Deployment SKU (GlobalStandard for global load balancing)')
param deploymentSku string = 'GlobalStandard'

@minValue(1)
@maxValue(1000)
@description('Capacity (units) for the GPT-4o deployment. Represents Tokens-Per-Minute throughput in thousands.')
param deploymentCapacity int = 10

@allowed(['Allow', 'Deny'])
@description('Default action for network ACLs when public network is enabled')
param networkDefaultAction string = 'Deny'

@description('Optional user-assigned managed identity resource ID for RBAC')
param identityResourceId string = ''

@description('List of IPv4 CIDR ranges allowed to reach the OpenAI endpoint')
param ipRules array = []

@description('Tags applied to all OpenAI resources')
param tags object = {}

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

@description('Custom subdomain name for token-based authentication')
param customSubdomainName string = ''

@description('Whether to deploy a text embedding model (model selected via embeddingModelName parameter)')
param deployEmbeddingModel bool = true

@allowed(['text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large'])
@description('Embedding model to deploy')
param embeddingModelName string = 'text-embedding-ada-002'

@minValue(1)
@maxValue(1000)
@description('Capacity (units) for the embedding deployment')
param embeddingDeploymentCapacity int = 10

// Map embedding model names to their API versions
var embeddingModelVersions = {
  'text-embedding-ada-002': '2'
  'text-embedding-3-small': '1'
  'text-embedding-3-large': '1'
}

var normalizedAccountName = toLower(accountName)
// Use the first 8 chars of the account name for brevity
var projectName = take(normalizedAccountName, 8)
var normalizedSubdomain = customSubdomainName != '' ? toLower(customSubdomainName) : toLower('${projectName}-openai-${uniqueString(resourceGroup().id)}')
var gpt4DeploymentName = 'gpt-4o-deployment'
var embeddingDeploymentName = 'embedding-deployment'

// Azure OpenAI Service account
resource openaiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: normalizedAccountName
  location: location
  kind: 'OpenAI'
  identity: identityResourceId != '' ? {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  } : null
  sku: {
    name: sku
  }
  tags: tags
  properties: {
    customSubDomainName: normalizedSubdomain
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: {
      defaultAction: enablePublicNetworkAccess ? networkDefaultAction : 'Deny'
      ipRules: [for cidr in ipRules: { value: cidr }]
    }
  }
}

// GPT-4o Deployment
resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = {
  parent: openaiAccount
  name: gpt4DeploymentName
  sku: {
    name: deploymentSku
    capacity: deploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: modelVersion
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
}

// Embedding Model Deployment (text-embedding-ada-002 or text-embedding-3-*)
resource embeddingDeployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = if (deployEmbeddingModel) {
  parent: openaiAccount
  name: embeddingDeploymentName
  sku: {
    name: deploymentSku
    capacity: embeddingDeploymentCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersions[embeddingModelName]
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  dependsOn: [gpt4Deployment]  // Deploy sequentially to avoid quota conflicts
}

// Outputs
@description('OpenAI account name')
output accountName string = openaiAccount.name
@description('OpenAI account resource ID')
output accountId string = openaiAccount.id
@description('OpenAI account endpoint URL')
output accountEndpoint string = openaiAccount.properties.endpoint
@description('Custom subdomain for token-based auth')
output customSubdomain string = openaiAccount.properties.customSubDomainName
@description('GPT-4o deployment resource ID')
output gpt4DeploymentId string = gpt4Deployment.id
@description('GPT-4o deployment name')
output gpt4DeploymentName string = gpt4Deployment.name
@description('Embedding deployment resource ID')
output embeddingDeploymentId string = deployEmbeddingModel ? embeddingDeployment.id : ''
@description('Embedding deployment name')
output embeddingDeploymentName string = deployEmbeddingModel ? embeddingDeployment.name : ''
@description('Configured SKU for OpenAI account')
output skuName string = sku
