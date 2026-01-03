<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Reporting Service

## Overview

The Reporting Service delivers summaries and insights to users via REST endpoints and optional push notifications. It consumes completed summaries, stores them with citations, and exposes searchable, filterable reports for dashboards or downstream systems. It can operate fully offline using local storage and self-hosted vector/document stores.

## Purpose

- Persist completed summaries with citations and metadata
- Serve summaries and reports via REST for dashboards/clients
- Provide filters (thread, working group, date, draft) and search
- Optionally emit notifications/webhooks when new reports arrive

## Responsibilities

- **Event ingestion:** Consume `SummaryComplete` events and store reports
- **API delivery:** Expose REST endpoints for summaries, threads, and search
- **Export:** Provide Markdown/JSON exports with citations
- **Filtering/search:** Query by thread, date range, draft mentions, sender
- **Notifications (optional):** Send webhooks or messages to chat channels
- **Health & observability:** Expose health, metrics, and structured logs

## Technology Stack

- **Language:** Python 3.10+
- **Framework:** Flask (REST)
- **Message Bus:** RabbitMQ (default) or Azure Service Bus
- **Storage:** MongoDB for summaries and metadata; Vector store for semantic search (optional)
- **Observability:** Prometheus metrics + structured JSON logs

## Configuration

### Environment Variables

| Variable | Type | Required | Default | Description |
|----------|------|----------|---------|-------------|
| `MESSAGE_BUS_HOST` | String | Yes | `messagebus` | Message bus hostname |
| `MESSAGE_BUS_PORT` | Integer | No | `5672` | Message bus port |
| `MESSAGE_BUS_USER` | String | No | `guest` | Message bus username |
| `MESSAGE_BUS_PASSWORD` | String | No | `guest` | Message bus password |
| `DOCUMENT_DATABASE_HOST` | String | Yes | `documentdb` | Document DB host |
| `DOCUMENT_DATABASE_PORT` | Integer | No | `27017` | Document DB port |
| `DOCUMENT_DATABASE_NAME` | String | No | `copilot` | Database name |
| `REPORTS_COLLECTION` | String | No | `summaries` | Collection for summaries/reports |
| `VECTOR_DB_HOST` | String | No | `vectorstore` | Vector store host (for search) |
| `VECTOR_DB_PORT` | Integer | No | `6333` | Vector store port (Qdrant) |
| `VECTOR_DB_COLLECTION` | String | No | `message_embeddings` | Collection for embeddings |
| `API_PORT` | Integer | No | `8080` | HTTP server port |
| `NOTIFY_WEBHOOK_URL` | String | No | - | Webhook for notifications (Slack/Teams/etc.) |
| `NOTIFY_ENABLED` | Boolean | No | `false` | Enable webhook notifications |
| `LOG_LEVEL` | String | No | `INFO` | Logging level |

## Events

### Subscribes To

