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

// ========================================
// Core RG Integration Parameters
// ========================================
// These parameters reference resources deployed in the Core RG (rg-core-ai)
// Obtain these values from the Core deployment outputs (core.bicep)

@description('Azure OpenAI endpoint URL from Core deployment')
param azureOpenAIEndpoint string

@description('Azure OpenAI GPT deployment name from Core deployment')
param azureOpenAIGptDeploymentName string

@description('Azure OpenAI embedding deployment name from Core deployment (empty string if not deployed)')
param azureOpenAIEmbeddingDeploymentName string = ''

@description('Core Key Vault resource ID from Core deployment')
param coreKeyVaultResourceId string

@description('Core Key Vault name from Core deployment')
param coreKeyVaultName string

@description('Secret URI for Azure OpenAI API key in Core Key Vault')
param coreKvSecretUriAoaiKey string

@minLength(3)
@maxLength(64)
@description('Azure OpenAI account name from Core deployment outputs (aoaiAccountName). Prefer passing this explicitly rather than deriving it from the endpoint.')
param coreAoaiAccountName string

// IMPORTANT: Azure OpenAI resource name is NOT reliably derivable from the endpoint hostname.
// Always pass the resource name explicitly via coreAoaiAccountName (from Core deployment output aoaiAccountName).
var effectiveAoaiAccountName = toLower(coreAoaiAccountName)

// ========================================
// End Core RG Integration Parameters
// ========================================

@description('Whether to deploy Container Apps environment and services')
param deployContainerApps bool = true

@allowed(['qdrant', 'azure_ai_search'])
@description('Vector store backend to use: qdrant (default, low cost) or azure_ai_search (higher cost, more features)')
param vectorStoreBackend string = 'qdrant'

@description('VNet address space for Container Apps (CIDR notation)')
param vnetAddressSpace string = '10.0.0.0/16'

@description('Container Apps subnet address prefix (CIDR notation)')
param subnetAddressPrefix string = '10.0.0.0/23'

@description('Private Endpoints subnet address prefix (CIDR notation)')
param privateEndpointSubnetPrefix string = '10.0.2.0/24'

@description('Whether to create Microsoft Entra app registration for OAuth')
param deployEntraApp bool = false

@description('Microsoft Entra (Azure AD) tenant ID for OAuth authentication')
param entraTenantId string = subscription().tenantId

@description('Override redirect URIs for OAuth (defaults to gateway FQDN callback)')
param oauthRedirectUris array = []

@description('Client secret expiration in days for Entra app (valid range: 30-730 days)')
@minValue(30)
@maxValue(730)
param oauthSecretExpirationDays int = 365

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

@description('GitHub OAuth application client ID (optional, stored in Key Vault)')
@secure()
param githubOAuthClientId string = ''

@description('GitHub OAuth application client secret (optional, stored in Key Vault)')
@secure()
param githubOAuthClientSecret string = ''

@description('Enable public network access to Key Vault. Set to false for production with Private Link.')
param enablePublicNetworkAccess bool = true

@description('Enable private network access (Private Link). When true, disables public access and creates Private Endpoints.')
param enablePrivateAccess bool = false

@description('Enable Azure RBAC authorization for Key Vault with per-secret access control. STRONGLY RECOMMENDED for production to enforce least-privilege principles.')
param enableRbacAuthorization bool = true

@description('Enable Blob storage archiving for ACA console logs (NDJSON format)')
param enableBlobLogArchiving bool = true

param tags object = {
  environment: environment
  project: 'copilot-for-consensus'
  createdBy: 'bicep'
}

@description('Force tag to control JWT key regeneration. Use utcNow() to regenerate keys on every deployment (WARNING: invalidates all active sessions). Default: keys persist across deployments unless this parameter changes.')
param jwtForceUpdateTag string = 'stable'

// Service names for identity assignment
// Note: 'openai' identity is managed in Core RG, not here
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
  'ingestion'
]

