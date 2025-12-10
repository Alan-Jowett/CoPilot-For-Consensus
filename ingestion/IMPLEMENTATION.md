# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Implementation Guide: Ingestion Service

## Overview

This document describes the implementation of the **Ingestion Service** for the Copilot-for-Consensus system. The service fetches mailing list archives from various sources and publishes events to notify downstream services.

## Architecture

The ingestion service is built with the following components:

### Core Modules

1. **`config.py`** - Configuration Management
   - `SourceConfig`: Configuration for individual archive sources
   - `IngestionConfig`: Overall service configuration
   - Environment variable expansion and YAML file loading
   - Support for multiple source types (rsync, IMAP, HTTP, local filesystem)

2. **`models.py`** - Data Models
   - `ArchiveIngestedEvent`: Event published when archive is successfully ingested
   - `ArchiveIngestionFailedEvent`: Event published when ingestion fails
   - `ArchiveMetadata`: Metadata for ingested archives

3. **`event_publisher.py`** - Event Publishing
   - `EventPublisher`: Abstract base class for event publishers
   - `RabbitMQPublisher`: RabbitMQ implementation
   - `NoopPublisher`: No-op implementation for testing
   - `create_publisher()`: Factory function for creating publishers

4. **`archive_fetcher.py`** - Archive Fetching
   - `ArchiveFetcher`: Abstract base class for archive fetchers
   - `RsyncFetcher`: Fetch archives via rsync (IETF archives)
   - `HTTPFetcher`: Fetch archives via HTTP
   - `LocalFetcher`: Copy archives from local filesystem
   - `IMAPFetcher`: Fetch emails via IMAP
   - `calculate_file_hash()`: SHA256 hashing utility
   - `create_fetcher()`: Factory function for creating fetchers

5. **`service.py`** - Main Service Logic
   - `IngestionService`: Main ingestion service class
   - Archive deduplication via checksums
   - Metadata logging
   - Event publishing
   - Retry logic with exponential backoff

### Testing

1. **Unit Tests** (`tests/`)
   - `test_config.py`: Configuration loading and validation
   - `test_event_publisher.py`: Event publishing
   - `test_archive_fetcher.py`: Archive fetching logic
   - `test_service.py`: Ingestion service logic

2. **Integration Tests** (`tests/`)
   - `test_integration.py`: End-to-end workflow testing
   - Multiple source ingestion
   - Deduplication verification
   - Event publishing verification
   - Storage directory structure verification

## Configuration

### Environment Variables

```bash
# Storage
STORAGE_PATH=/data/raw_archives              # Where to store fetched archives
CONFIG_FILE=/app/config.yaml                 # Path to YAML config file

# Message Bus (RabbitMQ)
MESSAGE_BUS_HOST=messagebus                  # RabbitMQ host
MESSAGE_BUS_PORT=5672                        # RabbitMQ port
MESSAGE_BUS_USER=guest                       # RabbitMQ username
MESSAGE_BUS_PASSWORD=guest                   # RabbitMQ password
MESSAGE_BUS_TYPE=rabbitmq                    # "rabbitmq" or "noop"

# Scheduling
INGESTION_SCHEDULE_CRON="0 */6 * * *"        # Every 6 hours (not used in main loop)

# Retry Policy
RETRY_MAX_ATTEMPTS=3                         # Max retries per source
RETRY_BACKOFF_SECONDS=60                     # Base backoff time

# Logging
LOG_LEVEL=INFO                               # DEBUG, INFO, WARNING, ERROR

# Blob Storage (optional)
BLOB_STORAGE_ENABLED=false
BLOB_STORAGE_CONNECTION_STRING=...
BLOB_STORAGE_CONTAINER=raw-archives
```

### Configuration File (config.yaml)

