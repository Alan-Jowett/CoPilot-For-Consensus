<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Azure Portal Dashboard for OpenTelemetry Metrics

## Overview

The Azure deployment now includes an automated Azure Portal Dashboard that visualizes OpenTelemetry metrics from all microservices. This dashboard provides a centralized view of service health, request rates, latency, failures, and log event rates.

## Features

The dashboard includes the following tiles:

### 1. Request Count
- **Type**: Line chart
- **Data**: HTTP requests per service over time (5-minute bins)
- **Source**: Application Insights `requests` table
- **Split by**: Service name (`cloud_RoleName`)

### 2. Request Duration (Latency)
- **Type**: Line chart
- **Data**: P50, P95, and P99 latency percentiles
- **Source**: Application Insights `requests` table
- **Metrics**: Duration in milliseconds
- **Split by**: Service name

### 3. Failed Requests
- **Type**: Stacked area chart
- **Data**: HTTP requests where `success == false`
- **Source**: Application Insights `requests` table
- **Split by**: Service name and HTTP status code

### 4. Log Event Rates
- **Type**: Line chart
- **Data**: Errors, warnings, and info logs per hour
- **Source**: Application Insights `traces` table
- **Metrics**: 
  - Errors per hour (severity = "Error")
  - Warnings per hour (severity = "Warning")
  - Info per hour (severity = "Information")

### 5. Custom Metrics - Service Processing Rates
- **Type**: Line chart
- **Data**: Service-specific counters (e.g., `ingestion_files_total`, `parsing_messages_parsed_total`)
- **Source**: Application Insights `customMetrics` table
- **Filter**: Metrics ending with `_total` or `_processed_total`

### 6. Custom Metrics - Service Durations
- **Type**: Line chart
- **Data**: P50 and P95 duration percentiles for service operations
- **Source**: Application Insights `customMetrics` table
- **Filter**: Metrics ending with `_duration_seconds` or `_latency_seconds`

### 7. Custom Metrics - Failure Rates
- **Type**: Stacked area chart
- **Data**: Service-specific failure counters
- **Source**: Application Insights `customMetrics` table
- **Filter**: Metrics ending with `_failures_total`, `_failed_total`, or `_errors_total`

## Deployment

The dashboard is automatically deployed when Container Apps are enabled (`deployContainerApps: true`). No additional parameters or configuration is required.

### Accessing the Dashboard

After deployment, get the dashboard URL from the deployment outputs:

```bash
# Bash
DASHBOARD_URL=$(az deployment group show \
  --name <deployment-name> \
  --resource-group <resource-group> \
  --query properties.outputs.dashboardUrl.value -o tsv)

echo "Dashboard URL: $DASHBOARD_URL"
```

```powershell
# PowerShell
$dashboardUrl = (az deployment group show `
  --name <deployment-name> `
  --resource-group <resource-group> `
  --query properties.outputs.dashboardUrl.value -o tsv)

