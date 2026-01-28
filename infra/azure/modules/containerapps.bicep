// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Container Apps environment and all microservices'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for all resources')
param location string

@description('Project name (prefix for resource names)')
param projectName string

@description('Environment name (dev, staging, prod)')
@allowed(['dev', 'staging', 'prod'])
param environment string

@description('Container image registry URL')
param containerRegistry string = 'ghcr.io/alan-jowett/copilot-for-consensus'

@description('Container image tag')
param containerImageTag string = 'latest'

@description('User-assigned managed identity resource IDs by service')
param identityResourceIds object

@description('User-assigned managed identity client IDs by service (required for DefaultAzureCredential to detect user-assigned identity)')
param identityClientIds object

@description('Azure OpenAI endpoint URL')
param azureOpenAIEndpoint string = ''

@description('Azure OpenAI GPT-4o deployment name')
param azureOpenAIGpt4DeploymentName string = ''

@description('Azure OpenAI embedding deployment name')
param azureOpenAIEmbeddingDeploymentName string = ''

@description('Azure OpenAI API key secret URI (from Key Vault)')
param azureOpenAIApiKeySecretUri string = ''

@allowed(['qdrant', 'azure_ai_search'])
@description('Vector store backend to use: qdrant (default) or azure_ai_search')
param vectorStoreBackend string = 'qdrant'

@description('Azure AI Search endpoint URL (only used when vectorStoreBackend is azure_ai_search)')
param aiSearchEndpoint string = ''

@description('Service Bus fully qualified namespace for managed identity connection')
param serviceBusNamespace string = ''

@description('Cosmos DB account endpoint URL for document store connection')
param cosmosDbEndpoint string = ''

@description('Cosmos DB auth database name')
param cosmosAuthDatabaseName string = 'auth'

@description('Cosmos DB documents database name')
param cosmosDocumentsDatabaseName string = 'copilot'

@description('Cosmos DB container name for documents')
param cosmosContainerName string = 'documents'

@description('Cosmos DB container name for auth service (must exist in cosmosAuthDatabaseName)')
param cosmosAuthContainerName string = 'documents'

@description('Cosmos DB partition key path for auth service container (must match provisioned container)')
param cosmosAuthPartitionKeyPath string = '/collection'

@description('Storage Account name for blob storage')
param storageAccountName string = ''

@description('Storage Account blob endpoint URL')
param storageBlobEndpoint string = ''

@description('Storage Account resource ID for diagnostic log archiving')
param storageAccountId string = ''

@description('Enable Blob storage archiving for ACA console logs')
param enableBlobLogArchiving bool = true

@description('Enable Qdrant persistent storage using Azure Files')
param qdrantStorageEnabled bool = false

@description('Azure Files share name for Qdrant storage')
param qdrantStorageShareName string = 'qdrant-storage'

@description('Container Apps subnet ID')
param subnetId string

@description('Key Vault name for secret access')
param keyVaultName string

@description('Application Insights instrumentation key secret URI (from Key Vault)')
param appInsightsKeySecretUri string = ''

@description('Application Insights connection string secret URI (from Key Vault)')
param appInsightsConnectionStringSecretUri string = ''

@description('Microsoft Entra tenant ID for OAuth')
param entraTenantId string = ''

@description('OAuth redirect URI for auth service')
param oauthRedirectUri string = ''

param tags object = {}

// Derived variables
var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var caEnvName = '${projectPrefix}-env-${environment}-${take(uniqueSuffix, 5)}'

// Logging options
// We intentionally do NOT enable Log Analytics (cost).
// To route logs to a Storage Account via Azure Monitor diagnostic settings, the environment must have
// logs destination set to Azure Monitor.
var envBaseProperties = {
  vnetConfiguration: {
    internal: false
    infrastructureSubnetId: subnetId
  }
  workloadProfiles: [
    {
      name: 'Consumption'
      workloadProfileType: 'Consumption'
    }
  ]
}

var envAzureMonitorLogsProperties = (enableBlobLogArchiving && storageAccountId != '') ? {
  appLogsConfiguration: {
    destination: 'azure-monitor'
  }
} : {}

// Scale-to-zero configuration for cost optimization across all environments
// All services now scale to 0 when idle to minimize compute costs
// HTTP services scale based on concurrent requests; Service Bus consumers scale via KEDA
var minReplicaCount = 0

