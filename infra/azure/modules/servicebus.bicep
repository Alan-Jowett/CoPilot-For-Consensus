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

@description('Managed identity resource IDs keyed by service name (from identities module)')
param identityResourceIds object

@description('Services that will send messages (sender role only)')
@minLength(1)
param senderServices array = [
  'ingestion'
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
]

@description('Services that will receive messages (receiver role only)')
@minLength(1)
param receiverServices array = [
  'parsing'
  'chunking'
  'embedding'
  'orchestrator'
  'summarization'
  'reporting'
]

@description('Grant additional permissions needed for KEDA autoscaling to read Service Bus runtime properties')
param enableKedaServiceBusScaling bool = true

var kedaReceiverServices = enableKedaServiceBusScaling ? receiverServices : []

@description('Shared topic name used for fan-out messaging')
param eventsTopicName string = 'copilot.events'

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

// Event type mappings for each service (which event types each service subscribes to)
// This enables server-side filtering to reduce bandwidth and compute costs
// SQL filter expressions are pre-computed for each service
// Note: If receiverServices contains a service not in this map, it falls back to a deny-all filter (1=0)
// to fail closed and prevent misconfiguration from delivering all messages
var serviceEventTypeFilters = {
  parsing: 'event_type IN (\'ArchiveIngested\', \'SourceDeletionRequested\')'
  chunking: 'event_type IN (\'JSONParsed\', \'SourceDeletionRequested\')'
  embedding: 'event_type IN (\'ChunksPrepared\', \'SourceDeletionRequested\')'
  orchestrator: 'event_type = \'EmbeddingsGenerated\''
  summarization: 'event_type = \'SummarizationRequested\''
  reporting: 'event_type IN (\'SummaryComplete\', \'SourceDeletionRequested\')'
}

// Service Bus Namespace
resource serviceBusNamespace 'Microsoft.ServiceBus/namespaces@2022-10-01-preview' = {
  name: namespaceName
  location: location
  sku: union({ name: sku }, sku == 'Premium' ? { capacity: capacity } : {})
  identity: {
    type: 'None'
  }
  properties: {
    disableLocalAuth: true
    zoneRedundant: sku == 'Premium'
    minimumTlsVersion: '1.2'
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
  }
}

// Shared topic for event fan-out
resource eventsTopic 'Microsoft.ServiceBus/namespaces/topics@2022-10-01-preview' = {
  parent: serviceBusNamespace
  name: eventsTopicName
  properties: {
    defaultMessageTimeToLive: 'P14D'
    duplicateDetectionHistoryTimeWindow: 'PT10M'
    enablePartitioning: sku == 'Standard'
    maxSizeInMegabytes: sku == 'Premium' ? 81920 : 1024
    requiresDuplicateDetection: false
    supportOrdering: false
  }
}

// Per-service subscriptions with server-side event type filtering
// Each service only receives the events it needs (defined in serviceEventTypeFilters)
resource eventsSubscriptions 'Microsoft.ServiceBus/namespaces/topics/subscriptions@2022-10-01-preview' = [
  for service in receiverServices: {
    parent: eventsTopic
    name: service
    properties: {
      lockDuration: 'PT5M'
      defaultMessageTimeToLive: 'P14D'
      deadLetteringOnMessageExpiration: true
      maxDeliveryCount: 10
      enableBatchedOperations: true
      requiresSession: false
    }
  }
]

// SQL filter rules for server-side event filtering
// Filters messages based on the event_type application property
// NOTE: Azure Service Bus automatically creates a $Default TrueFilter rule for each subscription.
// We use a custom rule name (EventTypeFilter) to avoid conflicts with the auto-created $Default rule
// and to ensure the custom SQL filter rule can be deployed reliably via ARM. The $Default rule must
// still be removed separately for these filters to be the only ones applied.
resource subscriptionFilters 'Microsoft.ServiceBus/namespaces/topics/subscriptions/rules@2022-10-01-preview' = [
  for (service, i) in receiverServices: {
    parent: eventsSubscriptions[i]
    name: 'EventTypeFilter'
    properties: {
      filterType: 'SqlFilter'
      sqlFilter: {
        // Safe access with fallback: if service not in map, use deny-all filter (1=0) to fail closed
        sqlExpression: serviceEventTypeFilters[?service] ?? '1=0'
        // Compatibility level 20 is the standard level for SQL 92 filters in Azure Service Bus
        compatibilityLevel: 20
      }
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
      principalId: reference(identityResourceIds[service], '2023-01-31').principalId
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
      // Built-in role for listening to queues and topics
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4f6d3b9b-027b-4f4c-9142-0e5a2a2247e0') // Azure Service Bus Data Receiver
      principalId: reference(identityResourceIds[service], '2023-01-31').principalId
      principalType: 'ServicePrincipal'
    }
  }
]

// RBAC: KEDA Service Bus scaler needs to read topic/subscription runtime properties to compute backlog.
// This typically requires the Azure Service Bus Data Owner role when using Azure AD / managed identity.
resource receiverKedaRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [
  for service in kedaReceiverServices: {
    name: guid(serviceBusNamespace.id, service, 'keda-data-owner')
    scope: serviceBusNamespace
    properties: {
      roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '090c5cfd-751d-490a-894a-3ce6f1109419') // Azure Service Bus Data Owner
      principalId: reference(identityResourceIds[service], '2023-01-31').principalId
      principalType: 'ServicePrincipal'
    }
  }
]

@description('The resource ID of the Service Bus namespace')
output namespaceName string = serviceBusNamespace.name

@description('The namespace resource ID for use by dependent resources')
output namespaceResourceId string = serviceBusNamespace.id

@description('The fully qualified domain name of the Service Bus namespace')
output namespaceFullyQualifiedName string = '${serviceBusNamespace.name}.servicebus.windows.net'

@description('Shared topic name deployed to the namespace')
output topicName string = eventsTopic.name

@description('Subscription names deployed under the shared topic')
output subscriptionNames array = [
  for service in receiverServices: service
]

