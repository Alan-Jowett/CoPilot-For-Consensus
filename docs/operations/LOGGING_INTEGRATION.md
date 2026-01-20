# Azure Storage-Based Logging Integration Guide

This document describes how to integrate Azure Storage-based logging into the Container Apps deployment.

## Overview

The logging infrastructure has been created with the following components:

1. **Storage Module Extensions** (`infra/azure/modules/storage.bicep`)
   - Added support for Azure Files shares
   - Added parameters for log-specific blob containers
   - Outputs storage account key for volume mounts

2. **Diagnostic Settings Module** (`infra/azure/modules/diagnosticsettings.bicep`)
   - Configures diagnostic settings for Container Apps
   - Archives platform logs to Blob Storage (NDJSON format)
   - Supports `ContainerAppConsoleLogs` and `ContainerAppSystemLogs`

3. **Container Apps Storage Module** (`infra/azure/modules/containerappstorage.bicep`)
   - Creates storage volumes for Azure Files in Container Apps environment
   - Mounts Azure Files share for CSV log writing

4. **CSV File Logger** (`adapters/copilot_logging/copilot_logging/csv_file_logger.py`)
   - Python logger that writes structured CSV logs
   - Daily rotation per replica
   - Schema evolution via JSON extras column

5. **Converter Script** (`scripts/convert_ndjson_to_csv.py`)
   - Converts NDJSON diagnostic logs to CSV
   - Can run as scheduled ACA Job

## Integration Steps

### Step 1: Update main.bicep

The following parameters have been added to `main.bicep`:

```bicep
@description('Enable Azure Files storage for application logs (CSV format)')
param enableAzureFilesLogging bool = true

@description('Enable Blob storage archiving for ACA platform logs (NDJSON format)')
param enableBlobLogArchiving bool = true

@description('Enable optional converter job to transform NDJSON logs to CSV')
param enableLogConverterJob bool = false
```

Storage module call has been updated:

```bicep
containerNames: concat(['archives'], enableBlobLogArchiving ? ['logs-raw'] : [])
fileShareNames: enableAzureFilesLogging ? ['logs-csv'] : []
```

### Step 2: Add Container Apps Storage Volume (TODO)

**Location:** `infra/azure/modules/containerapps.bicep`

**What to add:**

After the `containerAppsEnv` resource (around line 160), add:

```bicep
// Azure Files storage volume for application logs
module containerAppsStorage 'containerappstorage.bicep' = if (enableAzureFilesLogging) {
  name: 'containerAppsStorageDeployment'
  params: {
    containerAppsEnvId: containerAppsEnv.id
    storageAccountName: storageAccountName
    storageAccountKey: listKeys(resourceId('Microsoft.Storage/storageAccounts', storageAccountName), '2023-01-01').keys[0].value
    fileShareName: 'logs-csv'
    storageVolumeName: 'logfs'
    accessMode: 'ReadWrite'
  }
}
```

**Required inputs to module:**
- `enableAzureFilesLogging` (new parameter to add)
- `storageAccountName` (already exists)

### Step 3: Mount Volume in Container App Templates (TODO)

**Location:** `infra/azure/modules/containerapps.bicep`

**What to add:** For each Container App resource (gateway, ingestion, etc.), add the following to the template:

```bicep
resource gatewayApp 'Microsoft.App/containerApps@2024-03-01' = {
  properties: {
    template: {
      // Add volumes array
      volumes: enableAzureFilesLogging ? [
        {
          name: 'logfs'
          storageType: 'AzureFile'
          storageName: 'logfs'
        }
      ] : []
      
      containers: [
        {
          name: 'gateway'
          image: '...'
          // Add volume mounts
          volumeMounts: enableAzureFilesLogging ? [
            {
              volumeName: 'logfs'
              mountPath: '/mnt/logs'
            }
          ] : []
          
          env: concat(
            // ... existing env vars ...
            enableAzureFilesLogging ? [
              { name: 'APP_LOG_PATH', value: '/mnt/logs' }
              { name: 'APP_LOG_FORMAT', value: 'csv' }
            ] : []
          )
        }
      ]
    }
  }
}
```