// Service port mappings (internal container listen ports)
// Note: Gateway uses 8080 internally; Container Apps platform handles TLS termination and exposes externally on 443
var servicePorts = {
  auth: 8090
  reporting: 8080
  ingestion: 8001
  parsing: 8000
  chunking: 8000
  embedding: 8000
  orchestrator: 8000
  summarization: 8000
  ui: 80
  gateway: 8080
}

// Compute GitHub OAuth redirect URI based on gateway name pattern
// Format: https://{projectPrefix}-gateway-{environment}.{domain}/ui/callback
// The domain is auto-assigned by Container Apps and includes a unique suffix
// Note: Gateway name is computed below before being assigned to resources

// Container Apps Environment (VNet-integrated, consumption tier for dev)
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2025-01-01' = {
  name: caEnvName
  location: location
  tags: tags
  // NOTE: When enableBlobLogArchiving is false, envAzureMonitorLogsProperties is an empty object,
  // and union(envBaseProperties, {}) intentionally leaves envBaseProperties unchanged.
  properties: union(envBaseProperties, envAzureMonitorLogsProperties)
}

// Azure Files storage for Qdrant persistent storage
// This enables scale-to-zero and ensures vector data persists across restarts/redeploys
// Note: Uses storage account key for authentication (required for Azure Files with Container Apps)
// Managed identity authentication for Azure Files mounts is not yet supported in Container Apps
resource qdrantStorage 'Microsoft.App/managedEnvironments/storages@2025-01-01' = if (vectorStoreBackend == 'qdrant' && qdrantStorageEnabled) {
  parent: containerAppsEnv
  name: 'qdrant-storage'
  properties: {
    azureFile: {
      accountName: storageAccountName
      shareName: qdrantStorageShareName
      accessMode: 'ReadWrite'
      accountKey: listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2023-01-01').keys[0].value
    }
  }
}

// Qdrant Vector Database (port 6333) - Internal service for vector similarity search
// Only deployed when vectorStoreBackend is 'qdrant' (default, lower cost option)
// Deployed before application services that depend on it (embedding, summarization)
// Persistent storage: When qdrantStorageEnabled is true, Azure Files share is mounted to /qdrant/storage
// This enables scale-to-zero and ensures vector data persists across restarts/redeploys
resource qdrantApp 'Microsoft.App/containerApps@2025-01-01' = if (vectorStoreBackend == 'qdrant') {
  name: '${projectPrefix}-qdrant-${environment}'
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false  // Internal-only access
        targetPort: 6333
        // Allow HTTP within the Container Apps environment so services can reach Qdrant
        // via the ingress port (80) without needing TLS configuration in the clients.
        allowInsecure: true
      }
    }
    template: {
      containers: [
        {
          image: 'qdrant/qdrant@sha256:dab6de32f7b2cc599985a7c764db3e8b062f70508fb85ca074aa856f829bf335'
          name: 'qdrant'
          env: [
            {
              name: 'QDRANT__SERVICE__HTTP_PORT'
              value: '6333'
            }
            {
              name: 'QDRANT__SERVICE__GRPC_PORT'
              value: '6334'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
          // Mount Azure Files share for persistent storage when enabled
          volumeMounts: qdrantStorageEnabled ? [
            {
              volumeName: 'qdrant-data'
              mountPath: '/qdrant/storage'
            }
          ] : []
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/'
                port: 6333
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 10
              failureThreshold: 3
            }
          ]
        }
      ]
      // Define volume using Azure Files storage when enabled
      volumes: qdrantStorageEnabled ? [
        {
          name: 'qdrant-data'
          storageType: 'AzureFile'
          storageName: 'qdrant-storage'
        }
      ] : []
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: environment == 'prod' ? 2 : 1
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: qdrantStorageEnabled ? [qdrantStorage] : []
}