var serviceBusReceiverServices = [
  'parsing'
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
// Env Key Vault name must be 3-24 characters, globally unique
// Note: Core RG has its own Key Vault (coreKeyVaultName) for AOAI secrets
var keyVaultName = '${projectPrefix}envkv${take(uniqueSuffix, 11)}'
var identityPrefix = '${projectName}-${environment}'
var jwtKeysIdentityName = '${identityPrefix}-jwtkeys-id'
var entraAppIdentityName = '${identityPrefix}-entraapp-id'

// Compute effective public network access settings
// When enablePrivateAccess is true, force public access to false for all resources
var effectiveEnablePublicNetworkAccess = enablePrivateAccess ? false : enablePublicNetworkAccess

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

// Dedicated identity for Entra app deployment script with Graph API permissions
// This identity must be granted Application.ReadWrite.All and Directory.ReadWrite.All
// permissions by a Global Administrator before the deployment script can execute successfully.
resource entraAppIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = if (deployContainerApps && deployEntraApp) {
  name: entraAppIdentityName
  location: location
  tags: tags
}

// Module: Azure Key Vault
// Note: secretWriterPrincipalIds includes both jwtKeysIdentity and entraAppIdentity for deployment script write access.
// If additional deployment scripts or components require Key Vault write permissions in the future,
// consider refactoring to a dedicated parameter or variable array for better extensibility.
module keyVaultModule 'modules/keyvault.bicep' = {
  name: 'keyVaultDeployment'
  params: {
    location: location
    keyVaultName: keyVaultName
    tenantId: subscription().tenantId
    managedIdentityPrincipalIds: identitiesModule.outputs.identityPrincipalIds
    secretWriterPrincipalIds: deployContainerApps ? concat(
      [jwtKeysIdentity!.properties.principalId],
      deployEntraApp ? [entraAppIdentity!.properties.principalId] : []
    ) : []
    enablePublicNetworkAccess: effectiveEnablePublicNetworkAccess
    enableRbacAuthorization: enableRbacAuthorization
    tags: tags
  }
}

// Variable for Service Bus namespace name (must be globally unique)
// Use projectPrefix to avoid double-dash issues
var serviceBusNamespaceName = '${projectPrefix}-sb-${environment}-${take(uniqueSuffix, 8)}'
// Cosmos DB account name must be globally unique and lowercase
var cosmosAccountName = toLower('${take(projectPrefix, 10)}-cos-${environment}-${take(uniqueSuffix, 5)}')
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
    enablePublicNetworkAccess: effectiveEnablePublicNetworkAccess
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
    enablePublicNetworkAccess: effectiveEnablePublicNetworkAccess
    tags: tags
  }
}

// Module: Cosmos DB RBAC - Assign Data Contributor role to services that need document store access
// Services requiring Cosmos DB access: auth, parsing, chunking, embedding, orchestrator, summarization, reporting, ingestion
module cosmosRbacModule 'modules/cosmos-rbac.bicep' = {
  name: 'cosmosRbacDeployment'
  params: {
    cosmosAccountName: cosmosModule.outputs.accountName
    principalIds: [
      identitiesModule.outputs.identityPrincipalIdsByName.auth
      identitiesModule.outputs.identityPrincipalIdsByName.parsing
      identitiesModule.outputs.identityPrincipalIdsByName.chunking
      identitiesModule.outputs.identityPrincipalIdsByName.embedding
      identitiesModule.outputs.identityPrincipalIdsByName.orchestrator
      identitiesModule.outputs.identityPrincipalIdsByName.summarization
      identitiesModule.outputs.identityPrincipalIdsByName.reporting
      identitiesModule.outputs.identityPrincipalIdsByName.ingestion
    ]
  }
  dependsOn: [
    cosmosModule
    identitiesModule
  ]
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
    containerNames: concat(['archives'], enableBlobLogArchiving ? ['logs-raw'] : [])
    // SECURITY: Only grant blob access to services that actually need it
    // ingestion: stores raw email archives, parsing: reads archives for processing
    contributorPrincipalIds: [
      identitiesModule.outputs.identityPrincipalIdsByName.ingestion
      identitiesModule.outputs.identityPrincipalIdsByName.parsing
    ]
    networkDefaultAction: effectiveEnablePublicNetworkAccess ? 'Allow' : 'Deny'
    tags: tags
  }
}

