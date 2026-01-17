// SPDX-License-Identifier: MIT
// Copyright (c) 2025 Copilot-for-Consensus contributors

metadata description = 'Module to provision Azure Portal Dashboard for OpenTelemetry metrics visualization'
metadata author = 'Copilot-for-Consensus Team'

@description('Location for the dashboard resource')
param location string

@description('Project name prefix for dashboard naming')
param projectName string

@description('Environment name (dev, staging, prod)')
param environment string

@description('Log Analytics Workspace resource ID for dashboard queries')
param logAnalyticsWorkspaceResourceId string

param tags object = {}

var uniqueSuffix = uniqueString(resourceGroup().id)
var projectPrefix = take(replace(projectName, '-', ''), 8)
var dashboardName = '${projectPrefix}-dashboard-${environment}-${take(uniqueSuffix, 5)}'

// Azure Portal Dashboard resource
resource dashboard 'Microsoft.Portal/dashboards@2020-09-01-preview' = {
  name: dashboardName
  location: location
  tags: union(tags, {
    'hidden-title': 'Copilot for Consensus - ${environment} - OpenTelemetry Metrics'
  })
  properties: {
    lenses: [
      {
        order: 0
        parts: [
          // Overview tile
          {
            position: {
              x: 0
              y: 0
              colSpan: 6
              rowSpan: 1
            }
            metadata: {
              type: 'Extension/HubsExtension/PartType/MarkdownPart'
              settings: {
                content: {
                  settings: {
                    content: '## Copilot for Consensus - ${toUpper(environment)}\n\nOpenTelemetry Metrics Dashboard\n\nMonitoring service health, request rates, latency, and log event rates.'
                    title: ''
                    subtitle: ''
                  }
                }
              }
            }
          }
          // Request Count (HTTP requests from Application Insights)
          {
            position: {
              x: 0
              y: 1
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
requests
| where timestamp > ago(1h)
| summarize RequestCount = count() by bin(timestamp, 5m), cloud_RoleName
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'Line'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'RequestCount'
                        type: 'long'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'cloud_RoleName'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Sum'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Request Duration (Latency)
          {
            position: {
              x: 6
              y: 1
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
requests
| where timestamp > ago(1h)
| summarize P50 = percentile(duration, 50), P95 = percentile(duration, 95), P99 = percentile(duration, 99) by bin(timestamp, 5m), cloud_RoleName
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'Line'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'P50'
                        type: 'real'
                      }
                      {
                        name: 'P95'
                        type: 'real'
                      }
                      {
                        name: 'P99'
                        type: 'real'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'cloud_RoleName'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Avg'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Failed Requests
          {
            position: {
              x: 0
              y: 5
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
requests
| where timestamp > ago(1h)
| where success == false
| summarize FailedRequests = count() by bin(timestamp, 5m), cloud_RoleName, resultCode
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'StackedArea'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'FailedRequests'
                        type: 'long'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'cloud_RoleName'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Sum'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Log Event Rates (Errors per hour)
          {
            position: {
              x: 6
              y: 5
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
traces
| where timestamp > ago(24h)
| extend severityLevel = coalesce(tostring(customDimensions.severityLevel), tostring(severityLevel), "Information")
| where severityLevel in ("Error", "Warning", "Information")
| summarize ErrorsPerHour = countif(severityLevel == "Error"), 
            WarningsPerHour = countif(severityLevel == "Warning"), 
            InfoPerHour = countif(severityLevel == "Information") 
  by bin(timestamp, 1h)
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'Line'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'ErrorsPerHour'
                        type: 'long'
                      }
                      {
                        name: 'WarningsPerHour'
                        type: 'long'
                      }
                      {
                        name: 'InfoPerHour'
                        type: 'long'
                      }
                    ]
                    aggregation: 'Sum'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'P1D'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Custom Metrics - Service Processing Rates
          {
            position: {
              x: 0
              y: 9
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
customMetrics
| where timestamp > ago(1h)
| where name startswith "copilot."
| where name endswith "_total" or name endswith "_processed_total"
| summarize MetricValue = sum(value) by bin(timestamp, 5m), name
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'Line'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'MetricValue'
                        type: 'real'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'name'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Sum'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Custom Metrics - Service Durations
          {
            position: {
              x: 6
              y: 9
              colSpan: 6
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
customMetrics
| where timestamp > ago(1h)
| where name startswith "copilot."
| where name endswith "_duration_seconds" or name endswith "_latency_seconds"
| summarize P50 = percentile(value, 50), P95 = percentile(value, 95) by bin(timestamp, 5m), name
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'Line'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'P50'
                        type: 'real'
                      }
                      {
                        name: 'P95'
                        type: 'real'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'name'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Avg'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
          // Custom Metrics - Failure Rates
          {
            position: {
              x: 0
              y: 13
              colSpan: 12
              rowSpan: 4
            }
            metadata: {
              type: 'Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart'
              settings: {
                content: {
                  Query: '''
customMetrics
| where timestamp > ago(1h)
| where name startswith "copilot."
| where name endswith "_failures_total" or name endswith "_failed_total" or name endswith "_errors_total"
| summarize FailureCount = sum(value) by bin(timestamp, 5m), name
| render timechart
'''
                  ControlType: 'FrameControlChart'
                  SpecificChart: 'StackedArea'
                  Dimensions: {
                    xAxis: {
                      name: 'timestamp'
                      type: 'datetime'
                    }
                    yAxis: [
                      {
                        name: 'FailureCount'
                        type: 'real'
                      }
                    ]
                    splitBy: [
                      {
                        name: 'name'
                        type: 'string'
                      }
                    ]
                    aggregation: 'Sum'
                  }
                }
              }
              inputs: [
                {
                  name: 'resourceTypeMode'
                  value: 'workspace'
                }
                {
                  name: 'ComponentId'
                  value: {
                    ResourceId: logAnalyticsWorkspaceResourceId
                  }
                }
                {
                  name: 'TimeRange'
                  value: 'PT1H'
                }
                {
                  name: 'Version'
                  value: '2.0'
                }
              ]
            }
          }
        ]
      }
    ]
    metadata: {
      model: {
        timeRange: {
          value: {
            relative: {
              duration: 24
              timeUnit: 1
            }
          }
          type: 'MsPortalFx.Composition.Configuration.ValueTypes.TimeRange'
        }
        filterLocale: {
          value: 'en-us'
        }
        filters: {
          value: {
            MsPortalFx_TimeRange: {
              model: {
                format: 'utc'
                granularity: 'auto'
                relative: '24h'
              }
              displayCache: {
                name: 'UTC Time'
                value: 'Past 24 hours'
              }
              filteredPartIds: []
            }
          }
        }
      }
    }
  }
}

// Outputs
@description('Dashboard resource ID')
output dashboardId string = dashboard.id

@description('Dashboard name')
output dashboardName string = dashboard.name

@description('URL to access the dashboard in Azure Portal (Azure Public Cloud only; for Azure Government or Azure China, manually construct URL using portal domain)')
output dashboardUrl string = 'https://portal.azure.com/#@${subscription().tenantId}/dashboard/arm${dashboard.id}'