// Auth service (port 8090)
resource authApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-auth-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.auth}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.auth
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/auth:${containerImageTag}'
          name: 'auth'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'AUTH_LOG_LEVEL'
              value: 'INFO'
            }
            // Logger adapter
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            // Document Store adapter (Cosmos DB for user roles)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosAuthDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosAuthContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: cosmosAuthPartitionKeyPath
            }
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.auth
            }
            // JWT Signer adapter (Azure Key Vault)
            {
              name: 'JWT_SIGNER_TYPE'
              value: 'keyvault'
            }
            {
              name: 'AZURE_KEY_VAULT_URI'
              value: 'https://${keyVaultName}.vault.azure.net/'
            }
            {
              name: 'JWT_KEY_NAME'
              value: 'jwt-auth-key'
            }
            // Auth service settings
            {
              name: 'AUTH_AUDIENCES'
              value: 'copilot-for-consensus'
            }
            {
              name: 'AUTH_ISSUER'
              value: 'https://${projectPrefix}-auth-${environment}.copilot-for-consensus'
            }
            {
              name: 'AUTH_JWT_ALGORITHM'
              value: 'RS256'
            }
            {
              name: 'AUTH_JWT_DEFAULT_EXPIRY'
              value: '1800'
            }
            {
              name: 'AUTH_JWT_KEY_ID'
              value: 'default'
            }
            {
              name: 'AUTH_MAX_SKEW_SECONDS'
              value: '90'
            }
            {
              name: 'AUTH_REQUIRE_NONCE'
              value: 'true'
            }
            {
              name: 'AUTH_REQUIRE_PKCE'
              value: 'true'
            }
            {
              name: 'AUTH_ENABLE_DPOP'
              value: 'false'
            }
            {
              name: 'AUTH_FIRST_USER_AUTO_PROMOTION_ENABLED'
              value: 'false'
            }
            {
              name: 'AUTH_AUTO_APPROVE_ENABLED'
              value: 'false'
            }
            {
              name: 'AUTH_COOKIE_SECURE'
              value: 'true'
            }
            {
              name: 'AUTH_ROLE_STORE_COLLECTION'
              value: 'user_roles'
            }
            {
              name: 'AUTH_PORT'
              value: string(servicePorts.auth)
            }
            {
              name: 'AUTH_HOST'
              value: '0.0.0.0'
            }
            // OIDC Providers (Microsoft/Entra ID and GitHub)
            {
              name: 'OIDC_PROVIDERS'
              value: 'microsoft,github'
            }
            // Microsoft/Entra ID OIDC Provider
            {
              name: 'MICROSOFT_TENANT'
              value: entraTenantId != '' ? entraTenantId : subscription().tenantId
            }
            {
              name: 'MICROSOFT_REDIRECT_URI'
              value: oauthRedirectUri
            }
            // GitHub OIDC Provider
            {
              name: 'GITHUB_API_BASE_URL'
              value: 'https://api.github.com'
            }
            {
              name: 'GITHUB_REDIRECT_URI'
              value: oauthRedirectUri
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Reporting service (port 8080)
resource reportingApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-reporting-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.reporting}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.reporting
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/reporting:${containerImageTag}'
          name: 'reporting'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'REPORTING_LOG_LEVEL'
              value: 'INFO'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Vector Store adapter (Qdrant or Azure AI Search)
            {
              name: 'VECTOR_STORE_TYPE'
              value: vectorStoreBackend == 'qdrant' ? 'qdrant' : 'azure_ai_search'
            }
            {
              name: 'QDRANT_HOST'
              value: vectorStoreBackend == 'qdrant' ? '${projectPrefix}-qdrant-${environment}' : ''
            }
            {
              name: 'QDRANT_PORT'
              // Container Apps ingress listens on 80/443; targetPort routes to 6333.
              // Clients should use the ingress port, not the container port.
              value: vectorStoreBackend == 'qdrant' ? '80' : ''
            }
            {
              name: 'QDRANT_COLLECTION'
              value: vectorStoreBackend == 'qdrant' ? 'embeddings' : ''
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: vectorStoreBackend == 'azure_ai_search' ? aiSearchEndpoint : ''
            }
            {
              name: 'AZURE_SEARCH_INDEX_NAME'
              value: vectorStoreBackend == 'azure_ai_search' ? 'embeddings' : ''
            }
            // Embedding Backend adapter (Azure OpenAI or SentenceTransformers)
            {
              name: 'EMBEDDING_BACKEND_TYPE'
              value: azureOpenAIEndpoint != '' && azureOpenAIEmbeddingDeploymentName != '' ? 'azure_openai' : 'sentencetransformers'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIEmbeddingDeploymentName
            }
            // Removed AZURE_OPENAI_API_KEY - loaded via secret_provider from Key Vault
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.reporting
            }
            // Reporting service settings
            {
              name: 'REPORTING_HTTP_PORT'
              value: string(servicePorts.reporting)
            }
            {
              name: 'REPORTING_HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'REPORTING_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'REPORTING_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'REPORTING_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            {
              name: 'REPORTING_LOGGER_NAME'
              value: 'reporting'
            }
            {
              name: 'REPORTING_NOTIFY_ENABLED'
              value: 'false'
            }
            {
              name: 'REPORTING_WEBHOOK_SUMMARY_MAX_LENGTH'
              value: '500'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Ingestion service (port 8001)
resource ingestionApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-ingestion-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.ingestion}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.ingestion
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/ingestion:${containerImageTag}'
          name: 'ingestion'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'INGESTION_LOG_LEVEL'
              value: 'INFO'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Archive Store adapter (Azure Blob Storage)
            {
              name: 'ARCHIVE_STORE_TYPE'
              value: 'azureblob'
            }
            {
              name: 'AZUREBLOB_AUTH_TYPE'
              value: 'managed_identity'
            }
            {
              name: 'AZUREBLOB_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'AZUREBLOB_CONTAINER_NAME'
              value: 'raw-archives'
            }
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Logger adapter
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.ingestion
            }
            // Ingestion service settings
            {
              name: 'INGESTION_HTTP_PORT'
              value: string(servicePorts.ingestion)
            }
            {
              name: 'INGESTION_HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'INGESTION_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'INGESTION_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'INGESTION_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'INGESTION_BATCH_SIZE'
              value: '100'
            }
            {
              name: 'INGESTION_CONCURRENT_SOURCES'
              value: '5'
            }
            {
              name: 'INGESTION_ENABLE_INCREMENTAL'
              value: 'true'
            }
            {
              name: 'INGESTION_POLL_INTERVAL_SECONDS'
              value: '3600'
            }
            {
              name: 'INGESTION_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
            {
              name: 'INGESTION_REQUEST_TIMEOUT_SECONDS'
              value: '60'
            }
            {
              name: 'INGESTION_STORAGE_PATH'
              value: '/data/raw_archives'
            }
            {
              name: 'INGESTION_SCHEDULE_INTERVAL_SECONDS'
              value: '21600'
            }
          ]
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/health'
                port: servicePorts.ingestion
              }
              initialDelaySeconds: 15
              periodSeconds: 30
              timeoutSeconds: 10
              failureThreshold: 3
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [authApp]
}

