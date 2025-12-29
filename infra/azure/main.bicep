// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Main orchestration template for Copilot for Consensus Azure deployment'
metadata author = 'Copilot-for-Consensus Team'

@minLength(3)
@maxLength(15)
param projectName string = 'copilot'

@allowed(['dev', 'test', 'prod'])
param environment string = 'dev'

param location string = 'westus'

param containerImageTag string = 'latest'

param deployAzureOpenAI bool = true

@allowed(['S0', 'S1', 'S2'])
param azureOpenAISku string = 'S0'

@minValue(400)
@maxValue(1000000)
param cosmosDbAutoscaleMinRu int = 400

// cosmosDbAutoscaleMaxRu must be >= cosmosDbAutoscaleMinRu
@minValue(400)
@maxValue(1000000)
param cosmosDbAutoscaleMaxRu int = 1000

@allowed(['Standard', 'Premium'])
param serviceBusSku string = 'Standard'

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

var uniqueSuffix = uniqueString(resourceGroup().id)
// Key Vault name must be 3-24 characters, globally unique
var keyVaultName = '${take(projectName, 8)}kv${take(uniqueSuffix, 13)}'
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
    tags: tags
  }
}

// Module: Azure Service Bus (Placeholder for PR #2)
// module serviceBusModule 'modules/servicebus.bicep' = {
//   name: 'serviceBusDeployment'
//   ...
// }

// Module: Azure Cosmos DB (Placeholder for PR #3)
// module cosmosModule 'modules/cosmos.bicep' = {
//   name: 'cosmosDeployment'
//   ...
// }

// Module: Azure OpenAI (Placeholder for PR #4)
// module openaiModule 'modules/openai.bicep' = {
//   name: 'openaiDeployment'
//   ...
// }

// Module: Container Apps (Placeholder for PR #5)
// module containerAppsModule 'modules/containerapps.bicep' = {
//   name: 'containerAppsDeployment'
//   ...
// }

// Outputs
output keyVaultUri string = keyVaultModule.outputs.keyVaultUri
output keyVaultName string = keyVaultModule.outputs.keyVaultName
output managedIdentities array = identitiesModule.outputs.identities
output resourceGroupName string = resourceGroup().name
output location string = location
output environment string = environment
output deploymentId string = deployment().name
