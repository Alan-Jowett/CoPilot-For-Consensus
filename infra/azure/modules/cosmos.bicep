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

var normalizedAccountName = toLower(accountName)
var databaseName = 'copilot'
var containerName = 'documents'
var partitionKeyPath = '/collection'
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
    publicNetworkAccess: 'Enabled'
    enableFreeTier: false
    disableLocalAuth: false
  }
}

// Cosmos DB database with autoscale throughput
resource cosmosDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-11-15' = {
  parent: cosmosAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: {
      autoscaleSettings: {
        maxThroughput: autoscaleMaxRu
      }
    }
  }
}

// Single multi-collection container partitioned by logical collection name
resource documentsContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-11-15' = {
  parent: cosmosDatabase
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
      }
    }
    options: {}
  }
}

@description('Cosmos DB account name')
output accountName string = cosmosAccount.name

@description('Cosmos DB account endpoint')
output accountEndpoint string = cosmosAccount.properties.documentEndpoint

@description('Database name')
output databaseName string = cosmosDatabase.name

@description('Container name')
output containerName string = documentsContainer.name

@description('Autoscale max RU/s applied to the database')
output autoscaleMaxThroughput int = autoscaleMaxRu

@description('Configured write/replica regions (failover priority order)')
output writeRegions array = writeRegionNames

@description('Cosmos DB connection string for SDK access')
output connectionString string = listConnectionStrings(cosmosAccount.id, '2023-11-15').connectionStrings[0].connectionString
