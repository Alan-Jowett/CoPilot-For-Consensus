<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Verification Guide: Retry Policy Dashboard Fix

## Issue Summary
The Retry Policy Monitoring Grafana dashboard was showing "no-data" because:
1. Users were checking the dashboard before the retry-job had run for the first time
2. When there are no stuck/failed documents (healthy state), gauges weren't being explicitly set to 0
3. No explanatory text helped users understand this expected behavior

## Changes Made

### 1. Dashboard Enhancement
**File**: `infra/grafana/dashboards/retry-policy.json`

Added an informational panel at the top of the dashboard that:
- Explains the retry-job runs every 15 minutes
- Clarifies that "No Data" is normal before the first run
- States that zero values are healthy and expected
- Provides quick troubleshooting commands
- Links to RETRY_POLICY.md documentation

### 2. Metric Initialization Fix
**File**: `scripts/retry_stuck_documents.py`

Modified the `run_once()` method to:
- Initialize all collection gauges to 0 at the start of each run
- Ensure metrics always exist in Pushgateway after first execution
- Prevent "no data" state when pipeline is healthy (zero stuck/failed documents)
- Handle errors gracefully without losing metric visibility

**Code change**:
```python
def run_once(self):
    """Run retry job once."""
    logger.info("Starting retry job execution")
    start_time = time.time()

    # Initialize all gauges to 0 to ensure metrics exist even on failure
    for collection_name in self.COLLECTION_CONFIGS.keys():
        self.metrics.stuck_documents.labels(collection=collection_name).set(0)
        self.metrics.failed_documents.labels(collection=collection_name).set(0)

    # ... rest of the method
```

### 3. Documentation Enhancement
**File**: `documents/SERVICE_MONITORING.md`

Added comprehensive section 4.2 "Retry Policy Monitoring" covering:
- Dashboard panel descriptions and purpose
- Metrics reference table
- Prometheus query examples
- Detailed troubleshooting scenarios with solutions
- Alert integration and configuration tuning

## Verification Steps

### Step 1: Start the Stack

Linux/macOS (bash):
```bash
cd /home/runner/work/CoPilot-For-Consensus/CoPilot-For-Consensus
docker compose up -d
```

Windows (PowerShell):
```powershell
cd /home/runner/work/CoPilot-For-Consensus/CoPilot-For-Consensus
docker compose up -d
```

### Step 2: Verify Retry-Job Service is Running

Linux/macOS (bash):
```bash
docker compose ps retry-job
```

Windows (PowerShell):
```powershell
docker compose ps retry-job
```

Expected output: Service should be "Up" with status "Up X seconds/minutes"

### Step 3: Manually Trigger Retry Job (Optional - for immediate verification)
Instead of waiting 15 minutes for the first scheduled run:

Linux/macOS (bash):
```bash
docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
```

Windows (PowerShell):
```powershell
docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
```

Expected output:
```
INFO:retry_stuck_documents:Starting retry job execution
INFO:retry_stuck_documents:Connected to MongoDB at documentdb:27017
INFO:retry_stuck_documents:Connected to RabbitMQ at messagebus:5672
INFO:retry_stuck_documents:Processing collection: archives
INFO:retry_stuck_documents:Found 0 stuck documents in archives
INFO:retry_stuck_documents:Processed archives: 0 requeued, 0 skipped (backoff), 0 failed (max retries)
... (similar output for messages, chunks, threads)
INFO:retry_stuck_documents:Pushed metrics to http://pushgateway:9091
INFO:retry_stuck_documents:Retry job completed in X.XX seconds
```

### Step 4: Verify Metrics in Pushgateway
Open in browser: http://localhost:9091

Look for job "retry-job" and verify these metrics exist:
- `retry_job_stuck_documents{collection="archives"}` = 0
- `retry_job_stuck_documents{collection="messages"}` = 0
- `retry_job_stuck_documents{collection="chunks"}` = 0
- `retry_job_stuck_documents{collection="threads"}` = 0
- `retry_job_failed_documents{collection="archives"}` = 0
- `retry_job_failed_documents{collection="messages"}` = 0
- `retry_job_failed_documents{collection="chunks"}` = 0
- `retry_job_failed_documents{collection="threads"}` = 0
- `retry_job_runs_total{status="success"}` = 1 (or higher)
- `retry_job_duration_seconds` (histogram)

### Step 5: Verify Prometheus Scrapes the Metrics
Open in browser: http://localhost:9090

Run these queries:
```promql
# Should return 4 series (one per collection) with value 0
retry_job_stuck_documents

# Should return 4 series with value 0
retry_job_failed_documents

# Should return at least 1 with value >= 1
retry_job_runs_total{status="success"}
```

### Step 6: Verify Dashboard Shows Data
Open in browser: http://localhost:8080/grafana/ (login: admin/admin)

Navigate to: Dashboards → Retry Policy Monitoring