Write-Host "Dashboard URL: $dashboardUrl"
```

Or navigate manually in Azure Portal:
1. Go to **Azure Portal** (https://portal.azure.com)
2. Click **Dashboard** in the left navigation
3. Find dashboard named: `<project>-dashboard-<env>-<suffix>`

## Customization

### Adding a New Metric Tile

To add a new metric tile to the dashboard:

1. **Edit** `infra/azure/modules/dashboard.bicep`
2. **Add** a new tile definition to the `parts` array in the `lenses[0]` object
3. **Specify**:
   - `position`: x, y coordinates and size (colSpan, rowSpan)
   - `metadata.type`: Chart type (usually `Extension/Microsoft_OperationsManagementSuite_Workspace/PartType/LogsDashboardPart`)
   - `metadata.settings.content.Query`: KQL query for the data
   - `metadata.settings.content.ControlType`: Chart control (e.g., `FrameControlChart`)
   - `metadata.settings.content.SpecificChart`: Chart style (e.g., `Line`, `StackedArea`)
   - `inputs`: Data source configuration

#### Example: Adding Ingestion File Count Tile

```bicep
{
  position: {
    x: 0
    y: 17
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
| where name == "copilot.ingestion_files_total"
| summarize FileCount = sum(value) by bin(timestamp, 5m)
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
              name: 'FileCount'
              type: 'real'
            }
          ]
          aggregation: 'Sum'
        }
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
```

4. **Redeploy** the infrastructure using `./deploy.env.sh` or `./deploy.env.ps1`

### Removing a Tile

To remove a tile from the dashboard:

1. **Edit** `infra/azure/modules/dashboard.bicep`
2. **Remove** the corresponding tile object from the `parts` array
3. **Adjust** the `position` values of remaining tiles if needed
4. **Redeploy** the infrastructure

### Editing Tiles in Azure Portal (Temporary)

You can also customize the dashboard directly in Azure Portal:

1. **Open** the dashboard in Azure Portal
2. **Click** "Edit" in the top toolbar
3. **Add tiles** by dragging from the Tile Gallery
4. **Edit tiles** by clicking the pencil icon on each tile
5. **Click** "Done customizing" to save

**Note**: Changes made in the Portal will be **overwritten** on the next Bicep deployment. For permanent changes, edit the Bicep template.

## Available Metrics

See [metrics-catalog.md](../../docs/observability/metrics-catalog.md) for the complete list of metrics emitted by the system.

### Metric Naming Convention

- **Prometheus/Pushgateway**: `copilot_<metric_name>` (e.g., `copilot_parsing_duration_seconds`)
- **Azure Monitor/OpenTelemetry**: `copilot.<metric_name>` (e.g., `copilot.parsing_duration_seconds`)

### Data Sources

- **requests**: HTTP request telemetry (count, duration, success/failure)
- **traces**: Application logs with severity levels (Error, Warning, Information, etc.)
- **customMetrics**: Service-specific metrics
  - Counters: `*_total`, `*_count`
  - Histograms: `*_duration_seconds`, `*_latency_seconds`, `*_size_bytes`
  - Gauges: `*_processed`, `*_skipped`

## Troubleshooting

### Metrics Not Appearing

**Symptom**: Dashboard tiles show "No data" or empty charts.

**Resolution**:
1. **Verify** Application Insights is receiving data:
   ```bash
   az monitor app-insights query \
     --app <app-insights-name> \
     --resource-group <resource-group> \
     --analytics-query "traces | where timestamp > ago(1h) | take 10"
   ```
2. **Check** Container Apps have correct Application Insights connection string:
   ```bash
   az containerapp show \
     --name <service-name> \
     --resource-group <resource-group> \
     --query properties.configuration.secrets
   ```
3. **Ensure** OpenTelemetry instrumentation is enabled in services (check environment variables)
4. **Verify** dashboard queries use correct metric names (see `metrics-catalog.md`)
5. **Wait** 5-10 minutes for metrics to appear (telemetry ingestion latency)

### Dashboard Not Visible in Portal

**Symptom**: Dashboard doesn't appear in the Dashboards list.

**Resolution**:
1. **Check** deployment outputs for dashboard name:
   ```bash
   az deployment group show \
     --name <deployment-name> \
     --resource-group <resource-group> \
     --query properties.outputs.dashboardName.value -o tsv
   ```
2. **Verify** the dashboard resource exists:
   ```bash
   az resource list \
     --resource-group <resource-group> \
     --resource-type Microsoft.Portal/dashboards \
     --output table
   ```
3. **Confirm** you have permissions to view shared dashboards (Reader role on resource group)

### KQL Query Errors

**Symptom**: Tile shows "Query failed" or syntax error.

**Resolution**:
1. **Test** the KQL query in Application Insights Logs:
   - Open Application Insights in Azure Portal
   - Go to "Logs"
   - Paste the query from the dashboard tile
   - Debug and fix syntax errors
2. **Update** the Bicep template with the corrected query
3. **Redeploy** the infrastructure

### Type Warnings During Bicep Build

**Symptom**: Bicep build shows warnings about `BCP036` and `BCP037` for dashboard properties.

**Resolution**: These warnings are **expected** and can be ignored. They indicate known type definition inaccuracies in Azure's resource schemas for the `Microsoft.Portal/dashboards` resource type. The dashboard will deploy and function correctly despite these warnings.

## Architecture

```
┌────────────────────────────────────────────────────────┐
│              Container Apps (Services)                  │
│  - Emit OpenTelemetry metrics                          │
│  - Send telemetry to Application Insights              │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│          Application Insights + Log Analytics           │
│  - Ingest traces, metrics, requests                    │
│  - Store in tables: requests, traces, customMetrics    │
└────────────────────┬───────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────────┐
│            Azure Portal Dashboard                       │
│  - Query data via KQL (Kusto Query Language)           │
│  - Visualize metrics in charts and graphs              │
│  - Automatically deployed via Bicep                    │
└────────────────────────────────────────────────────────┘
```

## References

- [Azure Portal Dashboards Documentation](https://learn.microsoft.com/en-us/azure/azure-portal/azure-portal-dashboards)
- [Microsoft.Portal/dashboards Bicep Reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.portal/dashboards)
- [Kusto Query Language (KQL) Documentation](https://learn.microsoft.com/en-us/azure/data-explorer/kusto/query/)
- [Application Insights Data Model](https://learn.microsoft.com/en-us/azure/azure-monitor/app/data-model)
- [OpenTelemetry with Azure Monitor](https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-overview)
- [Metrics Catalog](../../docs/observability/metrics-catalog.md)