```yaml
sources:
  - name: "ietf-quic"
    type: "rsync"
    url: "rsync.ietf.org::mailman-archive/quic/"
    enabled: true

  - name: "custom-imap"
    type: "imap"
    url: "imap.example.com"
    port: 993
    username: "${IMAP_USERNAME}"
    password: "${IMAP_PASSWORD}"
    folder: "INBOX"
    enabled: false

  - name: "custom-http"
    type: "http"
    url: "https://example.com/archives.mbox"
    enabled: false

  - name: "local-archive"
    type: "local"
    url: "/path/to/local/archives"
    enabled: false
```

## Data Flow

```
┌─────────────────────┐
│  Configuration      │
│  - Sources          │
│  - Retry policy     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Fetch Archive       │
│ - Rsync             │
│ - HTTP              │
│ - IMAP              │
│ - Local FS          │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Calculate Hash      │
│ SHA256              │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Check Dedup         │
│ (checksums.json)    │
└──────┬──────────┬───┘
       │          │
   Duplicate   New Archive
       │          │
       ▼          ▼
     Skip    ┌─────────────────┐
            │ Store Archive   │
            │ Save Metadata   │
            └────────┬────────┘
                     │
                     ▼
            ┌─────────────────┐
            │ Publish Event   │
            │ ArchiveIngested │
            └─────────────────┘
```

## Event Schemas

### ArchiveIngested Event

Published when an archive is successfully fetched and stored.

```json
{
  "event_type": "ArchiveIngested",
  "event_id": "uuid",
  "timestamp": "2023-01-01T00:00:00Z",
  "version": "1.0",
  "data": {
    "archive_id": "uuid",
    "source_name": "ietf-quic",
    "source_type": "rsync",
    "source_url": "rsync.ietf.org::mailman-archive/quic/",
    "file_path": "/data/raw_archives/ietf-quic/2023-10.mbox",
    "file_size_bytes": 1024000,
    "file_hash_sha256": "abc123...",
    "ingestion_started_at": "2023-01-01T00:00:00Z",
    "ingestion_completed_at": "2023-01-01T00:05:00Z"
  }
}
```

### ArchiveIngestionFailed Event

Published when archive ingestion fails after all retries.

```json
{
  "event_type": "ArchiveIngestionFailed",
  "event_id": "uuid",
  "timestamp": "2023-01-01T00:00:00Z",
  "version": "1.0",
  "data": {
    "source_name": "ietf-quic",
    "source_type": "rsync",
    "source_url": "rsync.ietf.org::mailman-archive/quic/",
    "error_message": "Connection timeout",
    "error_type": "TimeoutError",
    "retry_count": 3,
    "ingestion_started_at": "2023-01-01T00:00:00Z",
    "failed_at": "2023-01-01T00:15:00Z"
  }
}
```

## Storage Structure

```
/data/raw_archives/
├── ietf-quic/
│   ├── 2023-10.mbox
│   ├── 2023-11.mbox
│   └── 2023-12.mbox
├── ietf-tls/
│   └── 2023-10.mbox
└── metadata/
    ├── checksums.json
    └── ingestion_log.jsonl
```

### checksums.json

Maps file hashes to metadata for deduplication:

```json
{
  "abc123def456...": {
    "archive_id": "uuid",
    "file_path": "/data/raw_archives/ietf-quic/2023-10.mbox",
    "first_seen": "2023-01-01T00:00:00Z"
  }
}
```

### ingestion_log.jsonl

JSON Lines format log of all ingestion operations:

```jsonl
{"archive_id": "uuid1", "source_name": "ietf-quic", "source_type": "rsync", "source_url": "...", "file_path": "...", "file_size_bytes": 1024000, "file_hash_sha256": "...", "ingestion_started_at": "...", "ingestion_completed_at": "...", "status": "success"}
{"archive_id": "uuid2", "source_name": "ietf-tls", "source_type": "rsync", "source_url": "...", "file_path": "...", "file_size_bytes": 2048000, "file_hash_sha256": "...", "ingestion_started_at": "...", "ingestion_completed_at": "...", "status": "success"}
```