**Services to update:**
- gateway
- ingestion  
- parsing
- chunking
- embedding
- orchestrator
- summarization
- reporting
- auth
- ui (optional)

### Step 4: Add Diagnostic Settings per Container App (TODO)

**Location:** `infra/azure/modules/containerapps.bicep`

**What to add:** After each Container App resource, add diagnostic settings:

```bicep
// Diagnostic settings for gateway app
module gatewayDiagnostics 'diagnosticsettings.bicep' = if (enableBlobLogArchiving) {
  name: 'gatewayDiagnosticsDeployment'
  params: {
    containerAppId: gatewayApp.id
    diagnosticSettingsName: 'archive-to-storage'
    storageAccountId: resourceId('Microsoft.Storage/storageAccounts', storageAccountName)
    enableConsoleLogs: true
    enableSystemLogs: true
  }
}
```

**Required inputs to module:**
- `enableBlobLogArchiving` (new parameter to add)
- `storageAccountId` (can derive from storageAccountName)

### Step 5: Add Converter Job (Optional, TODO)

**Location:** `infra/azure/modules/containerapps.bicep`

**What to add:** Add a new Container Apps Job resource:

```bicep
// Log converter job (NDJSON -> CSV)
resource logConverterJob 'Microsoft.App/jobs@2024-03-01' = if (enableLogConverterJob) {
  name: '${projectPrefix}-log-converter-${environment}'
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceIds.ingestion}': {}
    }
  }
  properties: {
    environmentId: containerAppsEnv.id
    configuration: {
      triggerType: 'Schedule'
      scheduleTriggerConfig: {
        cronExpression: '0 */5 * * *'  // Every 5 minutes
        parallelism: 1
        replicaCompletionCount: 1
      }
      replicaTimeout: 300  // 5 minutes
      replicaRetryLimit: 1
    }
    template: {
      volumes: [
        {
          name: 'logfs'
          storageType: 'AzureFile'
          storageName: 'logfs'
        }
      ]
      containers: [
        {
          name: 'converter'
          image: '${containerRegistry}/log-converter:${containerImageTag}'
          command: ['/bin/sh', '-c']
          args: [
            'python /app/scripts/convert_ndjson_to_csv.py --storage-account ${storageAccountName} --input-container logs-raw --output-mount /mnt/logs --lookback-hours 1'
          ]
          volumeMounts: [
            {
              volumeName: 'logfs'
              mountPath: '/mnt/logs'
            }
          ]
          env: [
            { name: 'STORAGE_ACCOUNT_NAME', value: storageAccountName }
            { name: 'INPUT_CONTAINER', value: 'logs-raw' }
            { name: 'OUTPUT_SHARE', value: 'logs-csv' }
            { name: 'OUTPUT_MOUNT_PATH', value: '/mnt/logs' }
            { name: 'LOOKBACK_HOURS', value: '1' }
            { name: 'AZURE_CLIENT_ID', value: identityClientIds.ingestion }
          ]
          resources: {
            cpu: json('0.5')
            memory: '1.0Gi'
          }
        }
      ]
    }
  }
}
```

**Required inputs to module:**
- `enableLogConverterJob` (new parameter to add)
- `identityResourceIds.ingestion` (already exists)
- `identityClientIds.ingestion` (already exists)

### Step 6: Create Converter Dockerfile (TODO)

**Location:** Create `infra/docker/log-converter/Dockerfile`

```dockerfile
FROM python:3.12-slim

# Install dependencies
RUN pip install --no-cache-dir \
    azure-identity \
    azure-storage-blob

# Copy converter script
COPY scripts/convert_ndjson_to_csv.py /app/scripts/

WORKDIR /app

CMD ["python", "/app/scripts/convert_ndjson_to_csv.py"]
```

### Step 7: Update Parameter Descriptions (DONE)

All three parameter files have been updated with the new logging parameters:
- `infra/azure/parameters.dev.json`
- `infra/azure/parameters.staging.json`
- `infra/azure/parameters.prod.json`

