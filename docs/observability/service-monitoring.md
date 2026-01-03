<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Service Monitoring & Troubleshooting

Unified guide for runtime observability: metrics, logs, dashboards, alerts, token/queue health, and document-processing status.

## Stack & Endpoints (default compose)
- Grafana: http://localhost:8080/grafana/
- Prometheus: http://localhost:9090
- Loki API: http://localhost:3100
- Pushgateway: http://localhost:9091
- RabbitMQ UI: http://localhost:15672 (guest/guest unless overridden)
- Qdrant dashboard: http://localhost:6333/dashboard

## Quick Start (Docker Compose)
- Start/stop: `docker compose up -d` / `docker compose down`
- Status: `docker compose ps`
- Logs: `docker compose logs -f [service]`

## Metrics Model
- Services push metrics to Pushgateway (no `/metrics` endpoints); infra exporters are scraped directly.
- Namespace prefix `copilot_` across services.
- Required labels: `service`, `environment`; domain labels: `status`, `error_type`, `queue`, `collection`, `backend`, `model`.

### Service Metric Highlights
- Parsing: `copilot_parsing_messages_parsed_total`, `copilot_parsing_duration_seconds`, `copilot_parsing_failures_total{error_type}`.
- Chunking: `copilot_chunking_chunks_created_total`, `copilot_chunking_duration_seconds`, `copilot_chunking_failures_total{error_type}`.
- Embedding: `copilot_embedding_generation_duration_seconds`, `copilot_embedding_failures_total{error_type}`.
- Summarization: `copilot_summarization_latency_seconds`, `copilot_summarization_llm_calls_total{backend,model}`, `copilot_summarization_failures_total{error_type}`.
- Orchestrator: `copilot_orchestration_events_total{event_type,outcome}`, `copilot_orchestration_failures_total{error_type}`.
- Infrastructure: `rabbitmq_queue_messages_ready{queue}`, `qdrant_collection_vectors_count{collection}`, cAdvisor `container_*` metrics.

### Document Processing Status Exporter
- Service: `document-processing-exporter` (port 9502) scrapes MongoDB and exposes:
  - `copilot_document_status_count{collection,status}`
  - `copilot_document_processing_duration_seconds{collection}`
  - `copilot_document_age_seconds{collection,status}`
  - `copilot_document_attempt_count{collection}`
  - `copilot_chunks_embedding_status_count{embedding_generated}`
- Prometheus scrape job `document-processing` targets `document-processing-exporter:9502`.
- Dashboard: Grafana "Document Processing Status" (UID `copilot-document-processing-status`).

### Alert Rule Coverage (Prometheus)
- Document processing: stuck/failed docs, long duration, low embedding completion, high attempts, failure rate.
- Service health & resources: service down, restarts, scrape failures, CPU/memory/disk, network errors, dependency health.
- Queue lag: depth, age, growth, missing consumers, dead letter growth.
- SLOs: latency (P95/P99) and error-rate burn for parsing/chunking/embedding/summarization/APIs.
- Retry policy & failed queues: dedicated rule groups.

## Dashboards & Logs
- Grafana dashboards: System Health, Service Metrics, Queue Status, Failed Queues, MongoDB Status, Qdrant Status, Container Resource Usage, Document Processing Status.
- Logs via Grafana Explore (Loki): `{container="<service>"}`, add `level="error"` when structured.

## Troubleshooting Playbook
- Pushgateway empty / no data: check Prometheus targets (`/targets`), ensure services processed work; restart `pushgateway` and the target service.
- Metrics missing for a service: `docker compose logs <service> | Select-String "push metrics"` (PowerShell) to find push errors; trigger ingestion to generate traffic.
- Queue issues: use Queue Status dashboard; RabbitMQ UI for depth/consumers; restart affected worker.
- Document processing alerts: use Document Processing Status dashboard; verify `document-processing-exporter` UP; check MongoDB connectivity; inspect alerts in `infra/prometheus/alerts/document_processing.yml`.
- Resource pressure: check Container Resource Usage dashboard; if high memory/CPU, inspect logs and consider scaling or raising limits.

## Handy Queries
- Pushgateway health: `up{job="pushgateway"}`
- Queue depth: `rabbitmq_queue_messages_ready{queue=~"parsing|chunking|embedding|summarization"}`
- Parsing throughput: `rate(copilot_parsing_messages_parsed_total[5m])`
- Chunking latency (p95): `histogram_quantile(0.95, rate(copilot_chunking_duration_seconds_bucket[5m]))`
- Embedding failures: `rate(copilot_embedding_failures_total[5m])`
- Summarization latency (p95): `histogram_quantile(0.95, rate(copilot_summarization_latency_seconds_bucket[5m]))`
- Doc failure rate: `copilot_document_status_count{collection="archives",status="failed"} / (copilot_document_status_count{collection="archives",status="failed"} + copilot_document_status_count{collection="archives",status="completed"})`

## Operations (compose)
Linux/macOS:
```bash
docker compose restart pushgateway monitoring grafana
```
Windows (PowerShell):
```powershell
docker compose restart pushgateway monitoring grafana
```

## References
- RFC and standards: [docs/OBSERVABILITY_RFC.md](../OBSERVABILITY_RFC.md)
- Alert rules: [infra/prometheus/alerts](../../infra/prometheus/alerts)
- Metrics integration guide: [documents/METRICS_INTEGRATION_GUIDE.md](../../documents/METRICS_INTEGRATION_GUIDE.md)
- Runbooks: [docs/operations/runbooks](../operations/runbooks)