// Parsing service (port 8000)
resource parsingApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-parsing-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.parsing}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.parsing
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/parsing:${containerImageTag}'
          name: 'parsing'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'PARSING_LOG_LEVEL'
              value: 'INFO'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Archive Store adapter (Azure Blob Storage)
            {
              name: 'ARCHIVE_STORE_TYPE'
              value: 'azureblob'
            }
            {
              name: 'AZUREBLOB_AUTH_TYPE'
              value: 'managed_identity'
            }
            {
              name: 'AZUREBLOB_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'AZUREBLOB_CONTAINER_NAME'
              value: 'raw-archives'
            }
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.parsing
            }
            // Parsing service settings
            {
              name: 'PARSING_HTTP_PORT'
              value: string(servicePorts.parsing)
            }
            {
              name: 'PARSING_HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'PARSING_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'PARSING_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'PARSING_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            {
              name: 'PARSING_LOGGER_NAME'
              value: 'parsing'
            }
            {
              name: 'PARSING_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
            {
              name: 'PARSING_RETRY_DELAY_SECONDS'
              value: '5'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              identity: identityResourceIds.parsing
              metadata: {
                topicName: 'copilot.events'
                subscriptionName: 'parsing'
                messageCount: '5'
                activationMessageCount: '1'
                namespace: serviceBusNamespace
              }
              // Authentication: KEDA uses the parsing service's user-assigned managed identity
              // The identity has Azure Service Bus Data Receiver role assigned via servicebus.bicep
            }
          }
        ]
      }
    }
  }
  dependsOn: [authApp]
}

