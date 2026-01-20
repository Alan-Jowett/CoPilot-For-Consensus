// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure diagnostic settings for Azure Container Apps to archive logs to Storage'

@description('Container App name')
param containerAppName string

@description('Diagnostic settings name')
param diagnosticSettingsName string = 'archive-to-storage'

@description('Storage Account resource ID for archiving logs')
param storageAccountId string

@description('Enable ContainerAppConsoleLogs archiving')
param enableConsoleLogs bool = true

@description('Enable ContainerAppSystemLogs archiving')
param enableSystemLogs bool = true

@description('Enable AppEnvSpringAppConsoleLogs archiving')
param enableSpringAppLogs bool = false

// Reference existing Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: containerAppName
}

// Diagnostic settings for Container App
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01' = {
  name: diagnosticSettingsName
  scope: containerApp
  properties: {
    storageAccountId: storageAccountId
    logs: [
      {
        category: 'ContainerAppConsoleLogs'
        enabled: enableConsoleLogs
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
      {
        category: 'ContainerAppSystemLogs'
        enabled: enableSystemLogs
        retentionPolicy: {
          enabled: false
          days: 0
        }
      }
    ]
  }
}

@description('Diagnostic settings resource ID')
output diagnosticSettingsId string = diagnosticSettings.id
