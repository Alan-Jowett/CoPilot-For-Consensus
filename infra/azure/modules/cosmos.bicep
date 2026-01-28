// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure Cosmos DB with autoscale throughput and optional multi-region failover'

@description('Azure region for the Cosmos DB account')
param location string

@description('Cosmos DB account name (3-44 lowercase letters, numbers, or hyphens)')
param accountName string

@description('Enable multi-region deployment with automatic failover')
param enableMultiRegion bool = false

@description('Minimum RU/s for validation (must be <= max RU/s)')
@minValue(400)
param cosmosDbAutoscaleMinRu int

@description('Maximum RU/s for autoscale (maxThroughput)')
@minValue(400)
param cosmosDbAutoscaleMaxRu int

@description('Tags applied to all Cosmos DB resources')
param tags object = {}

@description('Enable public network access (set to false for production with Private Link)')
param enablePublicNetworkAccess bool = true

var normalizedAccountName = toLower(accountName)
var authDatabaseName = 'auth'
var documentsDatabaseName = 'copilot'
var containerName = 'documents'
var partitionKeyPath = '/collection'
// New per-collection container routing uses partition key /id.
// These containers must exist because runtime managed-identity (AAD) tokens are not authorized
// to create containers via the Cosmos data plane in many configurations.
var perCollectionPartitionKeyPath = '/id'
var authPerCollectionContainers = [
  'user_roles'
]
var copilotPerCollectionContainers = [
  'messages'
  'archives'
  'chunks'
  'reports'
  'summaries'
  'embeddings'
  'threads'
  // Ingestion source configuration documents
  'sources'
]
var autoscaleMaxRu = cosmosDbAutoscaleMaxRu >= cosmosDbAutoscaleMinRu ? cosmosDbAutoscaleMaxRu : cosmosDbAutoscaleMinRu
var writeRegionNames = [
  for loc in failoverLocations: loc.locationName
]
var enableMultiRegionEffective = enableMultiRegion && contains(secondaryRegionMap, location)
var secondaryRegion = enableMultiRegionEffective ? secondaryRegionMap[location] : ''

// Preferred regional pairs for failover; falls back to the primary location if not mapped
var secondaryRegionMap = {
  eastus: 'westus'
  eastus2: 'centralus'
  westus: 'eastus2'
  westus2: 'centralus'
  westus3: 'eastus'
  centralus: 'eastus2'
  northeurope: 'westeurope'
  westeurope: 'northeurope'
  southeastasia: 'eastasia'
  eastasia: 'southeastasia'
  australiasoutheast: 'australiaeast'
  australiacentral: 'australiacentral2'
  germanywestcentral: 'germanynorth'
}

var failoverLocations = enableMultiRegionEffective ? [
  {
    locationName: location
    failoverPriority: 0
    isZoneRedundant: false
  }
  {
    locationName: secondaryRegion
    failoverPriority: 1
    isZoneRedundant: false
  }
] : [
  {
    locationName: location
    failoverPriority: 0
    isZoneRedundant: false
  }
]

// Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-11-15' = {
  name: normalizedAccountName
  location: location
  kind: 'GlobalDocumentDB'
  tags: tags
  properties: {
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: enableMultiRegion
    locations: failoverLocations
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    publicNetworkAccess: enablePublicNetworkAccess ? 'Enabled' : 'Disabled'
    enableFreeTier: false
    disableLocalAuth: false
    // Only allow Azure services to bypass network restrictions when public access is enabled
    // When using Private Link (public access disabled), enforce stricter isolation
    networkAclBypass: enablePublicNetworkAccess ? 'AzureServices' : 'None'
  }
}

// Auth database with autoscale throughput (for role-based access control and user management)
resource authDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: authDatabaseName
  properties: {
    resource: {
      id: authDatabaseName
    }
    options: {
      autoscaleSettings: {
        maxThroughput: autoscaleMaxRu
      }
    }
  }
}