// ========================================
// Cross-RG RBAC: Grant Env identities access to Core Key Vault
// ========================================

// Parse Core Key Vault resource ID to get subscription and resource group
var coreKvSubscriptionId = split(coreKeyVaultResourceId, '/')[2]
var coreKvResourceGroupName = split(coreKeyVaultResourceId, '/')[4]

// Grant all env service identities access to read secrets from Core Key Vault
module coreKvRbacModule 'modules/keyvault-rbac-cross-rg.bicep' = {
  name: 'coreKvRbacDeployment'
  scope: resourceGroup(coreKvSubscriptionId, coreKvResourceGroupName)
  params: {
    keyVaultName: coreKeyVaultName
    envServicePrincipalIds: identitiesModule.outputs.identityPrincipalIds
  }
}

// ========================================
// End Cross-RG RBAC
// ========================================

// Module: Azure AI Search (vector store - optional, higher cost alternative to Qdrant)
// Only deployed when vectorStoreBackend is 'azure_ai_search' and Container Apps are enabled
module aiSearchModule 'modules/aisearch.bicep' = if (deployContainerApps && vectorStoreBackend == 'azure_ai_search') {
  name: 'aiSearchDeployment'
  params: {
    location: location
    serviceName: aiSearchServiceName
    sku: environment == 'prod' ? 'standard' : 'basic'
    embeddingServicePrincipalId: identitiesModule.outputs.identityPrincipalIdsByName.embedding
    summarizationServicePrincipalId: identitiesModule.outputs.identityPrincipalIdsByName.summarization
    enablePublicNetworkAccess: effectiveEnablePublicNetworkAccess
    tags: tags
  }
}

// Module: Azure Portal Dashboard (OpenTelemetry metrics visualization)
// NOTE: Dashboard module disabled - requires Log Analytics workspace which has been removed for cost savings
// module dashboardModule 'modules/dashboard.bicep' = if (deployContainerApps) {
//   name: 'dashboardDeployment'
//   params: {
//     location: location
//     projectName: projectName
//     environment: environment
//     logAnalyticsWorkspaceResourceId: appInsightsModule!.outputs.workspaceId
//     tags: tags
//   }
// }

// Store Application Insights secrets securely in Key Vault
// NOTE: Application Insights disabled for cost savings - Log Analytics workspace removed
// resource appInsightsInstrKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployContainerApps) {
//   name: '${keyVaultName}/azure-monitor-instrumentation-key'
//   properties: {
//     value: appInsightsModule!.outputs.instrumentationKey
//     contentType: 'text/plain'
//   }
//   dependsOn: [
//     keyVaultModule
//   ]
// }

// Store Azure OpenAI API key in Env Key Vault for services using env secret_provider
// NOTE: Core infrastructure also stores this in Core Key Vault. Env services currently use env Key Vault
// for secret_provider (JWT/App Insights/etc), so we replicate the API key here.
var cognitiveServicesApiVersion = '2023-05-01'

// Azure Cognitive Services / Azure OpenAI account name length constraints.
// These are used to guard secret creation. Azure OpenAI account names can be longer than 24 chars.
var cognitiveServicesAccountNameMinLength = 3
var cognitiveServicesAccountNameMaxLength = 64

var shouldCreateEnvOpenaiSecret = deployContainerApps && azureOpenAIEndpoint != '' && effectiveAoaiAccountName != '' && length(effectiveAoaiAccountName) >= cognitiveServicesAccountNameMinLength && length(effectiveAoaiAccountName) <= cognitiveServicesAccountNameMaxLength