The Reporting Service subscribes to the following events. See [SCHEMA.md](../docs/schemas/data-storage.md#message-bus-event-schemas) for complete event schemas.

1) **SummaryComplete**
   - **Exchange:** `copilot.events`
   - **Routing Key:** `summary.complete`
   - See [SummaryComplete schema](../docs/schemas/data-storage.md#11-summarycomplete) in SCHEMA.md
   - **Behavior:** Persist summary and citations; index for search/filtering; optionally notify downstream channels.

### Publishes

The Reporting Service publishes the following events. See [SCHEMA.md](../docs/schemas/data-storage.md#message-bus-event-schemas) for complete event schemas.

1) **ReportPublished**
   - **Exchange:** `copilot.events`
   - **Routing Key:** `report.published`
   - See [ReportPublished schema](../docs/schemas/data-storage.md#13-reportpublished) in SCHEMA.md
   - **Behavior:** Signals that a report has been published and is available via API with notification status.

2) **ReportDeliveryFailed** *(optional)*
   - **Exchange:** `copilot.events`
   - **Routing Key:** `report.delivery_failed`
   - See [ReportDeliveryFailed schema](../docs/schemas/data-storage.md#14-reportdeliveryfailed) in SCHEMA.md
   - **Behavior:** Signals that report delivery (e.g., webhook notification) failed with retry details.

## Data Flow

```mermaid
graph LR
    A[SummaryComplete Event] --> B[Reporting Service]
    B --> C[Document DB (MongoDB)]
    B --> D[Vector Store (Qdrant)]
    C --> B
    D --> B
    B --> E[ReportPublished Event]
    E --> F[Dashboards / Webhooks]
```

## API Endpoints

### Reports
- `GET /health` — health and config snapshot
- `GET /api/reports` — list reports (filters: `thread_id`, `start_date`, `end_date`, `source`, `min_participants`, `max_participants`, `min_messages`, `max_messages`)
- `GET /api/reports/<report_id>` — fetch a specific report with citations
- `GET /api/reports/search?topic=<query>` — semantic search over summaries (requires vector store)
- `GET /api/threads/<thread_id>/summary` — fetch latest summary for a thread
- `GET /api/sources` — list available archive sources

### Threads (Citation Drilldown)
- `GET /api/threads` — list threads (filters: `archive_id`, pagination: `limit`, `skip`)
- `GET /api/threads/<thread_id>` — fetch a specific thread with metadata (subject, participants, message count, dates)

### Messages (Citation Drilldown)
- `GET /api/messages` — list messages (filters: `thread_id`, `message_id`, pagination: `limit`, `skip`)
- `GET /api/messages/<message_doc_id>` — fetch a specific message with headers, body, and metadata

### Chunks (Citation Drilldown)
- `GET /api/chunks` — list chunks (filters: `message_id`, `thread_id`, `message_doc_id`, pagination: `limit`, `skip`)
- `GET /api/chunks/<chunk_id>` — fetch a specific chunk with text and offsets

### Citation Drilldown Navigation
The new endpoints enable navigation from report citations to original content:
1. Start with a report citation (contains `chunk_id` and `message_id`)
2. Use `GET /api/chunks/<chunk_id>` to retrieve the chunk with context
3. Use `GET /api/messages/<message_doc_id>` to view the full message
4. Use `GET /api/threads/<thread_id>` to see thread metadata
5. Use `GET /api/messages?thread_id=<thread_id>` to browse all messages in the thread

## Storage Model (example)

```json
{
  "report_id": "rpt-01HXYZ...",
  "thread_id": "<20250115120000.XYZ789@example.com>",
  "summary_markdown": "- Consensus: ...",
  "citations": [
    {"message_id": "<20231015123456.ABC123@example.com>", "chunk_id": "a1b2c3", "offset": 120}
  ],
  "llm_backend": "ollama",
  "llm_model": "mistral",
  "tokens_prompt": 1800,
  "tokens_completion": 600,
  "latency_ms": 2400,
  "created_at": "2025-01-15T15:05:00Z",
  "updated_at": "2025-01-15T15:05:00Z"
}
```

## Error Handling

- Retries with backoff for message processing and webhook delivery
- Dead-letter queue for irrecoverable events
- Input validation on payload schemas and filters
- Timeouts/circuit breakers for DB or vector store access

## Monitoring & Metrics

Prometheus metrics at `/metrics`:
- `reporting_events_total` (labeled by event_type, outcome)
- `reporting_delivery_total` (labeled by channel, status)
- `reporting_latency_seconds` (histogram for end-to-end ingest → publish)
- `reporting_failures_total` (labeled by error_type)

Structured JSON logs include thread_id, report_id, backend, model, and latency.

## Dependencies

- **Message Bus:** RabbitMQ or Azure Service Bus
- **Document DB:** MongoDB for summaries and citations
- **Vector Store:** Qdrant for semantic search (optional)
- **Webhooks:** Slack/Teams/HTTP endpoints if notifications are enabled

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
export MESSAGE_BUS_HOST=localhost
export DOCUMENT_DATABASE_HOST=localhost
python main.py

# Docker
docker build -t copilot-reporting .
docker run -d \
  -e MESSAGE_BUS_HOST=messagebus \
  -e DOCUMENT_DATABASE_HOST=documentdb \
  -p 8080:8080 \
  copilot-reporting
```

## Future Enhancements

- [ ] Dashboard UI with charts and filters
- [ ] PDF export with inline citations
- [ ] Per-tenant branding/themes
- [ ] Advanced search (hybrid semantic + keyword)
- [ ] Access control and API tokens
