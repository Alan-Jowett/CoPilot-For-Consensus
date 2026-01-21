// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure Storage Account for blob storage (archives, artifacts)'

@description('Azure region for the Storage Account')
param location string

@description('Storage Account name (3-24 lowercase letters/numbers, globally unique)')
@minLength(3)
@maxLength(24)
param storageAccountName string

@description('Storage Account SKU (Standard_LRS for dev, Standard_GRS for prod)')
@allowed(['Standard_LRS', 'Standard_GRS', 'Standard_RAGRS', 'Standard_ZRS', 'Premium_LRS'])
param sku string = 'Standard_LRS'

@description('Access tier (Hot for frequently accessed data, Cool for infrequently accessed)')
@allowed(['Hot', 'Cool'])
param accessTier string = 'Hot'

@description('Enable hierarchical namespace (Data Lake Gen2)')
param enableHierarchicalNamespace bool = false

@description('Blob container names to create')
param containerNames array = ['archives']

@description('Managed identity principal IDs that need Storage Blob Data Contributor access')
param contributorPrincipalIds array = []

@description('Enable Azure Files share for Qdrant persistent storage')
param enableQdrantFileShare bool = true

@description('Qdrant file share name')
param qdrantFileShareName string = 'qdrant-storage'

@description('Qdrant file share quota in GB')
param qdrantFileShareQuotaGb int = 5

@description('Tags applied to all storage resources')
param tags object = {}

@description('Network access default action (Allow for dev/staging, Deny for production with specific allowlists)')
@allowed(['Allow', 'Deny'])
param networkDefaultAction string = 'Allow'

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageAccountName
  location: location
  tags: tags
  sku: {
    name: sku
  }
  kind: 'StorageV2'
  properties: {
    accessTier: accessTier
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
    isHnsEnabled: enableHierarchicalNamespace
    networkAcls: {
      // Network access is controlled via networkDefaultAction parameter
      // Production deployments should use 'Deny' and configure specific IP allowlists or VNet rules
      // Example for production:
      //   networkDefaultAction: 'Deny'
      //   ipRules: [{ value: 'your-ip-address', action: 'Allow' }]
      //   virtualNetworkRules: [{ id: subnetId, action: 'Allow' }]
      defaultAction: networkDefaultAction
      bypass: 'AzureServices'
    }
    encryption: {
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
      keySource: 'Microsoft.Storage'
    }
  }
}

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// Create blob containers
resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for containerName in containerNames: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

// File Service for Azure Files (used for Qdrant persistent storage)
resource fileService 'Microsoft.Storage/storageAccounts/fileServices@2023-01-01' = if (enableQdrantFileShare) {
  parent: storageAccount
  name: 'default'
  properties: {
    shareDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

// Azure Files share for Qdrant persistent storage
// This provides durable storage for Qdrant's vector database, enabling scale-to-zero
resource qdrantFileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = if (enableQdrantFileShare) {
  parent: fileService
  name: qdrantFileShareName
  properties: {
    shareQuota: qdrantFileShareQuotaGb
    enabledProtocols: 'SMB'
    accessTier: 'TransactionOptimized'
  }
}

// RBAC: Assign Storage Blob Data Contributor role to managed identities
// Role definition ID for Storage Blob Data Contributor: ba92f5b4-2d11-453d-a403-e96b0029c9fe
var storageBlobDataContributorRoleId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')

resource blobContributorRoleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for (principalId, i) in contributorPrincipalIds: {
  scope: storageAccount
  name: guid(storageAccount.id, principalId, storageBlobDataContributorRoleId)
  properties: {
    roleDefinitionId: storageBlobDataContributorRoleId
    principalId: principalId
    principalType: 'ServicePrincipal'
  }
}]

@description('Storage Account name')
output accountName string = storageAccount.name

@description('Storage Account resource ID')
output accountId string = storageAccount.id

@description('Primary blob service endpoint')
output blobEndpoint string = storageAccount.properties.primaryEndpoints.blob

@description('Primary endpoints for all services')
output primaryEndpoints object = storageAccount.properties.primaryEndpoints

@description('Container names created')
output containerNames array = containerNames

@description('Qdrant file share name (if enabled)')
output qdrantFileShareName string = enableQdrantFileShare ? qdrantFileShare.name : ''

@description('Qdrant file share enabled status')
output qdrantFileShareEnabled bool = enableQdrantFileShare