resource envOpenaiApiKeySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (shouldCreateEnvOpenaiSecret) {
  name: '${keyVaultName}/azure-openai-api-key'
  properties: {
    // IMPORTANT: The identity executing this deployment must have management-plane access
    // (e.g. 'Cognitive Services Contributor' or equivalent) on the Azure OpenAI account
    // referenced by coreKvSubscriptionId/coreKvResourceGroupName/effectiveAoaiAccountName,
    // otherwise this listKeys() call will fail at deployment time.
    value: listKeys(resourceId(coreKvSubscriptionId, coreKvResourceGroupName, 'Microsoft.CognitiveServices/accounts', effectiveAoaiAccountName), cognitiveServicesApiVersion).key1
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
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

// resource appInsightsConnectionStringSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (deployContainerApps) {
//   name: '${keyVaultName}/azure-monitor-connection-string'
//   properties: {
//     value: appInsightsModule!.outputs.connectionString
//     contentType: 'text/plain'
//   }
//   dependsOn: [
//     keyVaultModule
//   ]
// }

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
  dependsOn: [
    keyVaultModule
  ]
}

// Password is only stored if explicitly provided (no default for security)
resource grafanaAdminPasswordSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (grafanaAdminPassword != '') {
  name: '${keyVaultName}/grafana-admin-password'
  properties: {
    value: grafanaAdminPassword
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
}

// Store GitHub OAuth credentials in Key Vault
// Client ID is only stored if explicitly provided
resource githubOAuthClientIdSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (githubOAuthClientId != '') {
  name: '${keyVaultName}/github-oauth-client-id'
  properties: {
    value: githubOAuthClientId
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
}

// Client secret is only stored if explicitly provided
resource githubOAuthClientSecretSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = if (githubOAuthClientSecret != '') {
  name: '${keyVaultName}/github-oauth-client-secret'
  properties: {
    value: githubOAuthClientSecret
    contentType: 'text/plain'
  }
  dependsOn: [
    keyVaultModule
  ]
}

// Module: Key Vault RBAC - Per-secret role assignments for least-privilege access control
// This module configures fine-grained RBAC permissions, granting each service access only to
// the specific secrets it needs. Deployed after all secrets are created and before Container Apps start.
// Condition: Both deployContainerApps AND enableRbacAuthorization must be true because:
// - Service identities exist unconditionally (identitiesModule has no condition)
// - However, secrets (JWT keys, App Insights) only exist when deployContainerApps = true
// - RBAC assignments require the secrets to exist, so we need both conditions
module keyVaultRbacModule 'modules/keyvault-rbac.bicep' = if (deployContainerApps && enableRbacAuthorization) {
  name: 'keyVaultRbacDeployment'
  params: {
    keyVaultName: keyVaultModule.outputs.keyVaultName
    servicePrincipalIds: identitiesModule.outputs.identityPrincipalIdsByName
    enableRbacAuthorization: enableRbacAuthorization
    deployAzureOpenAI: azureOpenAIEndpoint != ''
  }
  dependsOn: [
    keyVaultModule
    jwtKeysModule  // Ensure JWT secrets exist before assigning access
    // appInsightsInstrKeySecret  // Disabled - Log Analytics removed for cost savings
    // appInsightsConnectionStringSecret  // Disabled - Log Analytics removed for cost savings
    envOpenaiApiKeySecret
    coreKvRbacModule  // Ensure Core KV access is granted before RBAC module runs
  ]
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
    privateEndpointSubnetPrefix: privateEndpointSubnetPrefix
    enablePrivateEndpointSubnet: enablePrivateAccess
    tags: tags
  }
}

// Module: Private DNS Zones (for Private Link)
// Note: Non-null assertions (!) are safe here because this module is only deployed when
// both deployContainerApps and enablePrivateAccess are true, which ensures vnetModule is deployed
module privateDnsModule 'modules/privatedns.bicep' = if (deployContainerApps && enablePrivateAccess) {
  name: 'privateDnsDeployment'
  params: {
    location: location
    vnetId: vnetModule!.outputs.vnetId
    tags: tags
  }
}

// Module: Private Endpoints for Key Vault
module keyVaultPrivateEndpointModule 'modules/privateendpoint.bicep' = if (deployContainerApps && enablePrivateAccess) {
  name: 'keyVaultPrivateEndpointDeployment'
  params: {
    location: location
    privateEndpointName: '${keyVaultName}-pe'
    subnetId: vnetModule!.outputs.privateEndpointSubnetId
    serviceResourceId: keyVaultModule.outputs.keyVaultId
    groupIds: ['vault']
    privateDnsZoneIds: [privateDnsModule!.outputs.privateDnsZoneIds.keyVault]
    tags: tags
  }
  dependsOn: [
    keyVaultModule
    privateDnsModule
  ]
}

// Module: Private Endpoints for Cosmos DB
module cosmosPrivateEndpointModule 'modules/privateendpoint.bicep' = if (deployContainerApps && enablePrivateAccess) {
  name: 'cosmosPrivateEndpointDeployment'
  params: {
    location: location
    privateEndpointName: '${cosmosAccountName}-pe'
    subnetId: vnetModule!.outputs.privateEndpointSubnetId
    serviceResourceId: cosmosModule.outputs.accountId
    groupIds: ['Sql']
    privateDnsZoneIds: [privateDnsModule!.outputs.privateDnsZoneIds.cosmosDb]
    tags: tags
  }
  dependsOn: [
    cosmosModule
    privateDnsModule
  ]
}

// Module: Private Endpoints for Service Bus
module serviceBusPrivateEndpointModule 'modules/privateendpoint.bicep' = if (deployContainerApps && enablePrivateAccess) {
  name: 'serviceBusPrivateEndpointDeployment'
  params: {
    location: location
    privateEndpointName: '${serviceBusNamespaceName}-pe'
    subnetId: vnetModule!.outputs.privateEndpointSubnetId
    serviceResourceId: serviceBusModule.outputs.namespaceResourceId
    groupIds: ['namespace']
    privateDnsZoneIds: [privateDnsModule!.outputs.privateDnsZoneIds.serviceBus]
    tags: tags
  }
  dependsOn: [
    serviceBusModule
    privateDnsModule
  ]
}

// Module: Private Endpoints for Storage Account
module storagePrivateEndpointModule 'modules/privateendpoint.bicep' = if (deployContainerApps && enablePrivateAccess) {
  name: 'storagePrivateEndpointDeployment'
  params: {
    location: location
    privateEndpointName: '${storageAccountName}-pe'
    subnetId: vnetModule!.outputs.privateEndpointSubnetId
    serviceResourceId: storageModule!.outputs.accountId
    groupIds: ['blob']
    privateDnsZoneIds: [privateDnsModule!.outputs.privateDnsZoneIds.blob]
    tags: tags
  }
  dependsOn: [
    storageModule
    privateDnsModule
  ]
}

// Module: Private Endpoints for AI Search (optional, only when using azure_ai_search)
module aiSearchPrivateEndpointModule 'modules/privateendpoint.bicep' = if (deployContainerApps && enablePrivateAccess && vectorStoreBackend == 'azure_ai_search') {
  name: 'aiSearchPrivateEndpointDeployment'
  params: {
    location: location
    privateEndpointName: '${aiSearchServiceName}-pe'
    subnetId: vnetModule!.outputs.privateEndpointSubnetId
    serviceResourceId: aiSearchModule!.outputs.serviceId
    groupIds: ['searchService']
    privateDnsZoneIds: [privateDnsModule!.outputs.privateDnsZoneIds.aiSearch]
    tags: tags
  }
  dependsOn: [
    aiSearchModule
    privateDnsModule
  ]
}

// Calculate redirect URIs for OAuth callback
// If oauthRedirectUris is explicitly provided, use those.
// Otherwise, leave empty array and user must manually configure after deployment.
// The gateway FQDN is only known after Container Apps deployment completes.
var effectiveRedirectUris = length(oauthRedirectUris) > 0 ? oauthRedirectUris : []

// Module: Container Apps (VNet and 10 microservices)
// IMPORTANT: This module uses non-null assertions (!) for outputs from vnetModule
// and Key Vault secrets. These assertions are safe ONLY because this module has the same
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
    identityClientIds: identitiesModule.outputs.identityClientIdsByName
    azureOpenAIEndpoint: azureOpenAIEndpoint
    azureOpenAIGpt4DeploymentName: azureOpenAIGptDeploymentName
    azureOpenAIEmbeddingDeploymentName: azureOpenAIEmbeddingDeploymentName
    azureOpenAIApiKeySecretUri: coreKvSecretUriAoaiKey
    vectorStoreBackend: vectorStoreBackend
    aiSearchEndpoint: vectorStoreBackend == 'azure_ai_search' ? aiSearchModule!.outputs.endpoint : ''
    serviceBusNamespace: serviceBusModule.outputs.namespaceFullyQualifiedName
    cosmosDbEndpoint: cosmosModule.outputs.accountEndpoint
    cosmosAuthDatabaseName: cosmosModule.outputs.authDatabaseName
    cosmosDocumentsDatabaseName: cosmosModule.outputs.documentsDatabaseName
    cosmosContainerName: cosmosModule.outputs.containerName
    cosmosAuthContainerName: cosmosModule.outputs.authContainerName
    cosmosAuthPartitionKeyPath: cosmosModule.outputs.authPartitionKeyPath
    storageAccountName: storageModule!.outputs.accountName
    storageBlobEndpoint: storageModule!.outputs.blobEndpoint
    storageAccountId: storageModule!.outputs.accountId
    enableBlobLogArchiving: enableBlobLogArchiving
    subnetId: vnetModule!.outputs.containerAppsSubnetId
    keyVaultName: keyVaultName
    // Application Insights disabled for cost savings - Log Analytics workspace removed
    appInsightsKeySecretUri: '' // Was: appInsightsInstrKeySecret!.properties.secretUriWithVersion
    appInsightsConnectionStringSecretUri: '' // Was: appInsightsConnectionStringSecret!.properties.secretUriWithVersion
    entraTenantId: entraTenantId
    oauthRedirectUri: length(effectiveRedirectUris) > 0 ? effectiveRedirectUris[0] : ''
    tags: tags
  }
  dependsOn: [
    jwtKeysModule  // Ensure JWT keys are generated before auth service starts
    envOpenaiApiKeySecret
    keyVaultRbacModule  // Ensure RBAC assignments are complete before services access secrets
    coreKvRbacModule  // Ensure Core KV access is granted before Container Apps start
  ]
}

