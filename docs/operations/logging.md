# Logging Architecture: Azure Storage-First Approach

This document describes the cost-optimized logging architecture for Copilot for Consensus, which uses Azure Storage (Blob + Files) as the primary log destination instead of Log Analytics.

## Overview

**Default Behavior:** Application and platform logs are written to Azure Storage in CSV/NDJSON format. Only a small, filtered subset (errors/warnings) is optionally sent to Log Analytics for KQL querying and alerting.

**Cost Savings:** Log Analytics ingestion costs scale with volume. By routing routine logs to Storage (~$0.02/GB) instead of Log Analytics (~$2.30/GB for ingestion + retention), costs are reduced by >99% for high-volume workloads.

**Developer Ergonomics:** Logs in CSV format are easy to parse locally with standard tools like Excel, pandas, qsv, ripgrep, or DuckDB.

---

## Architecture Components

### 1. Application Logs → Azure Files (CSV)

**Storage Target:** Azure Files share (`logs-csv`)

**Format:** CSV with stable schema + JSON extras column

**How It Works:**
- Container Apps mount the Azure Files share at `/mnt/logs`
- Application code uses `CSVFileLogger` to write structured logs
- Each replica writes to its own daily-rotated CSV file: `{component}_{replica_id}_{date}.csv`

**CSV Schema:**
```
ts,level,component,replica_id,request_id,message,json_extras
2025-01-20T16:30:00.123Z,INFO,gateway,replica-1,req-abc123,"Request received","{""method"":""GET"",""path"":""/api/reports""}"
```

**Configuration (Environment Variables):**
- `APP_LOG_PATH`: Base directory for CSV logs (default: `/mnt/logs`)
- `APP_LOG_FORMAT`: Log format (`csv` to enable CSV logging, or omit for default stdout)

**Example:**
```bash
# Enable CSV logging in Container App
az containerapp update \
  --name copilot-gateway-dev \
  --set-env-vars APP_LOG_PATH=/mnt/logs APP_LOG_FORMAT=csv
```

### 2. Platform Logs → Blob Storage (NDJSON)

**Storage Target:** Blob container (`logs-raw`)

**Format:** NDJSON (one JSON object per line)

**How It Works:**
- Diagnostic Settings on each Container App resource automatically archive logs to Blob Storage
- Categories: `ContainerAppConsoleLogs`, `ContainerAppSystemLogs`
- Files organized by resource and date: `resourceId=<id>/y=2025/m=01/d=20/PT1H.json`

**Configuration (Bicep Parameters):**
- `enableBlobLogArchiving`: `true` (default) to enable diagnostic log archiving
- Diagnostic settings configured per Container App via `diagnosticsettings.bicep` module

**Example:**
```bicep
param enableBlobLogArchiving bool = true  // Archive platform logs to Blob
```

### 3. Converter Job (Optional)

**Purpose:** Transform NDJSON diagnostic logs from Blob to normalized CSV in Azure Files

**Trigger:** Scheduled ACA Job (e.g., every 5 minutes, hourly, or daily)

**Script:** `scripts/convert_ndjson_to_csv.py`

**Configuration:**
- `enableLogConverterJob`: `false` (default, opt-in via Bicep parameter)
- Job mounts both Blob (via managed identity) and Azure Files (via volume mount)
- Processes blobs created in the last N hours (`LOOKBACK_HOURS` env var)

**Usage:**
```bash
# Run converter manually (inside ACA Job or locally with storage access)
python scripts/convert_ndjson_to_csv.py \
  --storage-account copilotst \
  --input-container logs-raw \
  --output-mount /mnt/logs \
  --lookback-hours 1
```

### 4. Filtered Log Analytics (Optional)

**Purpose:** Keep a minimal subset of logs in Log Analytics for KQL queries and alerting

**Configuration:** Data Collection Rules (DCR) filter logs by level:
- Send `Level >= Warning` to Log Analytics workspace
- Drop `Level < Warning` (INFO, DEBUG)

**Default:** `enableRbacAuthorization: true` in Bicep (no DCR filtering yet, all logs to LA by default)

**Future Enhancement:** Add `dcr.bicep` module to implement selective ingestion

---

## Accessing Logs

### Option 1: Download from Azure Files (SMB)

Azure Files shares support SMB, making logs accessible via standard file system tools.

**Linux/macOS:**
```bash
# Mount Azure Files share
sudo mkdir /mnt/copilot-logs
sudo mount -t cifs \
  //copilotst.file.core.windows.net/logs-csv /mnt/copilot-logs \
  -o vers=3.0,username=copilotst,password="<storage-key>",dir_mode=0777,file_mode=0777

# Browse logs
ls -lh /mnt/copilot-logs
cat /mnt/copilot-logs/gateway_replica-1_2025-01-20.csv | head -10
```

