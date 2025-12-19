<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Ingestion Service

The Ingestion Service is a continuously running service that fetches mailing list archives from multiple sources and publishes events when new archives are available for downstream processing. It provides a REST API for managing ingestion sources and triggering on-demand ingestions.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (42+ tests)
pytest tests/ -v

# Run service (continuous mode with REST API)
HTTP_PORT=8080 python main.py

# Access REST API (via gateway in Docker: http://localhost:8080/ingestion/...)
curl http://localhost:8080/health
curl http://localhost:8080/ingestion/api/sources
```

## Features

- **Continuous Operation:** Runs as a long-lived service with periodic ingestion
- **REST API:** Full CRUD operations for source management
- **Multiple Source Types:** rsync, HTTP/HTTPS, IMAP, local filesystem
- **Event Publishing:** RabbitMQ integration with schema-compliant events
- **Schema Validation:** All published events are automatically validated against JSON schemas
- **Deduplication:** SHA256-based duplicate detection with persistent checksums
- **Retry Logic:** Exponential backoff for failed fetches
- **Audit Logging:** JSONL format for all ingestion operations
- **Scheduler:** Configurable periodic ingestion intervals
- **Health & Metrics:** Built-in endpoints for monitoring

## Technology Stack

- **Python 3.10+**
- **FastAPI:** REST API framework
- **Uvicorn:** ASGI server
- **Dependencies:** pika (RabbitMQ), requests, imapclient, python-dotenv

## Architecture

### Project Structure

```
ingestion/
├── app/
│   ├── api.py                 # REST API endpoints
│   ├── scheduler.py           # Periodic ingestion scheduler
│   ├── service.py             # Main ingestion orchestration
│   └── exceptions.py          # Custom exceptions
├── tests/                     # Unit and integration tests
│   ├── test_api.py            # API endpoint tests
│   ├── test_scheduler.py      # Scheduler tests
│   └── test_service.py        # Service logic tests
├── main.py                    # Service entry point
├── requirements.txt           # Python dependencies
└── Dockerfile                 # Container image
```

## REST API

The service exposes a REST API on port 8080 (configurable via `HTTP_PORT` environment variable).

### Endpoints

#### Health & Stats

- `GET /health` - Health check with service status
- `GET /stats` - Service statistics (sources, files ingested, etc.)

#### Source Management

- `GET /ingestion/api/sources` - List all sources (supports `?enabled_only=true`)
- `GET /ingestion/api/sources/{name}` - Get specific source details
- `POST /ingestion/api/sources` - Create a new source
- `PUT /ingestion/api/sources/{name}` - Update an existing source
- `DELETE /ingestion/api/sources/{name}` - Delete a source

#### Source Operations

- `POST /ingestion/api/sources/{name}/trigger` - Trigger manual ingestion for a source
- `GET /ingestion/api/sources/{name}/status` - Get source ingestion status

### API Examples

```bash
# List all sources
curl http://localhost:8080/ingestion/api/sources

# Create a new source
curl -X POST http://localhost:8080/ingestion/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ietf-quic",
    "source_type": "rsync",
    "url": "rsync.ietf.org::mailman-archive/quic/",
    "enabled": true
  }'

# Trigger manual ingestion
curl -X POST http://localhost:8080/ingestion/api/sources/ietf-quic/trigger

# Get source status
curl http://localhost:8080/ingestion/api/sources/ietf-quic/status

# Update source
curl -X PUT http://localhost:8080/ingestion/api/sources/ietf-quic \
  -H "Content-Type: application/json" \
  -d '{
    "name": "ietf-quic",
    "source_type": "rsync",
    "url": "rsync.ietf.org::mailman-archive/quic/",
    "enabled": false
  }'

# Delete source
curl -X DELETE http://localhost:8080/ingestion/api/sources/ietf-quic
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_PORT` | `8080` | HTTP API server port |
| `INGESTION_SCHEDULE_INTERVAL_SECONDS` | `21600` | Interval between scheduled ingestions (6 hours) |
| `STORAGE_PATH` | `/data/raw_archives` | Archive storage location |
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `rabbitmq` or `noop` |
| `MESSAGE_BUS_HOST` | `messagebus` | RabbitMQ hostname |
| `MESSAGE_BUS_PORT` | `5672` | RabbitMQ port |
| `MESSAGE_BUS_USER` | `guest` | RabbitMQ username |
| `MESSAGE_BUS_PASSWORD` | `guest` | RabbitMQ password |
| `DOCUMENT_STORE_TYPE` | `mongodb` | Document store type |
| `DOCUMENT_DATABASE_HOST` | `documentdb` | Document store hostname |
| `DOCUMENT_DATABASE_PORT` | `27017` | Document store port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `RETRY_BACKOFF_SECONDS` | `60` | Retry backoff time |

### Source Configuration

Sources are managed via the REST API and stored in the document database. They can also be pre-configured in the database.
    
  # HTTP/HTTPS source
  - name: "archive-http"
    type: "http"
    url: "https://example.com/archives.mbox"
    enabled: true
    
  # IMAP source
  - name: "mail-archive"
    type: "imap"
    url: "imap.example.com"
    port: 993
    username: "${IMAP_USERNAME}"
    password: "${IMAP_PASSWORD}"
    folder: "INBOX"
    enabled: true
    
  # Local filesystem (testing)
  - name: "local-test"
    type: "local"
    url: "/path/to/local/archives"
    enabled: false
```

## Events Published

The service publishes events to RabbitMQ with automatic schema validation. All events are validated against their JSON schemas before being published, ensuring data consistency across the system. See [../documents/SCHEMA.md](../documents/SCHEMA.md) for complete schemas.

### ArchiveIngested

Published when an archive is successfully fetched and stored.

- **Exchange:** `copilot.events`
- **Routing Key:** `archive.ingested`
- **Key Fields:** `archive_id`, `source_name`, `source_type`, `file_path`, `file_hash_sha256`, timestamps

### ArchiveIngestionFailed

Published when ingestion fails after all retries.

- **Exchange:** `copilot.events`
- **Routing Key:** `archive.ingestion.failed`
- **Key Fields:** `source_name`, `error_message`, `error_type`, `retry_count`, `failed_at`

## Storage

Archives are organized by source with metadata for deduplication:

```
/data/raw_archives/
├── ietf-quic/2023-10.mbox
├── ietf-tls/2023-10.mbox
└── metadata/
    ├── checksums.json       # SHA256 hash index for deduplication
    └── ingestion_log.jsonl  # Audit log of all operations
```

## Testing

```bash
# Run all tests (42+ unit and integration tests)
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test suite
pytest tests/test_service.py -v
```

## Docker Deployment

```bash
# Build image
docker build -t ingestion-service .

# Run with RabbitMQ
docker run -d \
  -e MESSAGE_BUS_HOST=rabbitmq \
  -v raw_archives:/data/raw_archives \
  ingestion-service
```

## Development

```bash
# Install dependencies
pip install -r requirements.txt pytest

# Run with local testing
MESSAGE_BUS_TYPE=noop LOG_LEVEL=DEBUG python main.py

# Run tests during development
pytest tests/ -vv --tb=short
```
- [ ] Parallel ingestion from multiple sources
- [ ] Archive compression before storage
- [ ] Webhook support for push-based ingestion
- [ ] Real-time IMAP monitoring (IDLE command)
- [ ] Archive splitting for large files
- [ ] Built-in archive validation (mbox format check)