// Module: Microsoft Entra App Registration (for OAuth authentication)
// Requires deployment identity to have Application.ReadWrite.All and Directory.ReadWrite.All
// Graph API permissions. See ENTRA_APP_AUTOMATION.md for setup instructions.
// Note: Deployment skipped if redirect URIs are not provided (length == 0)
module entraAppModule 'modules/entra-app.bicep' = if (deployContainerApps && deployEntraApp && length(effectiveRedirectUris) > 0) {
  name: 'entraAppDeployment'
  params: {
    location: location
    appName: '${projectName}-auth-${environment}'
    tenantId: entraTenantId
    redirectUris: effectiveRedirectUris
    environment: environment
    secretExpirationDays: oauthSecretExpirationDays
    keyVaultName: keyVaultName
    deploymentIdentityId: entraAppIdentity!.id
    tags: tags
  }
  dependsOn: [containerAppsModule, keyVaultModule]
}

// Note: Client ID and secret are stored directly in Key Vault by the entraAppModule deployment script.
// No additional Key Vault secret resources are needed here.

// Outputs
output keyVaultUri string = keyVaultModule.outputs.keyVaultUri
output keyVaultName string = keyVaultModule.outputs.keyVaultName
output managedIdentities array = identitiesModule.outputs.identities
output serviceBusNamespace string = serviceBusModule.outputs.namespaceName
output serviceBusNamespaceId string = serviceBusModule.outputs.namespaceResourceId
output serviceBusTopic string = serviceBusModule.outputs.topicName
output serviceBusSubscriptions array = serviceBusModule.outputs.subscriptionNames
output cosmosAccountName string = cosmosModule.outputs.accountName
output cosmosAccountEndpoint string = cosmosModule.outputs.accountEndpoint
output cosmosAuthDatabaseName string = cosmosModule.outputs.authDatabaseName
output cosmosDocumentsDatabaseName string = cosmosModule.outputs.documentsDatabaseName
output cosmosContainerName string = cosmosModule.outputs.containerName
output cosmosAutoscaleMaxRu int = cosmosModule.outputs.autoscaleMaxThroughput
output cosmosWriteRegions array = cosmosModule.outputs.writeRegions
output cosmosRbacSummary string = cosmosRbacModule.outputs.summary
output storageAccountName string = deployContainerApps ? storageModule!.outputs.accountName : ''
output storageAccountId string = deployContainerApps ? storageModule!.outputs.accountId : ''
output storageBlobEndpoint string = deployContainerApps ? storageModule!.outputs.blobEndpoint : ''
output storageContainerNames array = deployContainerApps ? storageModule!.outputs.containerNames : []
output enableBlobLogArchiving bool = enableBlobLogArchiving
// Azure OpenAI outputs - references to Core RG resources
output coreKeyVaultResourceId string = coreKeyVaultResourceId
output coreKeyVaultName string = coreKeyVaultName
output azureOpenAIEndpoint string = azureOpenAIEndpoint
output azureOpenAIGptDeploymentName string = azureOpenAIGptDeploymentName
output azureOpenAIEmbeddingDeploymentName string = azureOpenAIEmbeddingDeploymentName
// Vector store outputs
output vectorStoreBackend string = vectorStoreBackend
// AI Search outputs: naming follows Azure resource type (Microsoft.Search/searchServices uses "service", not "account")
output aiSearchServiceName string = (deployContainerApps && vectorStoreBackend == 'azure_ai_search') ? aiSearchModule!.outputs.serviceName : ''
output aiSearchEndpoint string = (deployContainerApps && vectorStoreBackend == 'azure_ai_search') ? aiSearchModule!.outputs.endpoint : ''
output aiSearchServiceId string = (deployContainerApps && vectorStoreBackend == 'azure_ai_search') ? aiSearchModule!.outputs.serviceId : ''
// Qdrant outputs
output qdrantAppName string = (deployContainerApps && vectorStoreBackend == 'qdrant') ? containerAppsModule!.outputs.qdrantAppName : ''
output qdrantInternalEndpoint string = (deployContainerApps && vectorStoreBackend == 'qdrant') ? containerAppsModule!.outputs.qdrantInternalEndpoint : ''
// Application Insights outputs disabled - Log Analytics workspace removed for cost savings
// output appInsightsId string = deployContainerApps ? appInsightsModule!.outputs.appInsightsId : ''
// Dashboard outputs disabled - depends on Log Analytics workspace
// output dashboardId string = deployContainerApps ? dashboardModule!.outputs.dashboardId : ''
// output dashboardName string = deployContainerApps ? dashboardModule!.outputs.dashboardName : ''
// output dashboardUrl string = deployContainerApps ? dashboardModule!.outputs.dashboardUrl : ''
output containerAppsEnvId string = deployContainerApps ? containerAppsModule!.outputs.containerAppsEnvId : ''
output gatewayFqdn string = deployContainerApps ? containerAppsModule!.outputs.gatewayFqdn : ''
output githubOAuthRedirectUri string = deployContainerApps ? containerAppsModule!.outputs.githubOAuthRedirectUri : ''
output containerAppIds object = deployContainerApps ? containerAppsModule!.outputs.appIds : {}
output vnetId string = deployContainerApps ? vnetModule!.outputs.vnetId : ''
output entraAppClientId string = (deployContainerApps && deployEntraApp && length(effectiveRedirectUris) > 0) ? entraAppModule!.outputs.clientId : ''
output entraAppTenantId string = (deployContainerApps && deployEntraApp && length(effectiveRedirectUris) > 0) ? entraAppModule!.outputs.tenantId : ''
output entraAppObjectId string = (deployContainerApps && deployEntraApp && length(effectiveRedirectUris) > 0) ? entraAppModule!.outputs.objectId : ''
output oauthRedirectUris array = (deployContainerApps && deployEntraApp && length(effectiveRedirectUris) > 0) ? effectiveRedirectUris : []
output resourceGroupName string = resourceGroup().name
output location string = location
output environment string = environment
output deploymentId string = deployment().name
output keyVaultRbacEnabled bool = enableRbacAuthorization
// Safe to use non-null assertion because keyVaultRbacModule is deployed only when (deployContainerApps && enableRbacAuthorization) is true
// The ternary operator checks the same condition before accessing the output
output keyVaultRbacSummary string = (deployContainerApps && enableRbacAuthorization) ? keyVaultRbacModule!.outputs.summary : 'RBAC not enabled - using legacy access policies (NOT RECOMMENDED for production)'

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


