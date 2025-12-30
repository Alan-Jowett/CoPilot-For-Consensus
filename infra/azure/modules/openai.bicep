// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure OpenAI Service with GPT-4 and other model deployments'
metadata author = 'Copilot-for-Consensus Team'

@description('Azure region for the OpenAI resource')
param location string

@description('OpenAI account name (3-64 characters, lowercase alphanumeric and hyphens only)')
param accountName string

@description('SKU for Azure OpenAI Service (S0, S1, S2)')
param sku string = 'S0'

@description('Optional user-assigned managed identity resource ID for RBAC')
param identityResourceId string = ''

@description('Tags applied to all OpenAI resources')
param tags object = {}

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

@description('Custom subdomain name for token-based authentication')
param customSubdomainName string = ''

var normalizedAccountName = toLower(accountName)
// Use the first 8 chars of the account name for brevity
var projectName = take(normalizedAccountName, 8)
var normalizedSubdomain = customSubdomainName != '' ? toLower(customSubdomainName) : toLower('${projectName}-openai-${uniqueString(resourceGroup().id)}')
var deploymentName = 'gpt-4-deployment'

// Build identity object only when provided
var identityConfig = identityResourceId != '' ? {
  type: 'UserAssigned'
  userAssignedIdentities: {
    '${identityResourceId}': {}
  }
} : null

// Azure OpenAI Service account
resource openaiAccount 'Microsoft.CognitiveServices/accounts@2025-06-01' = {
  name: normalizedAccountName
  location: location
  kind: 'OpenAI'
  identity: identityConfig
  sku: {
    name: sku
  }
  tags: tags
  properties: {
    customSubDomainName: normalizedSubdomain
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    networkAcls: {
      defaultAction: 'Allow'
    }
  }
}

// GPT-4 Deployment
resource gpt4Deployment 'Microsoft.CognitiveServices/accounts/deployments@2025-09-01' = {
  parent: openaiAccount
  name: deploymentName
  sku: {
    name: 'Standard'
    capacity: 20
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4'
      version: '0613'
    }
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    scaleSettings: {
      scaleType: 'Standard'
      capacity: 20
    }
  }
}

// Outputs
output accountName string = openaiAccount.name
output accountId string = openaiAccount.id
output accountEndpoint string = openaiAccount.properties.endpoint
output customSubdomain string = openaiAccount.properties.customSubDomainName
output gpt4DeploymentId string = gpt4Deployment.id
output gpt4DeploymentName string = gpt4Deployment.name
output skuName string = sku
