// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

@description('The name of the Service Bus namespace')
param namespaceName string

@description('The location where the Service Bus namespace will be deployed')
param location string

@description('The SKU of the Service Bus namespace (Standard or Premium)')
@allowed(['Standard', 'Premium'])
param sku string = 'Standard'

@description('The capacity (messaging units) for Premium SKU. Only valid for Premium SKU')
param capacity int = 1

@description('Services that will send messages (sender role only)')
@minLength(1)
@maxLength(10)
param senderServices array = [
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
]

@description('Services that will receive messages (receiver role only)')
@minLength(1)
@maxLength(10)
param receiverServices array = [
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
  'ingestion'
]

var queueDefinitions = [
  {
    name: 'archive.ingested'
    description: 'Archive documents ingested into the system'
  }
  {
    name: 'json.parsed'
    description: 'JSON-parsed documents ready for chunking'
  }
  {
    name: 'chunks.prepared'
    description: 'Document chunks prepared for embedding'
  }
  {
    name: 'embeddings.generated'
    description: 'Generated embeddings ready for orchestration'
  }
  {
    name: 'summarization.requested'
    description: 'Documents requested for summarization'
  }
  {
    name: 'summary.complete'
    description: 'Completed summaries'
  }
  {
    name: 'dlq.dead-letter'
    description: 'Dead-letter queue for failed messages'
  }
]

// Service Bus Namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  sku: {
    name: sku
    // Capacity (messaging units) is only applicable for Premium SKU
    capacity: sku == 'Premium' ? capacity : null
  }
  identity: {
    type: 'None'
  }
  properties: {
    disableLocalAuth: true
    zoneRedundant: sku == 'Premium'
    minimumTlsVersion: '1.2'
    publicNetworkAccess: 'Enabled'
  }
}

// Create all message queues
resource queues 'Microsoft.ServiceBus/namespaces/queues@2022-10-01-preview' = [
  for queue in queueDefinitions: {
    parent: serviceBusNamespace
    name: queue.name
    properties: {
      lockDuration: 'PT5M'
      maxSizeInMegabytes: sku == 'Premium' ? 81920 : 1024
      requiresDuplicateDetection: false
      requiresSession: false
      defaultMessageTimeToLive: 'P14D'
      deadLetteringOnMessageExpiration: true
      duplicateDetectionHistoryTimeWindow: 'PT10M'
      maxMessageSizeInKilobytes: sku == 'Premium' ? 102400 : 256
      enablePartitioning: false
      enableExpress: false
      autoDeleteOnIdle: 'P10D'
    }
  }
]

// RBAC: Sender services get Azure Service Bus Data Sender role (only)
resource senderRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for service in senderServices: {
    name: guid(serviceBusNamespace.id, service, 'sender')
    scope: serviceBusNamespace
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '69a216fc-b8fb-44d8-bc22-1f3c2cd27a39') // Azure Service Bus Data Sender
      principalId: reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', service), '2023-01-31').principalId
      principalType: 'ServicePrincipal'
    }
  }
]

// RBAC: Receiver services get Azure Service Bus Data Receiver role (only)
resource receiverRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for service in receiverServices: {
    name: guid(serviceBusNamespace.id, service, 'receiver')
    scope: serviceBusNamespace
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-6440c6acfb47') // Azure Service Bus Data Receiver
      principalId: reference(resourceId('Microsoft.ManagedIdentity/userAssignedIdentities', service), '2023-01-31').principalId
      principalType: 'ServicePrincipal'
    }
  }
]

@description('The resource ID of the Service Bus namespace')
output namespaceName string = serviceBusNamespace.name

@description('The namespace resource ID for use by dependent resources')
output namespaceResourceId string = serviceBusNamespace.id

@description('Queue names deployed to the namespace')
output queueNames array = [
  for queue in queueDefinitions: queue.name
]
