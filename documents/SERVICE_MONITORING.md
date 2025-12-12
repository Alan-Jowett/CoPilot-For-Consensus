# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Service Monitoring & Troubleshooting Guide

This guide explains how to monitor and troubleshoot the services in this repository. It covers metrics, logs, message bus visibility, and common diagnostics, including a section specific to the Docker Compose setup shipped with the repo.

## 1) Quick Start (Docker Compose)
- Build & start: `docker compose up -d`
- Status: `docker compose ps`
- Logs (all): `docker compose logs -f`
- Logs (one service): `docker compose logs -f <service>`
- Stop: `docker compose down`

## 2) Observability Endpoints & Ports (default compose values)
- Grafana: http://localhost:3000 (dashboards + Loki Explore; default creds: `admin` / `admin`)
- Prometheus: http://localhost:9090 (raw metrics, ad-hoc queries)
- Loki HTTP API: http://localhost:3100 (log store)
- Promtail (shipper): publishes container logs into Loki
- RabbitMQ Management UI: http://localhost:15672 (default creds: `guest` / `guest` unless overridden)
- Service container logs: via `docker compose logs -f <service>`

## 3) Metrics (Prometheus)
- Scrape targets: services expose metrics endpoints (typically `/metrics`) discovered via the compose network.
- Quick checks:
  - Open Prometheus UI → **Status > Targets** to verify all endpoints are `UP`.
  - Run ad-hoc queries (Examples):
    - `up{job="<service>"}` — liveness of scrape targets
    - `rate(http_requests_total{service="<service>"}[5m])` — request rate
    - `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{service="<service>"}[5m]))` — P95 latency

## 4) Dashboards & Logs (Grafana + Loki)
- Access Grafana at http://localhost:3000
- Dashboards: use or create service dashboards with Prometheus as the data source.
- Logs via Grafana Explore (Loki):
  - Data source: Loki
  - Basic query: `{container="<service>"}`
  - Filter by severity (if structured): `{container="<service>", level="error"}`
  - Time-align with metrics by selecting the same time window.

## 5) RabbitMQ Management UI
- URL: http://localhost:15672
- Check queues, consumers, message rates, and dead-letter queues.
- Useful views:
  - **Queues** → select queue → **Get messages** to peek payloads.
  - **Connections/Channels** to ensure consumers are live.
  - **Overview** to watch publish/ack rates.

## 6) Log Collection (Loki / Promtail)
- Container logs are forwarded by Promtail into Loki.
- If logs are missing in Loki:
  - `docker compose logs -f promtail`
  - Verify promtail config paths match container log locations.

## 7) Health & Readiness
- If services expose `/health` or `/ready`, curl from host or from within the compose network:
  - Host: `curl http://localhost:<mapped-port>/health`
  - In-network: `docker compose exec <service> curl http://<service>:<port>/health`

## 8) Common Diagnostics (Playbook)
- Service looks down in Prometheus `up`:
  - Check container: `docker compose ps` and `docker compose logs <service>`
  - Confirm port mapping and metrics endpoint availability (`curl http://<service>:<port>/metrics` inside network).
- Spikes in errors/latency:
  - Grafana: inspect P95/P99 latency panels; correlate with logs in Loki for same time window.
  - RabbitMQ: check queue backlogs and consumer acks.
- No logs in Loki for a service:
  - Confirm container is emitting logs to stdout/stderr.
  - Check promtail config and container labels; inspect promtail logs.
- Message processing stalls:
  - RabbitMQ UI: queue depth rising, consumers low/none.
  - Service logs: look for connection/auth errors to RabbitMQ or doc store.
- Unexpected restarts:
  - `docker compose ps` for restart count; `docker compose logs <service>` for crash reason.

## 8.1) End-to-End Pipeline Status (Mail Archive)
Use these signals to see whether a mail archive was ingested and where it is in the pipeline.

- Ingestion → Parsing → Chunking → Embedding → Summarization → Reporting
  - **RabbitMQ queues** (primary signal):
    - Open RabbitMQ UI → Queues; watch queue depth and unacked counts for each stage (ingestion, parsing, chunking, embedding, summarization, reporting).
    - If a queue grows and consumers stay low/idle, the pipeline is stuck at that stage.
  - **Logs per service** (Loki/Grafana Explore):
    - Query by container: `{container="ingestion"}` then `{container="parsing"}` etc.
    - Look for per-message IDs flowing across services (ingestion log ID should appear in downstream logs).
  - **Metrics (Prometheus/Grafana):**
    - Throughput: `rate(messages_processed_total{stage="ingestion"}[5m])` and similar for other stages if emitted.
    - Errors: `rate(stage_errors_total{stage="parsing"}[5m])` for spikes.
    - Queue depth via RabbitMQ exporter if enabled (e.g., `rabbitmq_queue_messages_ready{queue="ingestion"}`).

- How to tell if an archive is ingested:
  - Ingestion logs show download and publish events for the archive key or filename.
  - RabbitMQ ingestion queue decreases after publish, and parsing queue shows corresponding enqueued messages.
  - Downstream services emit logs referencing the same message ID as it progresses.

- How to tell downstream status:
  - Parsing: look for successful parse logs and messages moving from parsing queue to chunking queue.
  - Chunking: logs indicating chunks emitted; chunking queue drains while embedding queue fills.
  - Embedding: logs for vector creation; embedding queue drains; vector store writes succeed (check logs/metrics if emitted).
  - Summarization: logs for summary generation per thread/batch; queue drains accordingly.
  - Reporting: logs for report generation or delivery; reporting queue drains; final outputs written/stored.

- If stuck:
  - Check the stage’s queue depth and consumer count in RabbitMQ UI.
  - Inspect that stage’s container logs for errors (auth, schema, upstream/downstream unavailable).
  - Validate config/credentials for dependent services (doc store, vector store, message bus).

## 8.2) Using the Orchestrator
- Purpose: coordinates cross-service workflows and may dispatch work to the pipeline.
- Observability:
  - Metrics: `up{job="orchestrator"}` plus any orchestrator-specific counters (dispatch counts, failures).
  - Logs: `{container="orchestrator"}` in Loki for task submissions and error handling.
  - Queues: if orchestrator publishes jobs, watch the relevant RabbitMQ queues for growth/drain.
- Operations:
  - Trigger or requeue work via orchestrator endpoints/CLI (if exposed); confirm acceptance in logs.
  - If orchestration fails, check credentials and downstream availability (RabbitMQ, doc store, vector store).

## 9) Scaling & Load Debugging
- Horizontal scale in compose: `docker compose up -d --scale <service>=N` (if the service is stateless and supports scaling).
- Watch effects:
  - Prometheus: `rate(http_requests_total...)` per instance.
  - RabbitMQ: queue depth and consumer count.
  - Grafana/Loki: error rates per instance.

## 10) Cleanup & Reset
- Stop stack: `docker compose down`
- Remove volumes (destructive): `docker compose down -v`
- Clear Loki data (if stored in a volume) before re-running tests to start fresh.

## 11) Tips for Faster Troubleshooting
- Always correlate metrics (Prometheus) with logs (Loki) and queue state (RabbitMQ) on the same time window.
- Keep one Grafana tab on dashboards and one on Explore for logs.
- When adding new services, ensure they expose `/metrics` and log to stdout for Promtail to ingest.
- For persistent issues, capture: timestamps, Grafana screenshots, exact PromQL/Loki queries, and RabbitMQ queue stats.
