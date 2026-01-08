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

@description('Storage Account name for blob storage')
param storageAccountName string = ''

@description('Storage Account blob endpoint URL')
param storageBlobEndpoint string = ''

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

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Log Analytics workspace customerId (GUID)')
param logAnalyticsCustomerId string

param tags object = {}

// Derived variables
var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var caEnvName = '${projectPrefix}-env-${environment}-${take(uniqueSuffix, 5)}'

// Scale-to-zero configuration for cost optimization in dev environment
// Dev: minReplicas = 1 (keep running during debugging to see startup failures)
// Staging/Prod: minReplicas = 1 (maintain at least one replica for faster response times)
var minReplicaCount = 1

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
var githubOAuthRedirectUriBase = 'https://${projectPrefix}-gateway-${environment}'

// Container Apps Environment (VNet-integrated, consumption tier for dev)
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: caEnvName
  location: location
  tags: tags
  properties: {
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
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: listKeys(logAnalyticsWorkspaceId, '2021-12-01-preview').primarySharedKey
      }
    }
  }
}

// Qdrant Vector Database (port 6333) - Internal service for vector similarity search
// Only deployed when vectorStoreBackend is 'qdrant' (default, lower cost option)
// Deployed before application services that depend on it (embedding, summarization)
// Note: Currently configured without persistent storage, suitable for development/ephemeral use.
// For production with persistent vector data, consider adding Azure Files volume mount.
// See: https://learn.microsoft.com/en-us/azure/container-apps/storage-mounts
resource qdrantApp 'Microsoft.App/containerApps@2024-03-01' = if (vectorStoreBackend == 'qdrant') {
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
        allowInsecure: false
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
      scale: {
        minReplicas: minReplicaCount
        maxReplicas: environment == 'prod' ? 2 : 1
      }
    }
  }
}

// Auth service (port 8090)
resource authApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'JWT_ALGORITHM'
              value: 'RS256'
            }
            {
              name: 'SECRET_PROVIDER_TYPE'
              value: 'azurekeyvault'
            }
            {
              name: 'AZURE_KEY_VAULT_NAME'
              value: keyVaultName
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.auth
            }
            {
              name: 'AUTH_MS_TENANT'
              value: entraTenantId != '' ? entraTenantId : subscription().tenantId
            }
            {
              name: 'AUTH_MS_REDIRECT_URI'
              value: oauthRedirectUri
            }
            {
              name: 'AUTH_ROLE_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'AUTH_COSMOS_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'AUTH_COSMOS_PORT'
              value: '443'
            }
            {
              name: 'AUTH_COSMOS_DATABASE'
              value: cosmosAuthDatabaseName
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
              value: cosmosDbEndpoint
            }
            {
              name: 'COSMOS_DATABASE'
              value: cosmosAuthDatabaseName
            }
            {
              name: 'COSMOS_CONTAINER'
              value: 'documents'
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
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

// Reporting service (port 8080)
resource reportingApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.reporting
            }
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
              value: '80'
            }
            {
              name: 'QDRANT_COLLECTION'
              value: 'embeddings'
            }
            {
              name: 'EMBEDDING_BACKEND'
              value: azureOpenAIEndpoint != '' && azureOpenAIEmbeddingDeploymentName != '' ? 'azure' : 'sentencetransformers'
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
}

// Ingestion service (port 8001)
resource ingestionApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.ingestion
            }
            {
              name: 'STORAGE_PATH'
              value: '/data/raw_archives'
            }
            {
              name: 'ARCHIVE_STORE_TYPE'
              value: 'azure_blob'
            }
            {
              name: 'LOCAL_LOCAL_ARCHIVE_STORE_PATH'
              value: '/data/raw_archives'
            }
            {
              name: 'AZUREBLOB_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'AZUREBLOB_CONTAINER'
              value: 'raw-archives'
            }
            {
              name: 'AZUREBLOB_ACCOUNT'
              value: storageAccountName
            }
            {
              name: 'AZUREBLOB_ENDPOINT'
              value: storageBlobEndpoint
            }
            {
              name: 'AZUREBLOB_STORAGE_CONTAINER'
              value: 'raw-archives'
            }
            {
              name: 'HTTP_PORT'
              value: string(servicePorts.ingestion)
            }
            {
              name: 'HTTP_HOST'
              value: '0.0.0.0'
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: [authApp]
}

// Parsing service (port 8000)
resource parsingApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.parsing
            }
            {
              name: 'ARCHIVE_STORE_TYPE'
              value: 'azure_blob'
            }
            {
              name: 'LOCAL_LOCAL_ARCHIVE_STORE_PATH'
              value: '/data/raw_archives'
            }
            {
              name: 'AZUREBLOB_ACCOUNT_NAME'
              value: storageAccountName
            }
            {
              name: 'AZUREBLOB_CONTAINER'
              value: 'raw-archives'
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: [authApp]
}

// Chunking service (port 8000)
resource chunkingApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.chunking
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: [authApp]
}

