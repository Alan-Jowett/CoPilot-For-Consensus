// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure diagnostic settings for Azure Container Apps to archive logs to Storage'

@description('Container App resource ID to configure diagnostic settings for')
param containerAppId string

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

// Diagnostic settings for Container App
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingsName
  scope: resourceId('Microsoft.App/containerApps', last(split(containerAppId, '/')))
  properties: {
    storageAccountId: storageAccountId
    logs: concat(
      enableConsoleLogs ? [
        {
          category: 'ContainerAppConsoleLogs'
          enabled: true
          retentionPolicy: {
            enabled: false
            days: 0
          }
        }
      ] : [],
      enableSystemLogs ? [
        {
          category: 'ContainerAppSystemLogs'
          enabled: true
          retentionPolicy: {
            enabled: false
            days: 0
          }
        }
      ] : [],
      enableSpringAppLogs ? [
        {
          category: 'AppEnvSpringAppConsoleLogs'
          enabled: true
          retentionPolicy: {
            enabled: false
            days: 0
          }
        }
      ] : []
    )
  }
}

@description('Diagnostic settings resource ID')
output diagnosticSettingsId string = diagnosticSettings.id
