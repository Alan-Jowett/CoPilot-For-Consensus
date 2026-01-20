<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Blob Storage Logging for Azure Container Apps

This document describes how to archive Azure Container Apps console logs to Blob Storage without using Log Analytics.

## Overview

**Goal:** Archive container console logs (stdout/stderr) to Azure Blob Storage without the expensive Log Analytics workspace.

**Cost Savings:** Blob Storage (~$0.02/GB) vs Log Analytics (~$2.30/GB) = >99% cost reduction for log storage.

**Architecture:** Use Azure Diagnostic Settings to automatically archive `ContainerAppConsoleLogs` and `ContainerAppSystemLogs` to Blob Storage in NDJSON format. No Log Analytics workspace is deployed.

## Important Changes

**Log Analytics Removed:** This implementation completely removes the Log Analytics workspace to eliminate costs. Container Apps will:
- Still function normally
- Have console logs archived to Blob Storage via Diagnostic Settings
- Not send logs to Log Analytics

**Application Insights Disabled:** Since Application Insights depends on Log Analytics, it is also disabled. For application monitoring, consider using:
- OpenTelemetry with alternative backends
- Prometheus metrics (already configured)
- Grafana dashboards with Prometheus data source

## Infrastructure

### Bicep Modules

**diagnosticsettings.bicep** - Configures diagnostic settings for Container Apps to archive logs to Blob Storage
- Input: Container App resource ID, Storage Account ID
- Output: Diagnostic settings resource ID
- Categories: `ContainerAppConsoleLogs`, `ContainerAppSystemLogs`

### Main Bicep Changes

**Parameter:**
```bicep
@description('Enable Blob storage archiving for ACA console logs (NDJSON format)')
param enableBlobLogArchiving bool = true
```

**Storage Account:**
- Creates `logs-raw` blob container when `enableBlobLogArchiving` is true
- Blob lifecycle policies can be added for automatic deletion (e.g., 30 days)

### Deployment

1. Set `enableBlobLogArchiving: true` in parameter files (dev/staging/prod) - already done by default
2. Deploy infrastructure with `az deployment group create`
3. Diagnostic settings are **automatically deployed** for all Container Apps

The `diagnosticsettings.bicep` module is invoked for each Container App in `containerapps.bicep`:
- auth, reporting, ingestion, parsing, chunking, embedding
- orchestrator, summarization, ui, gateway, qdrant (if enabled)

Each Container App's console logs (`ContainerAppConsoleLogs`) and system logs (`ContainerAppSystemLogs`) are archived to the `logs-raw` blob container.

**No manual configuration required** - logs begin archiving automatically upon deployment.

## Accessing Logs

### Download with AzCopy

```bash
# List blobs
az storage blob list \
  --account-name <storage-account> \
  --container-name logs-raw \
  --output table

# Download specific date
azcopy copy \
  "https://<storage-account>.blob.core.windows.net/logs-raw/resourceId=.../y=2025/m=01/d=20/*" \
  ./logs/ \
  --recursive
```

### Query with jq

```bash
# Parse NDJSON and filter errors
cat PT1H.json | jq -r 'select(.Level == "Error") | [.TimeGenerated, .Message] | @csv'

# Count by ContainerAppName
cat PT1H.json | jq -r '.ContainerAppName' | sort | uniq -c
```

### Optional: Convert to CSV

Use the provided `scripts/convert_ndjson_to_csv.py` script to convert NDJSON logs to CSV format:

```bash
python scripts/convert_ndjson_to_csv.py \
  --storage-account <account-name> \
  --input-container logs-raw \
  --output-mount /tmp/csv-logs \
  --lookback-hours 24
```

## Retention

Configure blob lifecycle management to automatically delete old logs:

```bicep
resource blobLifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  name: 'default'
  parent: storageAccount
  properties: {
    policy: {
      rules: [
        {
          name: 'delete-old-logs'
          enabled: true
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: ['blockBlob']
              prefixMatch: ['logs-raw/']
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: 30
                }
              }
            }
          }
        }
      ]
    }
  }
}
```

## Cost Impact

**Before:** 10GB/day @ $2.30/GB = ~$690/month (Log Analytics)
**After:** 10GB/day @ $0.02/GB = ~$6/month (Blob Storage)
**Savings:** ~$684/month (>99% reduction)

## References

- [Azure Container Apps Diagnostic Settings](https://learn.microsoft.com/en-us/azure/container-apps/logging)
- [Azure Storage Pricing](https://azure.microsoft.com/en-us/pricing/details/storage/blobs/)
- Bicep module: `infra/azure/modules/diagnosticsettings.bicep`
- Converter script: `scripts/convert_ndjson_to_csv.py`