// Chunking service (port 8000)
resource chunkingApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-chunking-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.chunking}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.chunking
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/chunking:${containerImageTag}'
          name: 'chunking'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'CHUNK_LOG_LEVEL'
              value: 'INFO'
            }
            // Event retry adapter
            {
              name: 'EVENT_RETRY_TYPE'
              value: 'default'
            }
            // Logger adapter
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.chunking
            }
            // Chunking service settings
            {
              name: 'CHUNK_HTTP_PORT'
              value: string(servicePorts.chunking)
            }
            {
              name: 'CHUNK_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'CHUNK_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'CHUNK_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'CHUNK_SIZE_TOKENS'
              value: '384'
            }
            {
              name: 'CHUNK_OVERLAP_TOKENS'
              value: '50'
            }
            {
              name: 'CHUNKER_TYPE'
              value: 'token_window'
            }
            {
              name: 'CHUNK_MIN_SIZE_TOKENS'
              value: '100'
            }
            {
              name: 'CHUNK_MAX_SIZE_TOKENS'
              value: '512'
            }
            {
              name: 'CHUNK_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              identity: identityResourceIds.chunking
              metadata: {
                topicName: 'copilot.events'
                subscriptionName: 'chunking'
                messageCount: '5'
                activationMessageCount: '1'
                namespace: serviceBusNamespace
              }
              // Authentication: KEDA uses the chunking service's user-assigned managed identity
              // The identity has Azure Service Bus Data Receiver role assigned via servicebus.bicep
            }
          }
        ]
      }
    }
  }
  dependsOn: [authApp]
}

// Embedding service (port 8000)
resource embeddingApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-embedding-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.embedding}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.embedding
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/embedding:${containerImageTag}'
          name: 'embedding'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'EMBEDDING_LOG_LEVEL'
              value: 'INFO'
            }
            // Event retry adapter
            {
              name: 'EVENT_RETRY_TYPE'
              value: 'default'
            }
            // Logger adapter
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Vector Store adapter (Qdrant or Azure AI Search)
            {
              name: 'VECTOR_STORE_TYPE'
              value: vectorStoreBackend == 'qdrant' ? 'qdrant' : 'azure_ai_search'
            }
            {
              name: 'QDRANT_HOST'
              value: vectorStoreBackend == 'qdrant' ? '${projectPrefix}-qdrant-${environment}' : ''
            }
            {
              name: 'QDRANT_PORT'
              // Container Apps ingress listens on 80/443; targetPort routes to 6333.
              // Clients should use the ingress port, not the container port.
              value: vectorStoreBackend == 'qdrant' ? '80' : ''
            }
            {
              name: 'QDRANT_COLLECTION'
              value: vectorStoreBackend == 'qdrant' ? 'embeddings' : ''
            }
            {
              name: 'QDRANT_DISTANCE'
              value: vectorStoreBackend == 'qdrant' ? 'cosine' : ''
            }
            {
              name: 'QDRANT_UPSERT_BATCH_SIZE'
              value: vectorStoreBackend == 'qdrant' ? '100' : ''
            }
            {
              name: 'EMBEDDING_DIMENSION'
              value: '384'
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: vectorStoreBackend == 'azure_ai_search' ? aiSearchEndpoint : ''
            }
            {
              name: 'AZURE_SEARCH_INDEX_NAME'
              value: vectorStoreBackend == 'azure_ai_search' ? 'embeddings' : ''
            }
            // Embedding Backend adapter (Azure OpenAI or SentenceTransformers)
            {
              name: 'EMBEDDING_BACKEND_TYPE'
              value: azureOpenAIEndpoint != '' && azureOpenAIEmbeddingDeploymentName != '' ? 'azure_openai' : 'sentencetransformers'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIEmbeddingDeploymentName
            }
            // Removed AZURE_OPENAI_API_KEY - loaded via secret_provider from Key Vault
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.embedding
            }
            // Embedding service settings
            {
              name: 'EMBEDDING_HTTP_PORT'
              value: string(servicePorts.embedding)
            }
            {
              name: 'EMBEDDING_HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'EMBEDDING_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'EMBEDDING_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'EMBEDDING_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'EMBEDDING_BATCH_SIZE'
              value: '32'
            }
            {
              name: 'EMBEDDING_ENABLE_CACHE'
              value: 'true'
            }
            {
              name: 'EMBEDDING_CACHE_TTL_SECONDS'
              value: '86400'
            }
            {
              name: 'EMBEDDING_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
            {
              name: 'EMBEDDING_RETRY_BACKOFF_SECONDS'
              value: '5'
            }
            {
              name: 'EMBEDDING_REQUEST_TIMEOUT_SECONDS'
              value: '30'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              identity: identityResourceIds.embedding
              metadata: {
                topicName: 'copilot.events'
                subscriptionName: 'embedding'
                messageCount: '5'
                activationMessageCount: '1'
                namespace: serviceBusNamespace
              }
              // Authentication: KEDA uses the embedding service's user-assigned managed identity
              // The identity has Azure Service Bus Data Receiver role assigned via servicebus.bicep
            }
          }
        ]
      }
    }
  }
  dependsOn: vectorStoreBackend == 'qdrant' ? [authApp, qdrantApp] : [authApp]
}

