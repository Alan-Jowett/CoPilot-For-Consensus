// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure Azure Files storage volumes for Container Apps environment'

@description('Container Apps environment resource ID')
param containerAppsEnvId string

@description('Storage Account name')
param storageAccountName string

@description('Storage Account key')
@secure()
param storageAccountKey string

@description('Azure Files share name')
param fileShareName string

@description('Storage volume name (used when mounting in Container Apps)')
param storageVolumeName string = 'logfs'

@description('Access mode for the file share')
@allowed(['ReadOnly', 'ReadWrite'])
param accessMode string = 'ReadWrite'

// Container Apps environment storage resource for Azure Files
resource containerAppsStorage 'Microsoft.App/managedEnvironments/storages@2024-03-01' = {
  name: '${last(split(containerAppsEnvId, '/'))}/${storageVolumeName}'
  properties: {
    azureFile: {
      accountName: storageAccountName
      accountKey: storageAccountKey
      shareName: fileShareName
      accessMode: accessMode
    }
  }
}

@description('Storage volume name that can be referenced in Container Apps')
output storageVolumeName string = storageVolumeName

@description('Container Apps storage resource ID')
output storageId string = containerAppsStorage.id
