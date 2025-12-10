# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

# Quick Start Guide: Ingestion Service

## 5-Minute Setup

### 1. Install Dependencies

```bash
cd ingestion
pip install -r requirements.txt pytest
```

### 2. Run Tests

```bash
pytest tests/ -v
```

Expected: **39+ tests passing** ✅

### 3. Configure

Copy and edit configuration:

```bash
cp .env.example .env
cp config.yaml config.yaml.local
```

Edit `config.yaml.local` to add your sources:

```yaml
sources:
  - name: "ietf-quic"
    type: "rsync"
    url: "rsync.ietf.org::mailman-archive/quic/"
    enabled: true
```

### 4. Run Service

```bash
# With noop publisher (for testing)
MESSAGE_BUS_TYPE=noop python main.py

# With RabbitMQ
MESSAGE_BUS_HOST=localhost python main.py

# With custom config
CONFIG_FILE=config.yaml.local python main.py
```

## What You Get

### Event Publishing
```
[ArchiveIngested] ──→ RabbitMQ
                       └─→ Parsing Service
```

### Local Storage
```
/data/raw_archives/
├── ietf-quic/2023-10.mbox
├── ietf-tls/2023-10.mbox
└── metadata/
    ├── checksums.json (deduplication index)
    └── ingestion_log.jsonl (audit trail)
```

### Metadata Files
```
checksums.json
{
  "abc123...": {
    "archive_id": "uuid",
    "file_path": "/data/raw_archives/ietf-quic/2023-10.mbox",
    "first_seen": "2023-01-01T00:00:00Z"
  }
}

ingestion_log.jsonl
{"archive_id": "...", "source_name": "ietf-quic", "status": "success", ...}
```

## Supported Source Types

### Rsync (IETF Archives)
```yaml
- name: "ietf-quic"
  type: "rsync"
  url: "rsync.ietf.org::mailman-archive/quic/"
  enabled: true
```

### HTTP Downloads
```yaml
- name: "archive-http"
  type: "http"
  url: "https://example.com/archives.mbox"
  enabled: true
```

### IMAP Servers
```yaml
- name: "archive-imap"
  type: "imap"
  url: "imap.example.com"
  port: 993
  username: "user@example.com"
  password: "${IMAP_PASSWORD}"
  folder: "INBOX"
  enabled: true
```

### Local Filesystem
```yaml
- name: "archive-local"
  type: "local"
  url: "/path/to/archives"
  enabled: true
```

## Environment Variables

```bash
# Storage
export STORAGE_PATH=/data/raw_archives

# Message Bus (RabbitMQ or noop for testing)
export MESSAGE_BUS_TYPE=rabbitmq
export MESSAGE_BUS_HOST=localhost
export MESSAGE_BUS_PORT=5672
export MESSAGE_BUS_USER=guest
export MESSAGE_BUS_PASSWORD=guest

# Service
export LOG_LEVEL=INFO
export RETRY_MAX_ATTEMPTS=3
export RETRY_BACKOFF_SECONDS=60

# Configuration file
export CONFIG_FILE=config.yaml
```

## Example: Local Testing

```bash
# Create test archives
mkdir -p /tmp/test_archives
echo "From: user@example.com" > /tmp/test_archives/test.mbox

# Configure for testing
cat > test-config.yaml <<EOF
sources:
  - name: "test-archive"
    type: "local"
    url: "/tmp/test_archives"
    enabled: true
EOF

# Run with test publisher
CONFIG_FILE=test-config.yaml \
MESSAGE_BUS_TYPE=noop \
LOG_LEVEL=DEBUG \
python main.py

# Check results
ls /data/raw_archives/test-archive/
cat /data/raw_archives/metadata/checksums.json
cat /data/raw_archives/metadata/ingestion_log.jsonl
```

## Example: Docker

```bash
# Build image
docker build -t ingestion-service .

# Run with environment variables
docker run \
  -e MESSAGE_BUS_HOST=rabbitmq \
  -e STORAGE_PATH=/data/raw_archives \
  -v raw_archives:/data/raw_archives \
  ingestion-service

# Run with config file
docker run \
  -e CONFIG_FILE=/app/config.yaml \
  -v ./config.yaml:/app/config.yaml:ro \
  -v raw_archives:/data/raw_archives \
  ingestion-service
```

## Verify Installation

```bash
# Test imports
python -c "from app.config import IngestionConfig; print('✓ Config')"
python -c "from app.service import IngestionService; print('✓ Service')"
python -c "from app.event_publisher import create_publisher; print('✓ Publisher')"
python -c "from app.archive_fetcher import create_fetcher; print('✓ Fetcher')"

# Run tests
pytest tests/ -q

# Check structure
ls -la app/
ls -la tests/
```

## Common Tasks

### Run specific test
```bash
pytest tests/test_service.py::TestIngestionService::test_ingest_archive_success -v
```

### Generate coverage report
```bash
pytest tests/ --cov=app --cov-report=html
open htmlcov/index.html
```

### Run with debug logging
```bash
LOG_LEVEL=DEBUG MESSAGE_BUS_TYPE=noop python main.py
```

### Test with custom sources
```bash
# Edit config
vi config.yaml

# Run
CONFIG_FILE=config.yaml MESSAGE_BUS_TYPE=noop python main.py
```

## Troubleshooting

### Import errors
```bash
# Add to PYTHONPATH
export PYTHONPATH=/path/to/ingestion:$PYTHONPATH
python main.py
```

### Missing dependencies
```bash
pip install --upgrade -r requirements.txt
```

### Permission denied
```bash
chmod +x main.py
chmod -R u+rwx app/ tests/
```

### Port already in use
```bash
# Change port or stop existing service
export MESSAGE_BUS_PORT=5673
python main.py
```

## Next Steps

1. ✅ Run tests to verify installation
2. ✅ Configure your archive sources
3. ✅ Run the service
4. ✅ Monitor ingestion logs
5. ✅ Integrate with parsing service

## Documentation

- **README.md**: Service overview and API
- **IMPLEMENTATION.md**: Detailed implementation
- **TESTING.md**: How to run tests
- **config.yaml**: Configuration examples
- **.env.example**: Environment variable reference

## Support

For issues or questions:
1. Check log output: `LOG_LEVEL=DEBUG python main.py`
2. Review IMPLEMENTATION.md for details
3. Run tests: `pytest tests/ -vv`
4. Check configuration: `python -c "from app.config import IngestionConfig; print(IngestionConfig.from_env())"`

---

**Ready to ingest?** 🚀

```bash
python main.py
```

That's it! The service will start ingesting archives and publishing events.