// Orchestrator service (port 8000)
resource orchestratorApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-orchestrator-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.orchestrator}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.orchestrator
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/orchestrator:${containerImageTag}'
          name: 'orchestrator'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'ORCHESTRATOR_LOG_LEVEL'
              value: 'INFO'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.orchestrator
            }
            // Consensus detector adapter
            {
              name: 'CONSENSUS_DETECTOR_TYPE'
              value: 'heuristic'
            }
            // Embedding backend adapter
            {
              name: 'EMBEDDING_BACKEND_TYPE'
              value: 'sentencetransformers'
            }
            // Vector store adapter (Qdrant)
            {
              name: 'VECTOR_STORE_TYPE'
              value: 'qdrant'
            }
            {
              name: 'QDRANT_HOST'
              value: '${projectPrefix}-qdrant-${environment}'
            }
            {
              name: 'QDRANT_PORT'
              // Container Apps ingress listens on 80/443; targetPort routes to 6333.
              // Clients should use the ingress port, not the container port.
              value: '80'
            }
            {
              name: 'QDRANT_COLLECTION'
              value: 'embeddings'
            }
            // LLM Backend adapter (Azure OpenAI)
            {
              name: 'LLM_BACKEND_TYPE'
              value: 'azure_openai_gpt'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIGpt4DeploymentName
            }
            // Removed AZURE_OPENAI_API_KEY - loaded via secret_provider from Key Vault
            // Orchestrator service settings
            {
              name: 'ORCHESTRATOR_HTTP_PORT'
              value: string(servicePorts.orchestrator)
            }
            {
              name: 'ORCHESTRATOR_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'ORCHESTRATOR_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'ORCHESTRATOR_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'ORCHESTRATOR_CONSENSUS_TIMEOUT_SECONDS'
              value: '300'
            }
            {
              name: 'ORCHESTRATOR_MAX_PARALLEL_REVIEWS'
              value: '10'
            }
            {
              name: 'ORCHESTRATOR_TOP_K'
              value: '5'
            }
            {
              name: 'ORCHESTRATOR_CONTEXT_WINDOW_TOKENS'
              value: '2048'
            }
            {
              name: 'ORCHESTRATOR_LLM_TEMPERATURE'
              value: '0.7'
            }
            {
              name: 'ORCHESTRATOR_LLM_MAX_TOKENS'
              value: '1024'
            }
            {
              name: 'ORCHESTRATOR_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            {
              name: 'ORCHESTRATOR_LOGGER_NAME'
              value: 'orchestrator'
            }
            {
              name: 'ORCHESTRATOR_REQUEST_TIMEOUT_SECONDS'
              value: '60'
            }
            {
              name: 'ORCHESTRATOR_WORKFLOW_HISTORY_RETENTION_DAYS'
              value: '90'
            }
            {
              name: 'ORCHESTRATOR_LLM_MODEL'
              value: 'gpt-4'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              identity: identityResourceIds.orchestrator
              metadata: {
                topicName: 'copilot.events'
                subscriptionName: 'orchestrator'
                messageCount: '5'
                activationMessageCount: '1'
                namespace: serviceBusNamespace
              }
              // Authentication: KEDA uses the orchestrator service's user-assigned managed identity
              // The identity has Azure Service Bus Data Receiver role assigned via servicebus.bicep
            }
          }
        ]
      }
    }
  }
  dependsOn: [authApp]
}