// Embedding service (port 8000)
resource embeddingApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.embedding
            }
            {
              name: 'VECTOR_STORE_TYPE'
              value: vectorStoreBackend == 'qdrant' ? 'qdrant' : 'ai_search'
            }
            {
              name: 'QDRANT_HOST'
              value: vectorStoreBackend == 'qdrant' ? '${projectPrefix}-qdrant-${environment}' : ''
            }
            {
              name: 'QDRANT_PORT'
              value: vectorStoreBackend == 'qdrant' ? '80' : ''
            }
            {
              name: 'QDRANT_COLLECTION'
              value: vectorStoreBackend == 'qdrant' ? 'document-embeddings' : ''
            }
            {
              name: 'VECTOR_DB_DISTANCE'
              value: vectorStoreBackend == 'qdrant' ? 'cosine' : ''
            }
            {
              name: 'VECTOR_DB_SENTENCETRANSFORMERS_SENTENCETRANSFORMERS_BATCH_SIZE'
              value: vectorStoreBackend == 'qdrant' ? '100' : ''
            }
            {
              name: 'AISEARCH_ENDPOINT'
              value: vectorStoreBackend == 'azure_ai_search' ? aiSearchEndpoint : ''
            }
            {
              name: 'AISEARCH_INDEX_NAME'
              value: vectorStoreBackend == 'azure_ai_search' ? 'document-embeddings' : ''
            }
            {
              name: 'EMBEDDING_BACKEND'
              value: azureOpenAIEndpoint != '' && azureOpenAIEmbeddingDeploymentName != '' ? 'azure' : 'sentencetransformers'
            }
            {
              name: 'SENTENCETRANSFORMERS_DIMENSION'
              value: '384'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AZURE_OPENAI_DEPLOYMENT'
              value: azureOpenAIEmbeddingDeploymentName
            }
            {
              name: 'AZURE_OPENAI_API_KEY'
              value: azureOpenAIApiKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${azureOpenAIApiKeySecretUri})' : ''
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: vectorStoreBackend == 'qdrant' ? [authApp, qdrantApp] : [authApp]
}

// Orchestrator service (port 8000)
resource orchestratorApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.orchestrator
            }
            {
              name: 'LLM_BACKEND'
              value: 'azure'
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
              name: 'AZURE_OPENAI_API_KEY'
              value: azureOpenAIApiKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${azureOpenAIApiKeySecretUri})' : ''
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: [authApp]
}

// Summarization service (port 8000)
resource summarizationApp 'Microsoft.App/containerApps@2024-03-01' = {
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
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'METRICS_TYPE'
              value: 'azure_monitor'
            }
            {
              name: 'ERROR_REPORTER_TYPE'
              value: 'console'
            }
            {
              name: 'MESSAGE_BUS_TYPE'
              value: 'azureservicebus'
            }
            {
              name: 'SERVICEBUS_USE_MANAGED_IDENTITY'
              value: 'true'
            }
            {
              name: 'SERVICEBUS_FULLY_QUALIFIED_NAMESPACE'
              value: serviceBusNamespace
            }
            {
              name: 'DOCUMENT_STORE_TYPE'
              value: 'cosmos'
            }
            {
              name: 'COSMOS_DB_ENDPOINT'
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
              name: 'AZURE_CLIENT_ID'
              value: identityClientIds.summarization
            }
            {
              name: 'VECTOR_STORE_TYPE'
              value: vectorStoreBackend == 'qdrant' ? 'qdrant' : 'ai_search'
            }
            {
              name: 'QDRANT_HOST'
              value: vectorStoreBackend == 'qdrant' ? '${projectPrefix}-qdrant-${environment}' : ''
            }
            {
              name: 'QDRANT_PORT'
              value: vectorStoreBackend == 'qdrant' ? '80' : ''
            }
            {
              name: 'QDRANT_COLLECTION'
              value: vectorStoreBackend == 'qdrant' ? 'document-embeddings' : ''
            }
            {
              name: 'VECTOR_DB_DISTANCE'
              value: vectorStoreBackend == 'qdrant' ? 'cosine' : ''
            }
            {
              name: 'VECTOR_DB_SENTENCETRANSFORMERS_SENTENCETRANSFORMERS_BATCH_SIZE'
              value: vectorStoreBackend == 'qdrant' ? '100' : ''
            }
            {
              name: 'AISEARCH_ENDPOINT'
              value: vectorStoreBackend == 'azure_ai_search' ? aiSearchEndpoint : ''
            }
            {
              name: 'AISEARCH_INDEX_NAME'
              value: vectorStoreBackend == 'azure_ai_search' ? 'document-embeddings' : ''
            }
            {
              name: 'SENTENCETRANSFORMERS_DIMENSION'
              value: '384'
            }
            {
              name: 'LLM_BACKEND'
              value: 'azure'
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
              name: 'AZURE_OPENAI_API_KEY'
              value: azureOpenAIApiKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${azureOpenAIApiKeySecretUri})' : ''
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}'
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
      }
    }
  }
  dependsOn: vectorStoreBackend == 'qdrant' ? [authApp, qdrantApp] : [authApp]
}

// UI service (port 3000)
resource uiApp 'Microsoft.App/containerApps@2024-03-01' = {
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
      }
    }
  }
}

// Gateway service (port 443, external ingress only)
resource gatewayApp 'Microsoft.App/containerApps@2024-03-01' = {
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
      }
    }
  }
  dependsOn: [reportingApp, authApp, ingestionApp, uiApp]
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

