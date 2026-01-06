// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

/*
  Azure Functions App for Message Consumer Services
  
  This module provisions an Azure Functions App (Consumption Plan) for event-driven
  message consumer services like chunking, parsing, embedding, orchestrator, and summarization.
  
  Key Features:
  - Consumption Plan for pay-per-execution pricing
  - Service Bus trigger bindings for automatic message processing
  - Managed Identity for secure access to Azure resources
  - Application Insights integration for monitoring
  - Scale-to-zero when idle
  - Automatic scaling based on queue depth
*/

@description('Project name prefix for all resources')
param projectName string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Azure region for resources')
param location string = resourceGroup().location

@description('Tags to apply to all resources')
param tags object = {}

@description('Storage Account ID for function app storage')
param storageAccountId string

@description('Application Insights Connection String')
param appInsightsConnectionString string

@description('Service Bus Namespace name')
param serviceBusNamespaceName string

@description('Cosmos DB Account name')
param cosmosAccountName string

@description('Azure AI Search endpoint')
param aiSearchEndpoint string

@description('Managed Identity ID for the function app')
param managedIdentityId string

@description('Key Vault name for secrets')
param keyVaultName string

// Function App Plan (Consumption)
resource functionAppPlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: '${projectName}-funcplan-${environment}'
  location: location
  tags: tags
  sku: {
    name: 'Y1'  // Consumption Plan
    tier: 'Dynamic'
  }
  properties: {
    reserved: true  // Required for Linux
  }
  kind: 'linux'
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: '${projectName}-func-${environment}'
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${managedIdentityId}': {}
    }
  }
  properties: {
    serverFarmId: functionAppPlan.id
    reserved: true
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      appSettings: [
        {
          name: 'AzureWebJobsStorage__accountName'
          value: split(storageAccountId, '/')[8]  // Extract account name from resource ID
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: appInsightsConnectionString
        }
        {
          name: 'AzureWebJobsServiceBus__fullyQualifiedNamespace'
          value: '${serviceBusNamespaceName}.servicebus.windows.net'
        }
        {
          name: 'AzureWebJobsServiceBus__credential'
          value: 'managedidentity'
        }
        {
          name: 'AzureWebJobsServiceBus__clientId'
          value: reference(managedIdentityId, '2023-01-31').clientId
        }
        // Document Store Configuration (Cosmos DB)
        {
          name: 'DOC_STORE_TYPE'
          value: 'azurecosmos'
        }
        {
          name: 'DOC_STORE_HOST'
          value: '${cosmosAccountName}.documents.azure.com'
        }
        {
          name: 'DOC_STORE_PORT'
          value: '443'
        }
        {
          name: 'DOC_STORE_NAME'
          value: 'copilot'
        }
        {
          name: 'DOC_STORE_USER'
          value: ''  // Managed Identity used
        }
        {
          name: 'DOC_STORE_PASSWORD'
          value: ''  // Managed Identity used
        }
        // Message Bus Configuration (Azure Service Bus)
        {
          name: 'MESSAGE_BUS_TYPE'
          value: 'azureservicebus'
        }
        {
          name: 'MESSAGE_BUS_HOST'
          value: '${serviceBusNamespaceName}.servicebus.windows.net'
        }
        {
          name: 'MESSAGE_BUS_PORT'
          value: '5671'
        }
        {
          name: 'MESSAGE_BUS_USER'
          value: ''  // Managed Identity used
        }
        {
          name: 'MESSAGE_BUS_PASSWORD'
          value: ''  // Managed Identity used
        }
        // Vector Store Configuration (Azure AI Search)
        {
          name: 'VECTOR_STORE_TYPE'
          value: 'azureaisearch'
        }
        {
          name: 'VECTOR_STORE_HOST'
          value: aiSearchEndpoint
        }
        // Chunking Configuration (defaults - can be overridden per function)
        {
          name: 'CHUNKING_STRATEGY'
          value: 'sentence'
        }
        {
          name: 'CHUNK_SIZE'
          value: '512'
        }
        {
          name: 'CHUNK_OVERLAP'
          value: '50'
        }
        {
          name: 'MIN_CHUNK_SIZE'
          value: '100'
        }
        {
          name: 'MAX_CHUNK_SIZE'
          value: '1024'
        }
        // Key Vault reference for secrets
        {
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
      ]
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
    }
    httpsOnly: true
  }
}

// Outputs
output functionAppId string = functionApp.id
output functionAppName string = functionApp.name
output functionAppDefaultHostName string = functionApp.properties.defaultHostName
output functionAppPlanId string = functionAppPlan.id

// Output for CI/CD deployment
output functionAppPublishProfile string = listPublishingCredentials(functionApp.id, functionApp.apiVersion).properties.publishingPassword