## Testing Plan

1. **Infrastructure Deployment Test:**
   ```bash
   # Deploy with logging enabled
   az deployment group create \
     --resource-group rg-env-dev \
     --template-file infra/azure/main.bicep \
     --parameters @infra/azure/parameters.dev.json \
     --parameters enableAzureFilesLogging=true enableBlobLogArchiving=true
   ```

2. **Volume Mount Verification:**
   ```bash
   # Check if volume is mounted in a container
   az containerapp exec --name copilot-gateway-dev --command "ls -la /mnt/logs"
   ```

3. **CSV Logging Test:**
   ```bash
   # Set environment variables and restart
   az containerapp update \
     --name copilot-gateway-dev \
     --set-env-vars APP_LOG_PATH=/mnt/logs APP_LOG_FORMAT=csv
   
   # Check if logs are being written
   # Download logs from Azure Files and inspect
   ```

4. **Diagnostic Logs Test:**
   ```bash
   # Check diagnostic settings
   az monitor diagnostic-settings show \
     --name archive-to-storage \
     --resource /subscriptions/.../containerApps/copilot-gateway-dev
   
   # Check if logs appear in blob storage after 5-10 minutes
   az storage blob list --container-name logs-raw --account-name <storage-account>
   ```

5. **Converter Job Test (if enabled):**
   ```bash
   # Manually trigger converter job
   az containerapp job start --name copilot-log-converter-dev
   
   # Check job logs
   az containerapp job logs show --name copilot-log-converter-dev
   ```

## Migration Path

**Phase 1: Additive (Current)**
- Deploy infrastructure with new parameters
- Storage resources created alongside existing Log Analytics
- No changes to running apps yet

**Phase 2: Opt-In**
- Enable CSV logging for specific services via environment variables
- Both CSV and stdout logs coexist
- Validate CSV output

**Phase 3: Default**
- Set `APP_LOG_FORMAT=csv` as default for all services
- Diagnostic settings archive platform logs to Blob
- Log Analytics continues to receive all logs

**Phase 4: Filtered (Future)**
- Implement DCR (Data Collection Rule) to filter Log Analytics ingestion
- Only send errors/warnings to Log Analytics
- Storage becomes primary log destination

## Rollback Plan

If issues arise:

1. **Disable CSV logging:**
   ```bash
   az containerapp update --name <app-name> --remove-env-vars APP_LOG_FORMAT
   ```

2. **Disable diagnostic settings:**
   ```bash
   az monitor diagnostic-settings delete \
     --name archive-to-storage \
     --resource /subscriptions/.../containerApps/<app-name>
   ```

3. **Continue using Log Analytics:**
   - All logs still flow to Log Analytics by default
   - No data loss

## Cost Impact

**Before:**
- Log Analytics ingestion: ~$2.30/GB
- 10GB/day = ~$690/month

**After (Phase 4):**
- Blob Storage: ~$0.02/GB
- Azure Files: ~$0.12/GB (Hot tier)
- Log Analytics (errors only, ~1GB/day): ~$69/month
- Total: ~$71-73/month (~90% cost reduction)

## Security Considerations

1. **Storage Key Management:**
   - Storage keys used for volume mounts are embedded in Container Apps configuration
   - Alternative: Use managed identity for blob access (converter job)

2. **Access Control:**
   - RBAC on storage account to restrict access
   - Private endpoints for production (already supported via `enablePrivateAccess` parameter)

3. **Retention:**
   - Implement lifecycle management policies for old logs
   - See `docs/operations/logging.md` for examples

## References

- Main documentation: `docs/operations/logging.md`
- Storage module: `infra/azure/modules/storage.bicep`
- Diagnostic settings module: `infra/azure/modules/diagnosticsettings.bicep`
- Container Apps storage module: `infra/azure/modules/containerappstorage.bicep`
- CSV logger: `adapters/copilot_logging/copilot_logging/csv_file_logger.py`
- Converter script: `scripts/convert_ndjson_to_csv.py`