// Summarization service (port 8000)
resource summarizationApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-summarization-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.summarization}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.summarization
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/summarization:${containerImageTag}'
          name: 'summarization'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'SUMMARIZATION_LOG_LEVEL'
              value: 'INFO'
            }
            // Message Bus adapter (Azure Service Bus)
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azure_service_bus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            // Document Store adapter (Cosmos DB)
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'azure_cosmosdb'
            }
            {
              name: 'COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosDocumentsDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: cosmosContainerName
            }
            {
              name: 'COSMOS_PARTITION_KEY'
              value: '/collection'
            }
            // Vector Store adapter (Qdrant or Azure AI Search)
            {
              name: 'VECTOR_STORE_TYPE'
              value: vectorStoreBackend == 'qdrant' ? 'qdrant' : 'azure_ai_search'
            }
            {
              name: 'QDRANT_HOST'
              value: vectorStoreBackend == 'qdrant' ? '${projectPrefix}-qdrant-${environment}' : ''
            }
            {
              name: 'QDRANT_PORT'
              // Container Apps ingress listens on 80/443; targetPort routes to 6333.
              // Clients should use the ingress port, not the container port.
              value: vectorStoreBackend == 'qdrant' ? '80' : ''
            }
            {
              name: 'QDRANT_COLLECTION'
              value: vectorStoreBackend == 'qdrant' ? 'embeddings' : ''
            }
            {
              name: 'QDRANT_DISTANCE'
              value: vectorStoreBackend == 'qdrant' ? 'cosine' : ''
            }
            {
              name: 'QDRANT_UPSERT_BATCH_SIZE'
              value: vectorStoreBackend == 'qdrant' ? '100' : ''
            }
            {
              name: 'AZURE_SEARCH_ENDPOINT'
              value: vectorStoreBackend == 'azure_ai_search' ? aiSearchEndpoint : ''
            }
            {
              name: 'AZURE_SEARCH_INDEX_NAME'
              value: vectorStoreBackend == 'azure_ai_search' ? 'embeddings' : ''
            }
            {
              name: 'EMBEDDING_DIMENSION'
              value: '384'
            }
            // Embedding Backend adapter (Azure OpenAI)
            {
              name: 'EMBEDDING_BACKEND_TYPE'
              value: 'azure_openai'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIEmbeddingDeploymentName
            }
            // LLM Backend adapter (Azure OpenAI)
            {
              name: 'LLM_BACKEND_TYPE'
              value: 'azure_openai_gpt'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIGpt4DeploymentName
            }
            {
              name: 'LLM_MODEL'
              value: 'gpt-4'
            }
            {
              name: 'AZURE_OPENAI_API_VERSION'
              value: '2024-02-15-preview'
            }
            // Removed AZURE_OPENAI_API_KEY - loaded via secret_provider from Key Vault
            // Metrics adapter (Azure Monitor)
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            // Removed APPINSIGHTS_INSTRUMENTATIONKEY and APPLICATIONINSIGHTS_CONNECTION_STRING
            // These secrets are loaded via secret_provider from Key Vault using schema secret_name
            // Error reporter adapter
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            // Secret Provider adapter (Azure Key Vault)
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azure_key_vault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.summarization
            }
            // Summarization service settings
            {
              name: 'SUMMARIZATION_HTTP_PORT'
              value: string(servicePorts.summarization)
            }
            {
              name: 'SUMMARIZATION_JWT_AUTH_ENABLED'
              value: 'true'
            }
            {
              name: 'SUMMARIZATION_AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'SUMMARIZATION_SERVICE_AUDIENCE'
              value: 'copilot-for-consensus'
            }
            {
              name: 'LOG_TYPE'
              value: 'stdout'
            }
            {
              name: 'SUMMARIZATION_LOGGER_NAME'
              value: 'summarization'
            }
            {
              name: 'SUMMARIZATION_RETRY_MAX_ATTEMPTS'
              value: '3'
            }
            {
              name: 'SUMMARIZATION_RETRY_DELAY_SECONDS'
              value: '5'
            }
            {
              name: 'SUMMARIZATION_TOP_K'
              value: '12'
            }
            {
              name: 'SUMMARIZATION_CITATION_COUNT'
              value: '12'
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'servicebus-scaling'
            custom: {
              type: 'azure-servicebus'
              identity: identityResourceIds.summarization
              metadata: {
                topicName: 'copilot.events'
                subscriptionName: 'summarization'
                messageCount: '5'
                activationMessageCount: '1'
                namespace: serviceBusNamespace
              }
              // Authentication: KEDA uses the summarization service's user-assigned managed identity
              // The identity has Azure Service Bus Data Receiver role assigned via servicebus.bicep
            }
          }
        ]
      }
    }
  }
  dependsOn: vectorStoreBackend == 'qdrant' ? [authApp, qdrantApp] : [authApp]
}

// UI service (port 3000)
resource uiApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-ui-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.ui}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: false
        targetPort: servicePorts.ui
        allowInsecure: false
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/ui:${containerImageTag}'
          name: 'ui'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'REACT_APP_API_BASE_URL'
              value: '/api'
            }
            {
              name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
              value: appInsightsKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsKeySecretUri})' : ''
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionStringSecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsConnectionStringSecretUri})' : ''
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 2
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
}