**Expected Results**:
1. ✅ Informational panel at top is visible with explanation
2. ✅ "Stuck Documents (Current)" gauge shows 0 for all collections (green)
3. ✅ "Failed Documents (Max Retries)" gauge shows 0 for all collections (green)
4. ✅ All other panels show data (even if values are zero)
5. ✅ NO panels show "No Data" (unless Prometheus is down)

### Step 7: Verify Dashboard Behavior Over Time
Wait 15-30 minutes and check that:
- "Retry Job Executions" panel shows steady increase in success count
- "Retry Job Duration" shows consistent execution times
- All gauges remain at 0 if pipeline is healthy

## Testing Edge Cases

### Test Case 1: Healthy Pipeline (No Stuck Documents)
**Expected**: All gauges show 0, which is correct and healthy

### Test Case 2: Fresh System Startup
**Expected**:
- First 15 minutes: Dashboard may show "No Data" (informational panel explains this)
- After 15 minutes: All panels show data (zeros for healthy state)

### Test Case 3: MongoDB Connection Failure
**Expected**:
- Retry job logs show connection error
- Gauges still initialized to 0 (baseline metrics pushed)
- `retry_job_runs_total{status="failure"}` increments
- `retry_job_errors_total` increments
- Dashboard shows 0 values, not "No Data"

### Test Case 4: Actual Stuck Documents
To simulate stuck documents:

Linux/macOS (bash):
```bash
# Connect to MongoDB
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin

# Insert test stuck document
use copilot
db.archives.insertOne({
  archive_id: "test-stuck-archive",
  status: "pending",
  attemptCount: 1,
  lastAttemptTime: new Date(Date.now() - 48*60*60*1000), // 48 hours ago
  file_path: "/tmp/test.mbox",
  source: "test"
})
```

Windows (PowerShell):
```powershell
# Connect to MongoDB
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin

# Then in mongosh:
# use copilot
# db.archives.insertOne({
#   archive_id: "test-stuck-archive",
#   status: "pending",
#   attemptCount: 1,
#   lastAttemptTime: new Date(Date.now() - 48*60*60*1000),
#   file_path: "/tmp/test.mbox",
#   source: "test"
# })
```

Wait for retry-job to run or manually trigger it:

Linux/macOS (bash):
```bash
docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
```

Windows (PowerShell):
```powershell
docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once
```

**Expected**:
- Dashboard "Stuck Documents (Current)" gauge shows 1 for archives
- "Retry Rate" panel shows activity
- "Total Documents Requeued" increments
- After requeue, stuck count may decrease (if processing succeeds)

Clean up:

Linux/macOS (bash):
```bash
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin
use copilot
db.archives.deleteOne({archive_id: "test-stuck-archive"})
```

Windows (PowerShell):
```powershell
docker compose exec documentdb mongosh -u root -p example --authenticationDatabase admin
# Then in mongosh:
# use copilot
# db.archives.deleteOne({archive_id: "test-stuck-archive"})
```

## Rollback Procedure (if needed)

If the changes cause issues:

Linux/macOS (bash):
```bash
# Revert the dashboard
git checkout HEAD~3 infra/grafana/dashboards/retry-policy.json

# Revert the script
git checkout HEAD~3 scripts/retry_stuck_documents.py

# Revert the documentation
git checkout HEAD~3 documents/SERVICE_MONITORING.md

# Restart Grafana to reload dashboard
docker compose restart grafana

# Rebuild and restart retry-job
docker compose up -d --build retry-job
```

Windows (PowerShell):
```powershell
# Revert the dashboard
git checkout HEAD~3 infra/grafana/dashboards/retry-policy.json

# Revert the script
git checkout HEAD~3 scripts/retry_stuck_documents.py

# Revert the documentation
git checkout HEAD~3 documents/SERVICE_MONITORING.md

# Restart Grafana to reload dashboard
docker compose restart grafana

# Rebuild and restart retry-job
docker compose up -d --build retry-job
```
docker compose restart grafana

# Rebuild and restart retry-job
docker compose up -d --build retry-job
```

## Success Criteria

✅ **Primary Goal**: Dashboard never shows "No Data" after the first retry-job run

✅ **Secondary Goals**:
1. Users understand why "No Data" appears initially (informational panel)
2. Zero values are clearly visible when pipeline is healthy
3. Documentation helps users troubleshoot retry issues
4. Metrics are resilient to connection failures

## Related Documentation

- **Issue**: GitHub Issue about Retry Policy Monitoring showing no data
- **RETRY_POLICY.md**: Complete retry policy specification
- **SERVICE_MONITORING.md**: Section 4.2 - Retry Policy Monitoring
- **Dashboard UID**: `retry-policy`

## Contact

For questions or issues with this fix, refer to:
- GitHub Issue comments
- `documents/RETRY_POLICY.md` for operational procedures
- `documents/SERVICE_MONITORING.md` section 4.2 for dashboard guide