**Windows (PowerShell):**
```powershell
# Mount Azure Files share as Z: drive
$storageAccount = "copilotst"
$fileShare = "logs-csv"
$storageKey = "<storage-key>"

net use Z: "\\$storageAccount.file.core.windows.net\$fileShare" /user:Azure\$storageAccount $storageKey

# Browse logs
dir Z:\
Get-Content Z:\gateway_replica-1_2025-01-20.csv | Select-Object -First 10
```

### Option 2: Download with AzCopy

**Download entire share:**
```bash
# Get SAS token (or use storage key)
SAS_TOKEN="?sv=2021-06-08&ss=f&srt=sco&sp=rl&se=2025-01-21T00:00:00Z&sig=..."

# Download all logs
azcopy copy \
  "https://copilotst.file.core.windows.net/logs-csv$SAS_TOKEN" \
  ./logs/ \
  --recursive
```

**Download specific date range:**
```bash
# Download logs from specific day
azcopy copy \
  "https://copilotst.file.core.windows.net/logs-csv/*_2025-01-20.csv$SAS_TOKEN" \
  ./logs/
```

### Option 3: Query with Local Tools

Once downloaded, use standard CSV tools to query logs:

**qsv (CSV Swiss Army knife):**
```bash
# Count logs by level
qsv frequency level gateway_replica-1_2025-01-20.csv

# Filter errors only
qsv search -s level ERROR gateway_replica-1_2025-01-20.csv > errors.csv

# Summary statistics
qsv stats gateway_replica-1_2025-01-20.csv
```

**pandas (Python):**
```python
import pandas as pd

# Load logs
df = pd.read_csv("gateway_replica-1_2025-01-20.csv")

# Filter warnings and errors
critical = df[df["level"].isin(["WARNING", "ERROR"])]
print(critical)

# Group by component
df.groupby("component").size()
```

**DuckDB (SQL on CSV):**
```bash
# Query multiple CSV files with SQL
duckdb -c "
  SELECT level, COUNT(*) as count
  FROM read_csv_auto('logs/*.csv')
  WHERE ts >= '2025-01-20T12:00:00Z'
  GROUP BY level
  ORDER BY count DESC
"
```

**ripgrep (fast text search):**
```bash
# Find all error messages containing "timeout"
rg -i "ERROR.*timeout" logs/*.csv

# Find logs for specific request ID
rg "req-abc123" logs/*.csv
```

### Option 4: Blob Storage (NDJSON Platform Logs)

Platform logs (diagnostic settings output) are stored as NDJSON in Blob Storage.

**Download with AzCopy:**
```bash
# Download diagnostic logs for specific date
azcopy copy \
  "https://copilotst.blob.core.windows.net/logs-raw/resourceId=.../y=2025/m=01/d=20/$SAS_TOKEN" \
  ./diagnostic-logs/ \
  --recursive
```

**Query with jq:**
```bash
# Parse NDJSON and filter errors
cat PT1H.json | jq -r 'select(.Level == "Error") | [.TimeGenerated, .Message] | @csv'

# Count by ContainerAppName
cat PT1H.json | jq -r '.ContainerAppName' | sort | uniq -c
```

---

## Temporarily Enabling Log Analytics (Incident Response)

During an incident, you may want to temporarily send more logs to Log Analytics for real-time KQL querying.

**Option 1: Disable Diagnostic Settings (Stop Storage Archiving)**
```bash
# Disable diagnostic settings on Container App (logs go to LA only)
az monitor diagnostic-settings update \
  --name archive-to-storage \
  --resource /subscriptions/.../containerApps/copilot-gateway-dev \
  --set logs[0].enabled=false
```

**Option 2: Add Temporary DCR Rule**
```bash
# TODO: Implement DCR module to dynamically adjust log level filter
# For now, logs always go to both Storage and Log Analytics
```

**Option 3: Query Storage Logs in Log Analytics**
```kql
// Query archived logs from Storage (requires Blob connector or ingestion pipeline)
// This is a future enhancement
```

---

## Retention Policies

### Azure Files (CSV Application Logs)

**Recommended Retention:** 7-30 days (application-specific)

**How to Implement:**
- **Manual:** Periodically delete old CSV files via script
- **Automated:** Use ACA Job with scheduled cleanup script

**Example Cleanup Script:**
```bash
#!/bin/bash
# Delete CSV files older than 30 days
find /mnt/logs -name "*.csv" -type f -mtime +30 -delete
```

