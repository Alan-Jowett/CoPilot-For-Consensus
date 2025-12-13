<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Ingestion Service

The Ingestion Service fetches mailing list archives from multiple sources and publishes events when new archives are available for downstream processing.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (42+ tests)
pytest tests/ -v

# Run service
MESSAGE_BUS_TYPE=noop python main.py          # Testing mode
MESSAGE_BUS_HOST=localhost python main.py      # With RabbitMQ
```

## Features

- **Multiple Source Types:** rsync, HTTP/HTTPS, IMAP, local filesystem
- **Event Publishing:** RabbitMQ integration with schema-compliant events
- **Schema Validation:** All published events are automatically validated against JSON schemas
- **Deduplication:** SHA256-based duplicate detection with persistent checksums
- **Retry Logic:** Exponential backoff for failed fetches
- **Audit Logging:** JSONL format for all ingestion operations
- **Flexible Configuration:** Environment variables for configuration

## Technology Stack

- **Python 3.10+**
- **Dependencies:** pika (RabbitMQ), requests, imapclient, python-dotenv

## Architecture

### Project Structure

```
ingestion/
├── app/
│   ├── config.py              # Configuration management
│   ├── models.py              # Event and metadata models
│   ├── event_publisher.py     # RabbitMQ/Noop publisher
│   ├── archive_fetcher.py     # Source type implementations
│   └── service.py             # Main ingestion orchestration
├── tests/                     # 42+ unit and integration tests
├── main.py                    # Service entry point
├── requirements.txt           # Python dependencies
└── Dockerfile                 # Container image
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_PATH` | `/data/raw_archives` | Archive storage location |
| `MESSAGE_BUS_TYPE` | `rabbitmq` | `rabbitmq` or `noop` |
| `MESSAGE_BUS_HOST` | `messagebus` | RabbitMQ hostname |
| `MESSAGE_BUS_PORT` | `5672` | RabbitMQ port |
| `MESSAGE_BUS_USER` | `guest` | RabbitMQ username |
| `MESSAGE_BUS_PASSWORD` | `guest` | RabbitMQ password |
| `LOG_LEVEL` | `INFO` | Logging level |
| `RETRY_MAX_ATTEMPTS` | `3` | Max retry attempts |
| `RETRY_BACKOFF_SECONDS` | `60` | Retry backoff time |

### Source Configuration (config.yaml)

Define archive sources in YAML format. Environment variables are expanded using `${VAR}` syntax:

```yaml
sources:
  # Rsync source (IETF archives)
  - name: "ietf-quic"
    type: "rsync"
    url: "rsync.ietf.org::mailman-archive/quic/"
    enabled: true
    
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
