// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to create Azure Service Bus namespace with queues and RBAC for managed identities'

param location string
param namespaceName string
param sku string = 'Standard'
param managedIdentityPrincipalIds array
param services array
param tags object

// Create Azure Service Bus Namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2021-11-01' = {
  name: namespaceName
  location: location
  tags: tags
  sku: {
    name: sku
    tier: sku
    capacity: sku == 'Premium' ? 1 : null
  }
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    zoneRedundant: sku == 'Premium' ? true : false
    disableLocalAuth: false  // Allow local auth (SAS keys) for initial setup; can be disabled later
  }
}

// Queue names aligned with Copilot-for-Consensus services
// Format: <source-service>-<destination-service>
// Example: ingestion-parser means ingestion publishes, parser consumes
var queueNames = [
  'ingestion-parser'       // Ingestion sends documents to parser
  'parser-chunker'         // Parser sends parsed docs to chunker
  'chunker-embedder'       // Chunker sends chunks to embedder
  'embedder-orchestrator'  // Embedder sends vectors to orchestrator
  'orchestrator-summarizer' // Orchestrator sends for summarization
  'summarizer-reporter'    // Summarizer sends results to reporter
  'dlq-dead-letter'        // Dead-letter queue for failed messages
]

// Create queues for each service-to-service connection
resource serviceBusQueues 'Microsoft.ServiceBus/namespaces/queues@2021-11-01' = [
  for queueName in queueNames: {
    parent: serviceBusNamespace
    name: queueName
    properties: {
      lockDuration: 'PT5M'                    // 5-minute lock timeout
      maxSizeInMegabytes: 1024                // 1 GB queue size
      requiresDuplicateDetection: false       // Can be enabled if exactly-once delivery needed
      requiresSession: false
      deadLetteringOnMessageExpiration: true  // Auto-DLQ on expiration
      enablePartitioning: sku != 'Basic'      // Partitioning not available in Basic
      maxMessageSizeInKilobytes: 256          // 256 KB max message size
      defaultMessageTimeToLive: 'P14D'        // 14 days default TTL
      maxDeliveryCount: 10                    // Retry 10 times before DLQ
    }
  }
]

// Azure RBAC Roles for Service Bus
// Sender role: Can send messages
// Listener role: Can receive messages
// Both roles assigned per service based on context

// Variable to map each service to its sender and listener roles
var serviceRoleAssignments = [
  for (service, idx) in services: {
    service: service
    principalId: managedIdentityPrincipalIds[idx]
  }
]

// Assign "Azure Service Bus Data Sender" role to all services
// (Each service may send to one or more queues)
resource serviceBusDataSenderRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for assignment in serviceRoleAssignments: {
    scope: serviceBusNamespace
    name: guid(serviceBusNamespace.id, assignment.principalId, 'ServiceBusDataSender')
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39')  // Azure Service Bus Data Sender
      principalId: assignment.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

// Assign "Azure Service Bus Data Receiver" role to all services
// (Each service may receive from one or more queues)
resource serviceBusDataReceiverRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for assignment in serviceRoleAssignments: {
    scope: serviceBusNamespace
    name: guid(serviceBusNamespace.id, assignment.principalId, 'ServiceBusDataReceiver')
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0')  // Azure Service Bus Data Receiver
      principalId: assignment.principalId
      principalType: 'ServicePrincipal'
    }
  }
]

// Outputs
output serviceBusNamespaceId string = serviceBusNamespace.id
output serviceBusNamespaceName string = serviceBusNamespace.name
output queueNames array = queueNames
output serviceBusPrincipalId string = serviceBusNamespace.identity.principalId
