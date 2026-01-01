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

// Azure OpenAI accounts only support S0 (S1/S2 apply to other Cognitive Services resources, not OpenAI)
@allowed(['S0'])
#disable-next-line no-unused-params
@description('SKU for Azure OpenAI Service. Azure OpenAI currently only supports the S0 SKU; other SKUs are not valid for this resource type.')
param azureOpenAISku string = 'S0'

@allowed(['Standard', 'GlobalStandard'])
#disable-next-line no-unused-params
@description('Deployment SKU for Azure OpenAI (GlobalStandard recommended for production)')
param azureOpenAIDeploymentSku string = 'GlobalStandard'

@allowed([
  '2024-05-13'
  '2024-08-06'
  '2024-11-20'
])
#disable-next-line no-unused-params
@description('Model version for GPT-4o deployments; default tracks latest GA. Override per environment if needed.')
param azureOpenAIModelVersion string = '2024-11-20'

@minValue(1)
@maxValue(1000)
#disable-next-line no-unused-params
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

@description('Whether to deploy Container Apps environment and services')
param deployContainerApps bool = true

@description('VNet address space for Container Apps (CIDR notation)')
param vnetAddressSpace string = '10.0.0.0/16'

@description('Container Apps subnet address prefix (CIDR notation)')
param subnetAddressPrefix string = '10.0.0.0/23'

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

@description('Grafana admin username for monitoring dashboards (optional, stored in Key Vault)')
@secure()
param grafanaAdminUser string = ''

@description('Grafana admin password for monitoring dashboards (optional, stored in Key Vault)')
@secure()
param grafanaAdminPassword string = ''

param tags object = {
  environment: environment
  project: 'copilot-for-consensus'
  createdBy: 'bicep'
}

@description('Force tag to control JWT key regeneration. Use utcNow() to regenerate keys on every deployment (WARNING: invalidates all active sessions). Default: keys persist across deployments unless this parameter changes.')
param jwtForceUpdateTag string = 'stable'

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
  'openai'
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
var jwtKeysIdentityName = '${identityPrefix}-jwtkeys-id'

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

// Dedicated identity to set JWT secrets in Key Vault during deployment
resource jwtKeysIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployContainerApps) {
  name: jwtKeysIdentityName
  location: location
  tags: tags
}

// Module: Azure Key Vault
// Note: secretWriterPrincipalIds is currently limited to jwtKeysIdentity for deployment script write access.
// If additional deployment scripts or components require Key Vault write permissions in the future,
// consider refactoring to a dedicated parameter or variable array for better extensibility.
module keyVaultModule 'modules/keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    tenantId: subscription().tenantId
    managedIdentityPrincipalIds: identitiesModule.outputs.identityPrincipalIds
    secretWriterPrincipalIds: deployContainerApps ? [jwtKeysIdentity!.properties.principalId] : []
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
// Azure AI Search service name must be globally unique and lowercase
var aiSearchServiceName = toLower('${take(projectPrefix, 10)}-ais-${environment}-${take(uniqueSuffix, 5)}')
// Storage Account name must be globally unique, lowercase, 3-24 chars (no hyphens allowed)
// Length breakdown: 6 (projectPrefix) + 2 ('st') + 3 (environment) + 10 (uniqueSuffix) = 21 chars (within 3-24 limit)
var storageAccountName = toLower('${take(projectPrefix, 6)}st${take(environment, 3)}${take(uniqueSuffix, 10)}')

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

// Module: Azure Storage Account (blob storage for archives)
// Only deployed when Container Apps are enabled (ingestion service requires blob storage)
module storageModule 'modules/storage.bicep' = if (deployContainerApps) {
  name: 'storageDeployment'
  params: {
    location: location
    storageAccountName: storageAccountName
    sku: environment == 'prod' ? 'Standard_GRS' : 'Standard_LRS'
    accessTier: 'Hot'
    enableHierarchicalNamespace: false
    containerNames: ['archives']
    // SECURITY: Only grant blob access to services that actually need it
    // ingestion: stores raw email archives, parsing: reads archives for processing
    contributorPrincipalIds: [
      identitiesModule.outputs.identityPrincipalIdsByName.ingestion
      identitiesModule.outputs.identityPrincipalIdsByName.parsing
    ]
    networkDefaultAction: environment == 'prod' ? 'Deny' : 'Allow'
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
    deploymentSku: azureOpenAIDeploymentSku
    modelVersion: azureOpenAIModelVersion
    deploymentCapacity: azureOpenAIDeploymentCapacity
    deployEmbeddingModel: deployAzureOpenAIEmbeddingModel
    embeddingModelName: azureOpenAIEmbeddingModelName
    embeddingDeploymentCapacity: azureOpenAIEmbeddingDeploymentCapacity
    identityResourceId: identitiesModule.outputs.identityResourceIds.openai
    enablePublicNetworkAccess: environment == 'dev'  // For dev enable public endpoint, but defaultAction remains Deny; use azureOpenAIAllowedCidrs to allow specific IPs
    networkDefaultAction: 'Deny'
    ipRules: azureOpenAIAllowedCidrs
    tags: tags
  }
}