// Gateway service (port 443, external ingress only)
resource gatewayApp 'Microsoft.App/containerApps@2025-01-01' = {
  name: '${projectPrefix}-gateway-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.gateway}': {}
    }
  }
  properties: {
    managedEnvironmentId: containerAppsEnv.id
    workloadProfileName: 'Consumption'
    configuration: {
      ingress: {
        external: true
        targetPort: servicePorts.gateway
        allowInsecure: false
        transport: 'http'
      }
    }
    template: {
      containers: [
        {
          image: '${containerRegistry}/gateway:${containerImageTag}'
          name: 'gateway'
          env: [
            {
              name: 'SERVICE_VERSION'
              value: '0.1.0'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'REPORTING_BACKEND'
              value: 'http://${projectPrefix}-reporting-${environment}'
            }
            {
              name: 'AUTH_BACKEND'
              value: 'http://${projectPrefix}-auth-${environment}'
            }
            {
              name: 'INGESTION_BACKEND'
              value: 'http://${projectPrefix}-ingestion-${environment}'
            }
            {
              name: 'UI_BACKEND'
              value: 'http://${projectPrefix}-ui-${environment}'
            }
            {
              name: 'ENABLE_INTERNAL_TLS'
              value: 'false'
            }
            // Gateway diagnostics toggles (used by infra/nginx/nginx.conf.template)
            // Defaults preserve existing behavior unless explicitly enabled.
            {
              name: 'CFC_GATEWAY_LOG_RESPONSES'
              value: '0'
            }
            {
              name: 'CFC_GATEWAY_GZIP'
              value: 'on'
            }
            {
              name: 'CFC_GATEWAY_ERROR_LOG_LEVEL'
              value: 'warn'
            }
            {
              name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
              value: appInsightsKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsKeySecretUri})' : ''
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              value: appInsightsConnectionStringSecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${appInsightsConnectionStringSecretUri})' : ''
            }
          ]
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: 3
        rules: [
          {
            name: 'http-scaling'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  dependsOn: [reportingApp, authApp, ingestionApp, uiApp]
}

// Diagnostic Settings - Archive Container Apps Environment logs to Storage via Azure Monitor
// Note: diagnostic log categories are supported at the managedEnvironment scope, not per container app.
// Prereq: containerAppsEnv.properties.appLogsConfiguration.destination must be set to 'azure-monitor'.
module envDiagnostics 'diagnosticsettings.bicep' = if (enableBlobLogArchiving && storageAccountId != '') {
  name: 'containerAppsEnvDiagnosticsDeployment'
  params: {
    managedEnvironmentName: containerAppsEnv.name
    storageAccountId: storageAccountId
    enableConsoleLogs: true
    enableSystemLogs: true
  }
  dependsOn: [
    containerAppsEnv
  ]
}

// Outputs
@description('Container Apps Environment ID')
output containerAppsEnvId string = containerAppsEnv.id

@description('Gateway FQDN for external access')
output gatewayFqdn string = gatewayApp.properties.configuration.ingress.fqdn

@description('GitHub OAuth redirect URI (computed from gateway FQDN)')
output githubOAuthRedirectUri string = 'https://${gatewayApp.properties.configuration.ingress.fqdn}/ui/callback'

@description('Container App resource IDs by service')
output appIds object = vectorStoreBackend == 'qdrant' ? {
  auth: authApp.id
  reporting: reportingApp.id
  ingestion: ingestionApp.id
  parsing: parsingApp.id
  chunking: chunkingApp.id
  embedding: embeddingApp.id
  orchestrator: orchestratorApp.id
  summarization: summarizationApp.id
  ui: uiApp.id
  gateway: gatewayApp.id
  qdrant: qdrantApp!.id
} : {
  auth: authApp.id
  reporting: reportingApp.id
  ingestion: ingestionApp.id
  parsing: parsingApp.id
  chunking: chunkingApp.id
  embedding: embeddingApp.id
  orchestrator: orchestratorApp.id
  summarization: summarizationApp.id
  ui: uiApp.id
  gateway: gatewayApp.id
}

@description('Qdrant vector database app name')
output qdrantAppName string = vectorStoreBackend == 'qdrant' ? qdrantApp!.name : ''

@description('Qdrant internal endpoint')
output qdrantInternalEndpoint string = vectorStoreBackend == 'qdrant' ? 'http://${qdrantApp!.name}' : ''