## Testing

### Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run unit tests only
pytest tests/test_config.py tests/test_event_publisher.py tests/test_archive_fetcher.py tests/test_service.py

# Run integration tests only
pytest tests/test_integration.py

# Run with coverage
pytest --cov=app tests/

# Run specific test
pytest tests/test_service.py::TestIngestionService::test_ingest_archive_success
```

### Test Coverage

The test suite includes:

**Unit Tests:**
- Configuration loading and validation
- Source configuration with environment variables
- Event creation and serialization
- Publisher implementations (Noop)
- Archive fetcher (Local, mocking others)
- Service initialization and checksum management
- Archive ingestion workflow
- Deduplication logic
- Event publishing

**Integration Tests:**
- End-to-end ingestion workflow
- Multiple source ingestion
- Duplicate archive handling
- Mixed enabled/disabled sources
- Checksum persistence across instances
- Ingestion log format verification
- Published event format verification
- Storage directory structure verification

## Implementation Details

### Archive Fetching

The service supports multiple fetcher types:

1. **Rsync** (`RsyncFetcher`)
   - Uses system `rsync` command
   - Ideal for IETF archives
   - Supports incremental syncs with `--delete`
   - URL format: `rsync.ietf.org::mailman-archive/quic/`

2. **HTTP** (`HTTPFetcher`)
   - Downloads archives via HTTP/HTTPS
   - Requires `requests` library
   - Useful for web-hosted archives

3. **IMAP** (`IMAPFetcher`)
   - Retrieves emails from IMAP servers
   - Requires `imapclient` library
   - Saves messages to mbox format
   - Supports username/password authentication

4. **Local** (`LocalFetcher`)
   - Copies files/directories from local filesystem
   - Useful for testing and local archives
   - Supports both files and directories

### Deduplication

Archives are deduplicated using SHA256 hashing:

1. After fetching, compute file hash
2. Check if hash exists in `checksums.json`
3. If exists, skip (already ingested)
4. If new, store archive and publish event

This prevents reprocessing of identical archives.

### Retry Logic

Failed fetches are retried with exponential backoff:

1. Initial attempt
2. Wait `RETRY_BACKOFF_SECONDS` seconds
3. Retry with backoff = backoff × 2
4. Continue until `RETRY_MAX_ATTEMPTS` reached
5. If all attempts fail, publish `ArchiveIngestionFailed` event

### Event Publishing

Events are published to RabbitMQ with:

- Exchange: `copilot.events`
- Routing Key: `archive.ingested` or `archive.ingestion.failed`
- Format: JSON
- Guaranteed delivery if publisher connected

### Logging

All operations are logged with:

1. **Console output**: Real-time operational logs
2. **Ingestion log**: Persistent record in `ingestion_log.jsonl`
3. **Log levels**: DEBUG, INFO, WARNING, ERROR

## Docker Deployment

The service runs in a Docker container:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "main.py"]
```

Environment variables should be set in `docker-compose.yml` or `.env` file.

## Performance Considerations

1. **Large Archives**: rsync efficiently syncs only changed files
2. **Deduplication**: O(1) lookup in `checksums.json`
3. **Hashing**: Files are hashed sequentially; streaming for large files
4. **Retry Backoff**: Prevents hammering failed sources
5. **Connection Pooling**: RabbitMQ connection reused across publishes

## Error Handling

The service handles:

1. **Network errors**: Retries with exponential backoff
2. **Missing dependencies**: Clear error messages
3. **Invalid configuration**: Validation at startup
4. **Publisher failures**: Logs error but continues
5. **Storage errors**: Logs and skips problematic archives

## Future Enhancements

1. Scheduled ingestion (using APScheduler or similar)
2. Webhook notifications for downstream services
3. Incremental rsync tracking for bandwidth optimization
4. Support for S3/Azure Blob storage
5. Archive compression and encryption
6. Parallel source ingestion
7. Metrics/monitoring integration