// Module: Azure AI Search (vector store)
// Only deployed when Container Apps are enabled (required for embedding service)
module aiSearchModule 'modules/aisearch.bicep' = if (deployContainerApps) {
  name: 'aiSearchDeployment'
  params: {
    location: location
    serviceName: aiSearchServiceName
    sku: environment == 'prod' ? 'standard' : 'basic'
    embeddingServicePrincipalId: identitiesModule.outputs.identityPrincipalIdsByName.embedding  // use named mapping to avoid fragile index coupling
    enablePublicNetworkAccess: environment != 'prod'  // Disable for production (Private Link), enable for dev/staging
    tags: tags
  }
}

// Module: Application Insights (monitoring for Container Apps)
module appInsightsModule 'modules/appinsights.bicep' = if (deployContainerApps) {
  name: 'appInsightsDeployment'
  params: {
    location: location
    projectName: projectName
    environment: environment
    tags: tags
  }
}

// Store Application Insights secrets securely in Key Vault
// These must NOT be passed as plaintext environment variables to Container Apps
resource appInsightsInstrKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployContainerApps) {
  name: '${keyVaultName}/appinsights-instrumentation-key'
  properties: {
    value: appInsightsModule!.outputs.instrumentationKey
    contentType: 'text/plain'
  }
}

// Module: Generate per-deployment JWT keys and store in Key Vault
module jwtKeysModule 'modules/jwtkeys.bicep' = if (deployContainerApps) {
  name: 'jwtKeysDeployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    scriptIdentityId: jwtKeysIdentity!.id
    forceUpdateTag: jwtForceUpdateTag
    tags: tags
  }
  dependsOn: [
    keyVaultModule
  ]
}

resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployContainerApps) {
  name: '${keyVaultName}/appinsights-connection-string'
  properties: {
    value: appInsightsModule!.outputs.connectionString
    contentType: 'text/plain'
  }
}

// Store Grafana admin credentials in Key Vault
// These are used when Grafana is deployed as a Container App for monitoring dashboards
// Credentials can be rotated by updating the secrets in Key Vault and restarting the Grafana Container App
// Note: Username secret is always created (defaults to 'admin') so it's present for rotation workflows
resource grafanaAdminUserSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  name: '${keyVaultName}/grafana-admin-user'
  properties: {
    value: grafanaAdminUser != '' ? grafanaAdminUser : 'admin'
    contentType: 'text/plain'
  }
}

// Password is only stored if explicitly provided (no default for security)
resource grafanaAdminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (grafanaAdminPassword != '') {
  name: '${keyVaultName}/grafana-admin-password'
  properties: {
    value: grafanaAdminPassword
    contentType: 'text/plain'
  }
}

// Store Azure OpenAI API key securely in Key Vault when OpenAI is deployed
// Services will access this via Key Vault reference in environment variables
resource openaiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployAzureOpenAI && deployContainerApps) {
  name: '${keyVaultName}/azure-openai-api-key'
  properties: {
    value: deployAzureOpenAI ? listKeys(
      resourceId('Microsoft.CognitiveServices/accounts', openaiAccountName),
      '2023-10-01-preview'
    ).key1 : ''
    contentType: 'text/plain'
  }
  dependsOn: [keyVaultModule]
}

// Module: Virtual Network (for Container Apps integration)
module vnetModule 'modules/vnet.bicep' = if (deployContainerApps) {
  name: 'vnetDeployment'
  params: {
    location: location
    projectName: projectName
    environment: environment
    vnetAddressSpace: vnetAddressSpace
    subnetAddressPrefix: subnetAddressPrefix
    tags: tags
  }
}

