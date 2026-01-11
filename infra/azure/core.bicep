// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Core infrastructure template for long-lived Azure OpenAI and Key Vault resources'
metadata author = 'Copilot-for-Consensus Team'

@minLength(3)
@maxLength(15)
param projectName string = 'copilot'

@allowed(['dev', 'staging', 'prod'])
param environment string = 'dev'

param location string = 'westus'

// Azure OpenAI accounts only support S0 (S1/S2 apply to other Cognitive Services resources, not OpenAI)
@allowed(['S0'])
@description('SKU for Azure OpenAI Service. Azure OpenAI currently only supports the S0 SKU; other SKUs are not valid for this resource type.')
param azureOpenAISku string = 'S0'

@allowed(['Standard', 'GlobalStandard'])
@description('Deployment SKU for Azure OpenAI (GlobalStandard recommended for production)')
param azureOpenAIDeploymentSku string = 'GlobalStandard'

@allowed(['gpt-4o', 'gpt-4o-mini'])
@description('GPT model to deploy: gpt-4o (full capability, higher quota) or gpt-4o-mini (80-90% capability, lower quota). Default gpt-4o for prod/staging.')
param azureOpenAIModelName string = 'gpt-4o'

@allowed([
  '2024-05-13'
  '2024-07-18'
  '2024-08-06'
  '2024-11-20'
])
@description('Model version for GPT deployments; 2024-11-20 for gpt-4o, 2024-07-18 for gpt-4o-mini. Must match the model specified in azureOpenAIModelName.')
param azureOpenAIModelVersion string = '2024-11-20'

@minValue(1)
@maxValue(1000)
@description('Deployment capacity units for Azure OpenAI. Each unit represents 1K tokens per minute (TPM). For GlobalStandard SKU, capacity determines throughput allocation across global regions. Use lower values for dev, higher for prod.')
param azureOpenAIDeploymentCapacity int = 10

@description('Whether to deploy embedding model (text-embedding-ada-002 or text-embedding-3-*) to Azure OpenAI')
param deployAzureOpenAIEmbeddingModel bool = true

@allowed(['text-embedding-ada-002', 'text-embedding-3-small', 'text-embedding-3-large'])
@description('Embedding model to deploy to Azure OpenAI')
param azureOpenAIEmbeddingModelName string = 'text-embedding-ada-002'

@minValue(1)
@maxValue(1000)
@description('Deployment capacity units for Azure OpenAI embedding model')
param azureOpenAIEmbeddingDeploymentCapacity int = 10

@description('IPv4 CIDR allowlist for Azure OpenAI when public network access is enabled')
param azureOpenAIAllowedCidrs array = []

@description('Enable public network access to Key Vault. Set to false for production with Private Link.')
param enablePublicNetworkAccess bool = true

@description('Enable Azure RBAC authorization for Key Vault with per-secret access control. STRONGLY RECOMMENDED for production to enforce least-privilege principles.')
param enableRbacAuthorization bool = true

param tags object = {
  environment: environment
  project: 'copilot-for-consensus'
  createdBy: 'bicep'
  scope: 'core'
}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)

// Core Key Vault name must be 3-24 characters, globally unique
var coreKeyVaultName = '${projectPrefix}corekv${take(uniqueSuffix, 10)}'

// OpenAI account name must be globally unique and lowercase
var openaiAccountName = toLower('${take(projectPrefix, 10)}-oai-core-${take(uniqueSuffix, 5)}')

// Create a dedicated managed identity for OpenAI in the Core RG
resource openaiIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${projectName}-core-openai-id'
  location: location
  tags: tags
}

// Module: Azure Key Vault for Core secrets
module coreKeyVaultModule 'modules/keyvault.bicep' = {
  name: 'coreKeyVaultDeployment'
  params: {
    location: location
    keyVaultName: coreKeyVaultName
    tenantId: subscription().tenantId
    managedIdentityPrincipalIds: []  // No read access needed at Core level; env identities will be granted access via RBAC
    secretWriterPrincipalIds: []  // Secrets will be written by this template, not deployment scripts
    enablePublicNetworkAccess: enablePublicNetworkAccess
    enableRbacAuthorization: enableRbacAuthorization
    tags: tags
  }
}

