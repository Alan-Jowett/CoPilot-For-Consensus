// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Main orchestration template for Copilot for Consensus Azure deployment'
metadata author = 'Copilot-for-Consensus Team'

@minLength(3)
@maxLength(15)
param projectName string = 'copilot'

@allowed(['dev', 'staging', 'prod'])  // Keep environment alignment across docs and params
param environment string = 'dev'

param location string = 'westus'

#disable-next-line no-unused-params
param containerImageTag string = 'latest'

#disable-next-line no-unused-params
param deployAzureOpenAI bool = true

@allowed(['S0', 'S1', 'S2'])
#disable-next-line no-unused-params
param azureOpenAISku string = 'S0'

@minValue(400)
@maxValue(1000000)
#disable-next-line no-unused-params
param cosmosDbAutoscaleMinRu int = 400

// cosmosDbAutoscaleMaxRu must be >= cosmosDbAutoscaleMinRu
@minValue(400)
@maxValue(1000000)
#disable-next-line no-unused-params
param cosmosDbAutoscaleMaxRu int = 1000

@allowed(['Standard', 'Premium'])
param serviceBusSku string = 'Standard'

#disable-next-line no-unused-params
param enableMultiRegionCosmos bool = false

param tags object = {
  environment: environment
  project: 'copilot-for-consensus'
  createdBy: 'bicep'
}

// Service names for identity assignment
var services = [
  'ingestion'
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
  'auth'
  'ui'
  'gateway'
]

// Explicit sender/receiver lists for least-privilege RBAC in Service Bus
var serviceBusSenderServices = [
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
]

var serviceBusReceiverServices = [
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
  'ingestion'
]

var uniqueSuffix = uniqueString(resourceGroup().id)
// Ensure project name prefix doesn't end with dash to avoid double-dash in resource names
var projectPrefix = take(replace(projectName, '-', ''), 8)
// Key Vault name must be 3-24 characters, globally unique
var keyVaultName = '${projectPrefix}kv${take(uniqueSuffix, 13)}'
var identityPrefix = '${projectName}-${environment}'

// Module: User-Assigned Managed Identities
module identitiesModule 'modules/identities.bicep' = {
  name: 'identitiesDeployment'
  params: {
    location: location
    identityPrefix: identityPrefix
    services: services
    tags: tags
  }
}

// Module: Azure Key Vault
module keyVaultModule 'modules/keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    tenantId: subscription().tenantId
    managedIdentityPrincipalIds: identitiesModule.outputs.identityPrincipalIds
    enablePublicNetworkAccess: true  // Set to false for production with Private Link
    enableRbacAuthorization: false  // TODO: Migrate to true in future PRs (#2-5) when services use Azure RBAC role assignments
    tags: tags
  }
}

// Variable for Service Bus namespace name (must be globally unique)
// Use projectPrefix to avoid double-dash issues
var serviceBusNamespaceName = '${projectPrefix}-sb-${environment}-${take(uniqueSuffix, 8)}'
// Cosmos DB account name must be globally unique and lowercase
var cosmosAccountName = toLower('${take(projectPrefix, 10)}-cos-${environment}-${take(uniqueSuffix, 5)}')
// OpenAI account name must be globally unique and lowercase
var openaiAccountName = toLower('${take(projectPrefix, 10)}-oai-${environment}-${take(uniqueSuffix, 5)}')

// Module: Azure Service Bus
module serviceBusModule 'modules/servicebus.bicep' = {
  name: 'serviceBusDeployment'
  params: {
    location: location
    namespaceName: serviceBusNamespaceName
    sku: serviceBusSku
    identityResourceIds: identitiesModule.outputs.identityResourceIds
    senderServices: serviceBusSenderServices
    receiverServices: serviceBusReceiverServices
  }
}

// Module: Azure Cosmos DB
module cosmosModule 'modules/cosmos.bicep' = {
  name: 'cosmosDeployment'
  params: {
    location: location
    accountName: cosmosAccountName
    enableMultiRegion: enableMultiRegionCosmos
    cosmosDbAutoscaleMinRu: cosmosDbAutoscaleMinRu
    cosmosDbAutoscaleMaxRu: cosmosDbAutoscaleMaxRu
    tags: tags
  }
}

// Module: Azure OpenAI
module openaiModule 'modules/openai.bicep' = if (deployAzureOpenAI) {
  name: 'openaiDeployment'
  params: {
    location: location
    accountName: openaiAccountName
    sku: azureOpenAISku
    enablePublicNetworkAccess: environment == 'dev'  // Disable for non-dev; use Private Link in staging/prod
    networkDefaultAction: environment == 'dev' ? 'Allow' : 'Deny'
    tags: tags
  }
}

// Module: Container Apps (Placeholder for PR #5)
// module containerAppsModule 'modules/containerapps.bicep' = {
//   name: 'containerAppsDeployment'
//   ...
// }

// Outputs
output keyVaultUri string = keyVaultModule.outputs.keyVaultUri
output keyVaultName string = keyVaultModule.outputs.keyVaultName
output managedIdentities array = identitiesModule.outputs.identities
output serviceBusNamespace string = serviceBusModule.outputs.namespaceName
output serviceBusNamespaceId string = serviceBusModule.outputs.namespaceResourceId
output serviceBusQueues array = serviceBusModule.outputs.queueNames
output cosmosAccountName string = cosmosModule.outputs.accountName
output cosmosAccountEndpoint string = cosmosModule.outputs.accountEndpoint
output cosmosDatabaseName string = cosmosModule.outputs.databaseName
output cosmosContainerName string = cosmosModule.outputs.containerName
output cosmosAutoscaleMaxRu int = cosmosModule.outputs.autoscaleMaxThroughput
output cosmosWriteRegions array = cosmosModule.outputs.writeRegions
output openaiAccountName string = deployAzureOpenAI ? openaiModule.outputs.accountName : ''
output openaiAccountId string = deployAzureOpenAI ? openaiModule.outputs.accountId : ''
output openaiAccountEndpoint string = deployAzureOpenAI ? openaiModule.outputs.accountEndpoint : ''
output openaiCustomSubdomain string = deployAzureOpenAI ? openaiModule.outputs.customSubdomain : ''
output openaiGpt4DeploymentId string = deployAzureOpenAI ? openaiModule.outputs.gpt4DeploymentId : ''
output openaiGpt4DeploymentName string = deployAzureOpenAI ? openaiModule.outputs.gpt4DeploymentName : ''
output openaiSkuName string = deployAzureOpenAI ? openaiModule.outputs.skuName : ''
output resourceGroupName string = resourceGroup().name
output location string = location
output environment string = environment
output deploymentId string = deployment().name
