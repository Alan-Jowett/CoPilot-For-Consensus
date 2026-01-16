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

# Access REST API via gateway in Docker
curl http://localhost:8080/ingestion/health
curl http://localhost:8080/ingestion/api/sources

# Access REST API when running standalone (no gateway)
# curl http://localhost:8080/health
# curl http://localhost:8080/api/sources
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
  - **Hash Override:** Explicitly triggering ingestion will delete any existing checksums for the source, forcing re-ingestion of all files even if they were previously processed. This allows manual re-processing of content when needed.
- `GET /ingestion/api/sources/{name}/status` - Get source ingestion status

#### File Upload

- `POST /api/uploads` - Upload a mailbox file (.mbox, .zip, .tar, .tar.gz, .tgz up to 100MB)

### API Examples

```bash
# List all sources
curl http://localhost:8080/ingestion/api/sources

# Upload a mailbox file
curl -X POST http://localhost:8080/api/uploads \
  -F "file=@/path/to/local/archive.mbox"

# Response includes server path to use when creating a source
# {
#   "filename": "archive.mbox",
#   "server_path": "/data/raw_archives/uploads/archive.mbox",
#   "size_bytes": 12345,
#   "uploaded_at": "2025-12-19T20:30:00Z",
#   "suggested_source_type": "local"
# }

# Create a new source using uploaded file
curl -X POST http://localhost:8080/api/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "uploaded-mailbox",
    "source_type": "local",
    "url": "/data/raw_archives/uploads/archive.mbox",
    "enabled": true
  }'

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
# Note: This will delete existing checksums for the source and force re-ingestion
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
| `INGESTION_SOURCES_STORE_TYPE` | `document_store` | Backend for source storage: `document_store` (default, production) or `file` (dev/legacy) |
| `INGESTION_SOURCES_FILE_PATH` | `None` | Path to sources JSON file (only used when `SOURCES_STORE_TYPE=file`) |
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

### Source Storage Backends

The ingestion service supports two backends for storing and loading source configurations:

#### Document Store Backend (Default, Recommended for Production)

- **Configuration:** `INGESTION_SOURCES_STORE_TYPE=document_store` (default)
- **Storage:** Sources are stored in the `sources` collection in the configured document store (MongoDB/CosmosDB)
- **Management:** Sources are fully managed via REST API CRUD operations
- **Scheduler:** Periodic ingestion uses sources from the document store (single source of truth)
- **Use Case:** Production deployments where sources need dynamic management

#### File Backend (Legacy/Development)

- **Configuration:** `INGESTION_SOURCES_STORE_TYPE=file`
- **Storage:** Sources are loaded from a JSON file at startup
- **File Path:** Set via `INGESTION_SOURCES_FILE_PATH` or legacy `INGESTION_SOURCES_CONFIG_PATH` env var
- **Default File:** Falls back to `ingestion/config.json` if no path is specified
- **Scheduler:** Periodic ingestion uses sources from the startup file (immutable during runtime)
- **Use Case:** Development, testing, or deployments with static source configuration

**Migration Path:** When switching from file to document_store backend, any sources provided at startup will be automatically merged into the document store on first run (deduplicated by name).

### Source Configuration

**Default Behavior (Production):** Sources are managed dynamically via the REST API and stored in the document database. No static configuration file is required.

**Legacy/Development Mode:** For static source configuration, set `INGESTION_SOURCES_STORE_TYPE=file` and optionally specify a file path with `INGESTION_SOURCES_FILE_PATH`. Example file format:

```json
{
  "sources": [
    {
      "name": "ietf-quic",
      "source_type": "rsync",
      "url": "rsync.ietf.org::mailman-archive/quic/",
      "enabled": true
    },
    {
      "name": "archive-http",
      "source_type": "http",
      "url": "https://example.com/archives.mbox",
      "enabled": true
    },
    {
      "name": "mail-archive",
      "source_type": "imap",
      "url": "imap.example.com",
      "port": 993,
      "username": "${IMAP_USERNAME}",
      "password": "${IMAP_PASSWORD}",
      "folder": "INBOX",
      "enabled": true
    },
    {
      "name": "local-test",
      "source_type": "local",
      "url": "/path/to/local/archives",
      "enabled": false
    }
  ]
}
```

For production deployments using the default document_store backend, use the REST API to create sources dynamically instead of maintaining a static configuration file.

## UI Upload Workflow

The web UI provides a user-friendly file upload feature for local mailbox ingestion:

1. Navigate to the "Sources" page in the web UI
2. Click "Add New Source"
3. Select "LOCAL" as the source type
4. Click "Upload Mailbox File" and select a `.mbox`, `.zip`, or `.tar` file (up to 100MB)
5. Watch the progress bar as the file uploads
6. Once uploaded, the URL field is automatically populated with the server path
7. Provide a source name and click "Create Source"
8. Optionally click "Trigger" to start ingestion immediately

This workflow eliminates the need for `docker cp` and makes local mailbox ingestion accessible to non-technical users.

## Events Published

The service publishes events to RabbitMQ with automatic schema validation. All events are validated against their JSON schemas before being published, ensuring data consistency across the system. See [../docs/schemas/data-storage.md](../docs/schemas/data-storage.md#message-bus-event-schemas) for complete schemas.

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
├── uploads/                 # User-uploaded files
│   ├── mailbox1.mbox
│   └── archive.zip
├── ietf-quic/2023-10.mbox
├── ietf-tls/2023-10.mbox
└── metadata/
    ├── checksums.json       # SHA256 hash index for deduplication
    └── ingestion_log.jsonl  # Audit log of all operations
```

**Upload Directory**: Files uploaded via the UI or `/api/uploads` endpoint are stored in `/data/raw_archives/uploads/`. These files are available for reference when creating local sources.

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