// Module: Container Apps (VNet and 10 microservices)
// IMPORTANT: This module uses non-null assertions (!) for outputs from vnetModule, appInsightsModule,
// aiSearchModule, and Key Vault secrets. These assertions are safe ONLY because this module has the same
// conditional guard (if (deployContainerApps)) as those resources. Changing this condition independently
// will cause deployment failures. Keep all Container Apps-related conditionals synchronized.
module containerAppsModule 'modules/containerapps.bicep' = if (deployContainerApps) {
  name: 'containerAppsDeployment'
  params: {
    location: location
    projectName: projectName
    environment: environment
    containerRegistry: 'ghcr.io/alan-jowett/copilot-for-consensus'
    containerImageTag: containerImageTag
    identityResourceIds: identitiesModule.outputs.identityResourceIds
    azureOpenAIEndpoint: deployAzureOpenAI ? openaiModule!.outputs.accountEndpoint : ''
    azureOpenAIGpt4DeploymentName: deployAzureOpenAI ? openaiModule!.outputs.gpt4DeploymentName : ''
    azureOpenAIEmbeddingDeploymentName: deployAzureOpenAI && deployAzureOpenAIEmbeddingModel ? openaiModule!.outputs.embeddingDeploymentName : ''
    azureOpenAIApiKeySecretUri: deployAzureOpenAI ? openaiApiKeySecret!.properties.secretUriWithVersion : ''
    aiSearchEndpoint: aiSearchModule!.outputs.endpoint
    serviceBusNamespace: serviceBusModule.outputs.namespaceName
    cosmosDbEndpoint: cosmosModule.outputs.accountEndpoint
    storageAccountName: storageModule!.outputs.accountName
    storageBlobEndpoint: storageModule!.outputs.blobEndpoint
    subnetId: vnetModule!.outputs.containerAppsSubnetId
    keyVaultName: keyVaultName
    appInsightsKeySecretUri: appInsightsInstrKeySecret!.properties.secretUriWithVersion
    appInsightsConnectionStringSecretUri: appInsightsConnectionStringSecret!.properties.secretUriWithVersion
    logAnalyticsWorkspaceId: appInsightsModule!.outputs.workspaceId
    logAnalyticsCustomerId: appInsightsModule!.outputs.workspaceCustomerId
    tags: tags
  }
  dependsOn: [
    jwtKeysModule  // Ensure JWT keys are generated before auth service starts
  ]
}

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
output storageAccountName string = deployContainerApps ? storageModule!.outputs.accountName : ''
output storageAccountId string = deployContainerApps ? storageModule!.outputs.accountId : ''
output storageBlobEndpoint string = deployContainerApps ? storageModule!.outputs.blobEndpoint : ''
output storageContainerNames array = deployContainerApps ? storageModule!.outputs.containerNames : []
output openaiAccountName string = deployAzureOpenAI ? openaiModule!.outputs.accountName : ''
output openaiAccountId string = deployAzureOpenAI ? openaiModule!.outputs.accountId : ''
output openaiAccountEndpoint string = deployAzureOpenAI ? openaiModule!.outputs.accountEndpoint : ''
output openaiCustomSubdomain string = deployAzureOpenAI ? openaiModule!.outputs.customSubdomain : ''
output openaiGpt4DeploymentId string = deployAzureOpenAI ? openaiModule!.outputs.gpt4DeploymentId : ''
output openaiGpt4DeploymentName string = deployAzureOpenAI ? openaiModule!.outputs.gpt4DeploymentName : ''
output openaiEmbeddingDeploymentId string = deployAzureOpenAI && deployAzureOpenAIEmbeddingModel ? openaiModule!.outputs.embeddingDeploymentId : ''
output openaiEmbeddingDeploymentName string = deployAzureOpenAI && deployAzureOpenAIEmbeddingModel ? openaiModule!.outputs.embeddingDeploymentName : ''
output openaiSkuName string = deployAzureOpenAI ? openaiModule!.outputs.skuName : ''
// AI Search outputs: naming follows Azure resource type (Microsoft.Search/searchServices uses "service", not "account")
output aiSearchServiceName string = deployContainerApps ? aiSearchModule!.outputs.serviceName : ''
output aiSearchEndpoint string = deployContainerApps ? aiSearchModule!.outputs.endpoint : ''
output aiSearchServiceId string = deployContainerApps ? aiSearchModule!.outputs.serviceId : ''
output appInsightsId string = deployContainerApps ? appInsightsModule!.outputs.appInsightsId : ''
output containerAppsEnvId string = deployContainerApps ? containerAppsModule!.outputs.containerAppsEnvId : ''
output gatewayFqdn string = deployContainerApps ? containerAppsModule!.outputs.gatewayFqdn : ''
output containerAppIds object = deployContainerApps ? containerAppsModule!.outputs.appIds : {}
output vnetId string = deployContainerApps ? vnetModule!.outputs.vnetId : ''
output resourceGroupName string = resourceGroup().name
output location string = location
output environment string = environment
output deploymentId string = deployment().name

// OAuth and Grafana secret setup instructions
output oauthSecretsSetupInstructions string = '''
JWT keys are automatically generated during deployment. To configure OAuth providers, set secrets manually in Key Vault:

# Set OAuth credentials (replace with actual values):
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name github-oauth-client-id --value "YOUR_GITHUB_CLIENT_ID"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name github-oauth-client-secret --value "YOUR_GITHUB_CLIENT_SECRET"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name google-oauth-client-id --value "YOUR_GOOGLE_CLIENT_ID"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name google-oauth-client-secret --value "YOUR_GOOGLE_CLIENT_SECRET"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name microsoft-oauth-client-id --value "YOUR_MICROSOFT_CLIENT_ID"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name microsoft-oauth-client-secret --value "YOUR_MICROSOFT_CLIENT_SECRET"

# Set Grafana admin credentials (if deploying Grafana):
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name grafana-admin-user --value "admin"
az keyvault secret set --vault-name ${keyVaultModule.outputs.keyVaultName} --name grafana-admin-password --value "YOUR_SECURE_PASSWORD"

After setting secrets, restart the auth service to pick up the new values:
az containerapp restart --name <project>-auth-<env> --resource-group <resource-group>
'''