// Module: Azure OpenAI
module openaiModule 'modules/openai.bicep' = {
  name: 'coreOpenaiDeployment'
  params: {
    location: location
    accountName: openaiAccountName
    sku: azureOpenAISku
    modelName: azureOpenAIModelName
    deploymentSku: azureOpenAIDeploymentSku
    modelVersion: azureOpenAIModelVersion
    deploymentCapacity: azureOpenAIDeploymentCapacity
    deployEmbeddingModel: deployAzureOpenAIEmbeddingModel
    embeddingModelName: azureOpenAIEmbeddingModelName
    embeddingDeploymentCapacity: azureOpenAIEmbeddingDeploymentCapacity
    identityResourceId: openaiIdentity.id
    enablePublicNetworkAccess: environment == 'dev'  // For dev enable public endpoint, but defaultAction remains Deny; use azureOpenAIAllowedCidrs to allow specific IPs
    networkDefaultAction: 'Deny'
    ipRules: azureOpenAIAllowedCidrs
    tags: tags
  }
}

// Store Azure OpenAI API key securely in Core Key Vault
resource openaiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${coreKeyVaultName}/azure-openai-api-key'
  properties: {
    value: openaiModule.outputs.apiKey
    contentType: 'text/plain'
  }
  dependsOn: [
    coreKeyVaultModule
  ]
}

// Store Azure OpenAI endpoint in Core Key Vault
resource openaiEndpointSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${coreKeyVaultName}/azure-openai-endpoint'
  properties: {
    value: openaiModule.outputs.accountEndpoint
    contentType: 'text/plain'
  }
  dependsOn: [
    coreKeyVaultModule
  ]
}

// Store Azure OpenAI GPT deployment name in Core Key Vault
resource openaiGptDeploymentSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${coreKeyVaultName}/azure-openai-gpt-deployment-name'
  properties: {
    value: openaiModule.outputs.gpt4DeploymentName
    contentType: 'text/plain'
  }
  dependsOn: [
    coreKeyVaultModule
  ]
}

// Store Azure OpenAI embedding deployment name in Core Key Vault
resource openaiEmbeddingDeploymentSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployAzureOpenAIEmbeddingModel) {
  name: '${coreKeyVaultName}/azure-openai-embedding-deployment-name'
  properties: {
    value: openaiModule.outputs.embeddingDeploymentName
    contentType: 'text/plain'
  }
  dependsOn: [
    coreKeyVaultModule
  ]
}

// Outputs for consumption by env deployments
@description('Core Key Vault resource ID')
output coreKvResourceId string = coreKeyVaultModule.outputs.keyVaultId

@description('Core Key Vault name')
output coreKvName string = coreKeyVaultModule.outputs.keyVaultName

@description('Core Key Vault URI')
output coreKvUri string = coreKeyVaultModule.outputs.keyVaultUri

@description('Azure OpenAI endpoint URL')
output aoaiEndpoint string = openaiModule.outputs.accountEndpoint

@description('Azure OpenAI GPT-4 deployment name')
output aoaiGptDeploymentName string = openaiModule.outputs.gpt4DeploymentName

@description('Azure OpenAI embedding deployment name')
output aoaiEmbeddingDeploymentName string = deployAzureOpenAIEmbeddingModel ? openaiModule.outputs.embeddingDeploymentName : ''

@description('Azure OpenAI account resource ID')
output aoaiAccountId string = openaiModule.outputs.accountId

@description('Azure OpenAI account name')
output aoaiAccountName string = openaiModule.outputs.accountName

@description('Secret URIs for env deployments to reference')
output kvSecretUris object = {
  aoaiKey: openaiApiKeySecret.properties.secretUriWithVersion
  aoaiEndpoint: openaiEndpointSecret.properties.secretUriWithVersion
  aoaiGptDeploymentName: openaiGptDeploymentSecret.properties.secretUriWithVersion
  aoaiEmbeddingDeploymentName: deployAzureOpenAIEmbeddingModel ? openaiEmbeddingDeploymentSecret!.properties.secretUriWithVersion : ''
}

@description('Deployment summary')
output summary string = '''
Core infrastructure deployed successfully:
- Azure OpenAI: ${openaiModule.outputs.accountName}
- Key Vault: ${coreKeyVaultModule.outputs.keyVaultName}
- GPT Deployment: ${openaiModule.outputs.gpt4DeploymentName}
- Embedding Deployment: ${deployAzureOpenAIEmbeddingModel ? openaiModule.outputs.embeddingDeploymentName : 'Not deployed'}

Next steps:
1. Note the output values above for use in env deployments
2. Deploy environment-specific resources using main.bicep with these Core outputs
3. Grant env managed identities 'Key Vault Secrets User' role on Core Key Vault
'''