// Auth container for roles, users, and permissions
resource authContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: authDatabase
  name: 'documents'
  properties: {
    resource: {
      id: 'documents'
      partitionKey: {
        paths: ['/collection']
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
    options: {}
  }
}

// Auth per-collection containers (partitioned by /id)
resource authPerCollectionContainerResources 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = [
  for c in authPerCollectionContainers: {
    parent: authDatabase
    name: c
    properties: {
      resource: {
        id: c
        partitionKey: {
          paths: [
            perCollectionPartitionKeyPath
          ]
          kind: 'Hash'
          version: 2
        }
        indexingPolicy: {
          indexingMode: 'consistent'
          automatic: true
          includedPaths: [
            {
              path: '/*'
            }
          ]
          excludedPaths: [
            {
              path: '/"_etag"/?'
            }
          ]
        }
      }
      options: {}
    }
  }
]

// Documents database with autoscale throughput (for archives, messages, chunks, threads, summaries)
resource documentsDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: documentsDatabaseName
  properties: {
    resource: {
      id: documentsDatabaseName
    }
    options: {
      autoscaleSettings: {
        maxThroughput: autoscaleMaxRu
      }
    }
  }
}

// Single multi-collection container partitioned by logical collection name
// This approach stores all document types (archives, messages, chunks, threads, summaries)
// in a single container, using the '/collection' field as the partition key.
// Benefits:
// - Simplified throughput management (one RU budget for all collections)
// - Cross-collection queries and transactions are possible
// - Lower cost than multiple containers for small-to-medium workloads
// Trade-offs:
// - Collections share the same partition key space (design must avoid hot partitions)
// - Cannot set different TTL or indexing policies per collection (would require separate containers)
//
// For production scale-out, consider migrating to individual containers per collection type
// if throughput requirements diverge or if specific indexing/TTL policies are needed.
resource documentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: documentsDatabase
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          partitionKeyPath
        ]
        kind: 'Hash'
        version: 2
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
        // Composite indexes for common query patterns (archives, messages, threads, summaries)
        compositeIndexes: [
          // Archives: queries by source + ingestion_date
          [
            { path: '/collection', order: 'ascending' }
            { path: '/source', order: 'ascending' }
            { path: '/ingestion_date', order: 'descending' }
          ]
          // Messages: queries by archive_id + date
          [
            { path: '/collection', order: 'ascending' }
            { path: '/archive_id', order: 'ascending' }
            { path: '/date', order: 'descending' }
          ]
          // Messages: queries by thread_id + date
          [
            { path: '/collection', order: 'ascending' }
            { path: '/thread_id', order: 'ascending' }
            { path: '/date', order: 'descending' }
          ]
          // Threads: queries by archive_id + last_message_date
          [
            { path: '/collection', order: 'ascending' }
            { path: '/archive_id', order: 'ascending' }
            { path: '/last_message_date', order: 'descending' }
          ]
          // Summaries: queries by thread_id + generated_at
          [
            { path: '/collection', order: 'ascending' }
            { path: '/thread_id', order: 'ascending' }
            { path: '/generated_at', order: 'descending' }
          ]
          // Chunks: queries by message_id + sequence
          [
            { path: '/collection', order: 'ascending' }
            { path: '/message_id', order: 'ascending' }
            { path: '/sequence', order: 'ascending' }
          ]
        ]
      }
    }
    options: {}
  }
}

// Copilot per-collection containers (partitioned by /id)
resource copilotPerCollectionContainerResources 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = [
  for c in copilotPerCollectionContainers: {
    parent: documentsDatabase
    name: c
    properties: {
      resource: {
        id: c
        partitionKey: {
          paths: [
            perCollectionPartitionKeyPath
          ]
          kind: 'Hash'
          version: 2
        }
        indexingPolicy: {
          indexingMode: 'consistent'
          automatic: true
          includedPaths: [
            {
              path: '/*'
            }
          ]
          excludedPaths: [
            {
              path: '/"_etag"/?'
            }
          ]
        }
      }
      options: {}
    }
  }
]

@description('Cosmos DB account name')
output accountName string = cosmosAccount.name

@description('Cosmos DB account resource ID')
output accountId string = cosmosAccount.id

@description('Cosmos DB account endpoint')
output accountEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Auth database name')
output authDatabaseName string = authDatabase.name

@description('Documents database name')
output documentsDatabaseName string = documentsDatabase.name

@description('Container name')
output containerName string = documentsContainer.name

@description('Auth container name')
output authContainerName string = authContainer.name

@description('Auth container partition key path')
output authPartitionKeyPath string = '/collection'

@description('Autoscale max RU/s applied to the database')
output autoscaleMaxThroughput int = autoscaleMaxRu

@description('Configured write/replica regions (failover priority order)')
output writeRegions array = writeRegionNames

