// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Application Insights for monitoring'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for resources')
param location string

@description('Project name')
param projectName string

@description('Environment name')
param environment string

param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var appInsightsName = '${projectPrefix}-ai-${environment}-${take(uniqueSuffix, 5)}'
var lawName = '${projectPrefix}-law-${environment}-${take(uniqueSuffix, 5)}'

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  name: lawName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
  }
}

// Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

// Outputs (secrets NOT exposed as plaintext; stored in Key Vault instead)
@description('Application Insights Instrumentation Key (for Key Vault storage only)')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Application Insights Connection String (for Key Vault storage only)')
output connectionString string = appInsights.properties.ConnectionString

@description('Application Insights ID')
output appInsightsId string = appInsights.id

@description('Log Analytics Workspace ID')
output workspaceId string = logAnalyticsWorkspace.id

@description('Log Analytics Workspace customerId (GUID) - store in Key Vault, do not pass as plaintext')
output workspaceCustomerId string = logAnalyticsWorkspace.properties.customerId
