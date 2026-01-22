// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Application Insights (classic) for Azure Monitor OpenTelemetry exporters (no Log Analytics workspace)'

@description('Location for resources')
param location string

@description('Project name')
param projectName string

@description('Environment name')
param environment string

@description('Tags applied to resources')
param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var appInsightsName = '${projectPrefix}-ai-${environment}-${take(uniqueSuffix, 5)}'

// Classic Application Insights (no WorkspaceResourceId) to avoid Log Analytics workspace costs.
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
  }
}

@description('Application Insights connection string')
output connectionString string = appInsights.properties.ConnectionString

@description('Application Insights instrumentation key')
output instrumentationKey string = appInsights.properties.InstrumentationKey

@description('Application Insights resource ID')
output appInsightsId string = appInsights.id
