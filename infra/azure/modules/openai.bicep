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

var normalizedAccountName = toLower(accountName)
// Use the first 8 chars of the account name for brevity
var projectName = take(normalizedAccountName, 8)
var normalizedSubdomain = customSubdomainName != '' ? toLower(customSubdomainName) : toLower('${projectName}-openai-${uniqueString(resourceGroup().id)}')
var deploymentName = 'gpt-4o-deployment'

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
  name: deploymentName
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
@description('Configured SKU for OpenAI account')
output skuName string = sku
