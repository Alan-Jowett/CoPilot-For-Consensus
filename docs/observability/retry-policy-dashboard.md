<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Verification Guide: Retry Policy Dashboard Fix

Explains the Grafana Retry Policy Monitoring dashboard updates and how to verify metrics for the retry job.

## Issue Summary
Dashboard showed "no-data" because the retry job had not run yet, healthy zeros were not initialized, and users lacked guidance.

## Changes Made
- Dashboard (`infra/grafana/dashboards/retry-policy.json`): info panel explaining schedule, healthy zeros, and troubleshooting with link to [retry policy](../operations/retry-policy.md).
- Retry job (`scripts/retry_stuck_documents.py`): initializes gauges to 0 each run so metrics exist even when healthy.
- Documentation: added dashboard section to monitoring guide; this verification guide summarizes expected behavior.

## Verification Steps
1. Start stack: `docker compose up -d`.
2. Ensure retry-job is running: `docker compose ps retry-job`.
3. (Optional) Trigger once: `docker compose run --rm retry-job python /app/scripts/retry_stuck_documents.py --once`.
4. Check Pushgateway http://localhost:9091 for `retry_job_*` metrics (stuck/failed docs = 0, runs_total>=1).
5. Prometheus http://localhost:9090 queries:
```promql
retry_job_stuck_documents
retry_job_failed_documents
retry_job_runs_total{status="success"}
```
6. Grafana http://localhost:8080/grafana/ → Retry Policy Monitoring dashboard: info panel visible; gauges show zeros (healthy), no "No Data" after first run.

## Testing Edge Cases
- Healthy pipeline: gauges at 0 (expected).
- Fresh startup: may show "No Data" before first run; cleared after run.
- MongoDB failure: metrics still initialized to 0; `retry_job_runs_total{status="failure"}` increments.
- Actual stuck docs: insert test doc, run job, expect non-zero gauges and alerts.

## References
- Retry policy: [docs/operations/retry-policy.md](../operations/retry-policy.md)
- Monitoring guide: [docs/observability/service-monitoring.md](service-monitoring.md)
- Metrics integration: [docs/observability/metrics-integration.md](metrics-integration.md)
