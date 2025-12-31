// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Container Apps environment and all microservices'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for all resources')
param location string

@description('Project name (prefix for resource names)')
param projectName string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Container image registry URL')
param containerRegistry string = 'ghcr.io/alan-jowett/copilot-for-consensus'

@description('Container image tag')
param containerImageTag string = 'latest'

@description('User-assigned managed identity resource IDs by service')
param identityResourceIds object

@description('Azure OpenAI endpoint URL')
param azureOpenAIEndpoint string = ''

@description('Azure AI Search endpoint URL')
param aiSearchEndpoint string = ''

@description('Service Bus namespace name for message bus connection')
param serviceBusNamespace string = ''

@description('Cosmos DB account endpoint URL for document store connection')
param cosmosDbEndpoint string = ''

@description('Container Apps subnet ID')
param subnetId string

@description('Key Vault secret URI for JWT private key (RS256)')
param jwtPrivateKeySecretUri string = ''

@description('Key Vault secret URI for JWT public key (RS256)')
param jwtPublicKeySecretUri string = ''

@description('Application Insights instrumentation key secret URI (from Key Vault)')
param appInsightsKeySecretUri string = ''

@description('Application Insights connection string secret URI (from Key Vault)')
param appInsightsConnectionStringSecretUri string = ''

@description('Log Analytics workspace resource ID')
param logAnalyticsWorkspaceId string

@description('Log Analytics workspace customerId (GUID)')
param logAnalyticsCustomerId string

param tags object = {}

// Derived variables
var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var caEnvName = '${projectPrefix}-env-${environment}-${take(uniqueSuffix, 5)}'

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
  ui: 3000
  gateway: 8080
}

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
              name: 'JWT_ALGORITHM'
              value: 'RS256'
            }
            {
              name: 'JWT_PRIVATE_KEY'
              value: jwtPrivateKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${jwtPrivateKeySecretUri})' : ''
            }
            {
              name: 'JWT_PUBLIC_KEY'
              value: jwtPublicKeySecretUri != '' ? '@Microsoft.KeyVault(SecretUri=${jwtPublicKeySecretUri})' : ''
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'STORAGE_PATH'
              value: '/data/raw_archives'
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'VECTORSTORE_TYPE'
              value: 'ai_search'
            }
            {
              name: 'AISEARCH_ENDPOINT'
              value: aiSearchEndpoint
            }
            {
              name: 'AISEARCH_INDEX_NAME'
              value: 'document-embeddings'
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('1')
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  dependsOn: [authApp]
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
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
              name: 'MESSAGE_BUS_TYPE'
              value: 'service_bus'
            }
            {
              name: 'SERVICE_BUS_NAMESPACE'
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
              name: 'LLM_BACKEND'
              value: 'azure'
            }
            {
              name: 'AZURE_OPENAI_ENDPOINT'
              value: azureOpenAIEndpoint
            }
            {
              name: 'AUTH_SERVICE_URL'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
      }
    }
  }
  dependsOn: [authApp]
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
        minReplicas: 1
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
        transport: 'auto'
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
              name: 'UPSTREAM_AUTH'
              value: 'http://${projectPrefix}-auth-${environment}:${servicePorts.auth}'
            }
            {
              name: 'UPSTREAM_REPORTING'
              value: 'http://${projectPrefix}-reporting-${environment}:${servicePorts.reporting}'
            }
            {
              name: 'UPSTREAM_INGESTION'
              value: 'http://${projectPrefix}-ingestion-${environment}:${servicePorts.ingestion}'
            }
            {
              name: 'UPSTREAM_UI'
              value: 'http://${projectPrefix}-ui-${environment}:${servicePorts.ui}'
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
            cpu: json('0.5')
            memory: '1Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
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

@description('Container App resource IDs by service')
output appIds object = {
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

