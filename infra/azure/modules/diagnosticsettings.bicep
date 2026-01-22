// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to configure diagnostic settings for Azure Container Apps Environment to archive logs to Storage'

@description('Container Apps Environment name (Microsoft.App/managedEnvironments)')
param managedEnvironmentName string

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

// Reference existing Container Apps Environment
resource containerAppsEnv 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: managedEnvironmentName
}

// Diagnostic settings for Container Apps Environment
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: diagnosticSettingsName
  scope: containerAppsEnv
  properties: {
    storageAccountId: storageAccountId
    logs: [
      {
        category: 'ContainerAppConsoleLogs'
        enabled: enableConsoleLogs
      }
      {
        category: 'ContainerAppSystemLogs'
        enabled: enableSystemLogs
      }
      {
        category: 'AppEnvSpringAppConsoleLogs'
        enabled: enableSpringAppLogs
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
      }
    ]
  }
}

@description('Diagnostic settings resource ID')
output diagnosticSettingsId string = diagnosticSettings.id