### Blob Storage (NDJSON Platform Logs)

**Recommended Retention:** 30-90 days

**How to Implement:** Blob lifecycle management policy

**Example Bicep:**
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

### Log Analytics (Filtered Logs)

**Recommended Retention:** 30 days (default, configurable in `appinsights.bicep`)

**Cost:** Retention beyond 30 days incurs additional charges (~$0.12/GB/month)

**Configuration:**
```bicep
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  properties: {
    retentionInDays: 30  // Adjust as needed
  }
}
```

---

## Deployment Parameters

### Bicep Parameters (main.bicep)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `enableAzureFilesLogging` | `true` | Create Azure Files share for CSV logs |
| `enableBlobLogArchiving` | `true` | Archive ACA diagnostic logs to Blob Storage |
| `enableLogConverterJob` | `false` | Deploy ACA Job to convert NDJSON → CSV |

### Example Deployment

```bash
# Deploy with Azure Files and Blob archiving enabled (default)
az deployment group create \
  --resource-group rg-copilot-dev \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/parameters.dev.json \
  --parameters enableAzureFilesLogging=true enableBlobLogArchiving=true

# Deploy with converter job enabled
az deployment group create \
  --resource-group rg-copilot-prod \
  --template-file infra/azure/main.bicep \
  --parameters @infra/azure/parameters.prod.json \
  --parameters enableLogConverterJob=true
```

---

## Troubleshooting

### Logs Not Appearing in Azure Files

**Symptoms:** `/mnt/logs` is empty or CSV files are not being created

**Diagnosis:**
1. Check if Azure Files volume is mounted:
   ```bash
   az containerapp show --name copilot-gateway-dev --query "properties.template.volumes"
   ```
2. Check environment variables:
   ```bash
   az containerapp show --name copilot-gateway-dev --query "properties.template.containers[0].env"
   ```
3. Check container logs for mount errors:
   ```bash
   az containerapp logs show --name copilot-gateway-dev --follow
   ```

**Resolution:**
- Ensure `APP_LOG_PATH=/mnt/logs` is set
- Ensure `APP_LOG_FORMAT=csv` is set
- Verify Azure Files share `logs-csv` exists in storage account
- Verify storage key is correct in Container Apps environment storage config

### Diagnostic Logs Not Appearing in Blob Storage

**Symptoms:** `logs-raw` container is empty

**Diagnosis:**
1. Check diagnostic settings:
   ```bash
   az monitor diagnostic-settings show \
     --name archive-to-storage \
     --resource /subscriptions/.../containerApps/copilot-gateway-dev
   ```
2. Verify storage account ID is correct
3. Check if categories are enabled

**Resolution:**
- Ensure `enableBlobLogArchiving=true` in Bicep parameters
- Redeploy diagnostic settings module
- Allow 5-10 minutes for logs to appear

### Converter Job Fails

**Symptoms:** Converter job exits with error

**Diagnosis:**
1. Check job logs:
   ```bash
   az containerapp job logs show --name copilot-log-converter-dev
   ```
2. Verify managed identity has `Storage Blob Data Contributor` role
3. Verify Azure Files mount is working

**Resolution:**
- Grant managed identity access to storage account
- Check `STORAGE_ACCOUNT_NAME` environment variable
- Verify lookback window (`LOOKBACK_HOURS`) is appropriate

---

## Future Enhancements

1. **Data Collection Rule (DCR) Module:** Implement `dcr.bicep` to filter logs sent to Log Analytics by level (errors/warnings only)
2. **Immutable Blob Storage:** Enable blob versioning and immutability policies for compliance requirements
3. **Event Hub Integration:** Stream filtered logs to Event Hub for SIEM integration
4. **Log Analytics Connector:** Query archived Storage logs directly from Log Analytics (requires custom ingestion pipeline)
5. **Automated Retention:** Add ACA Job to clean up old CSV files in Azure Files based on retention policy

---

## References

- [Azure Storage Pricing](https://azure.microsoft.com/en-us/pricing/details/storage/files/)
- [Log Analytics Pricing](https://azure.microsoft.com/en-us/pricing/details/monitor/)
- [Container Apps Diagnostic Settings](https://learn.microsoft.com/en-us/azure/container-apps/logging)
- [Azure Files SMB Mount](https://learn.microsoft.com/en-us/azure/storage/files/storage-how-to-use-files-linux)
- [qsv - CSV Swiss Army Knife](https://github.com/jqnatividad/qsv)
- [DuckDB - SQL on CSV](https://duckdb.org/)
