# Copilot Archive Store Adapter

A shared archive storage library for the Copilot-for-Consensus microservices ecosystem.

## Overview

The `copilot-archive-store` adapter provides an abstraction layer for storing and retrieving mailbox archives, enabling deployment-time selection of the storage backend without code changes.

### Supported Backends

- **Local Volume** (Default): Filesystem-based storage for single-node deployments
- **MongoDB GridFS** (Planned): Database-backed storage for multi-node clusters
- **Azure Blob Storage** (Future): Cloud storage for Azure deployments
- **AWS S3** (Future): Cloud storage for AWS deployments

## Installation

### Basic Installation

```bash
pip install -e /app/adapters/copilot_archive_store
```

### With MongoDB Support

```bash
pip install -e "/app/adapters/copilot_archive_store[mongodb]"
```

### Development Installation

```bash
pip install -e "/app/adapters/copilot_archive_store[dev]"
```

## Usage

### Local Volume Storage (Default)

```python
from copilot_archive_store import create_archive_store

# Create store with default settings
store = create_archive_store()

# Or specify configuration
store = create_archive_store("local", base_path="/data/raw_archives")

# Store an archive
archive_id = store.store_archive(
    source_name="ietf-wg-example",
    file_path="/path/to/archive.mbox",
    content=archive_bytes
)

# Retrieve an archive
content = store.get_archive(archive_id)

# List archives for a source
archives = store.list_archives("ietf-wg-example")
```

### MongoDB GridFS Storage (Planned)

```python
from copilot_archive_store import create_archive_store

# Create MongoDB-backed store
store = create_archive_store(
    "mongodb",
    host="documentdb",
    port=27017,
    database="copilot_archives",
    username="user",
    password="pass"
)

# Use the same API as local storage
archive_id = store.store_archive(...)
```

### Environment-Based Configuration

```python
import os

# Set environment variable
os.environ["ARCHIVE_STORE_TYPE"] = "local"
os.environ["ARCHIVE_STORE_PATH"] = "/data/raw_archives"

# Auto-detect from environment
store = create_archive_store()
```

## Configuration

### Local Volume Backend

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ARCHIVE_STORE_TYPE` | `local` | Storage backend type |
| `ARCHIVE_STORE_PATH` | `/data/raw_archives` | Base directory for archives |

### MongoDB Backend (Planned)

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ARCHIVE_STORE_TYPE` | - | Set to `mongodb` |
| `MONGODB_HOST` | `localhost` | MongoDB host |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `ARCHIVE_STORE_DB` | `copilot_archives` | Database name |
| `MONGODB_USER` | - | MongoDB username |
| `MONGODB_PASSWORD` | - | MongoDB password |

## Architecture

### Interface Design

The `ArchiveStore` abstract base class defines the following methods:

- `store_archive(source_name, file_path, content)` → `archive_id`
- `get_archive(archive_id)` → `bytes | None`
- `get_archive_by_hash(content_hash)` → `archive_id | None`
- `archive_exists(archive_id)` → `bool`
- `delete_archive(archive_id)` → `bool`
- `list_archives(source_name)` → `List[Dict]`

### Content-Addressable Storage

Archives are identified by a deterministic ID derived from their content hash (SHA256), enabling:

- **Deduplication**: Same content = same ID
- **Integrity**: Content hash verification
- **Idempotency**: Re-uploading same file is a no-op

### Backward Compatibility

The `LocalVolumeArchiveStore` maintains the existing directory structure:

```
/data/raw_archives/
├── metadata/
│   └── archives.json         # Metadata index
├── ietf-wg-example/
│   ├── archive1.mbox
│   └── archive2.mbox
└── ietf-wg-another/
    └── archive3.mbox
```

## Testing

```bash
# Run unit tests
cd /app/adapters/copilot_archive_store
pytest tests/

# Run with coverage
pytest --cov=copilot_archive_store tests/

# Run integration tests (requires MongoDB)
pytest tests/test_integration_mongodb.py
```

## Development

### Project Structure

```
copilot_archive_store/
├── copilot_archive_store/
│   ├── __init__.py
│   ├── archive_store.py              # ABC interface + factory
│   ├── local_volume_archive_store.py # Local filesystem implementation
│   └── mongodb_archive_store.py      # MongoDB GridFS implementation (planned)
├── tests/
│   ├── __init__.py
│   ├── test_archive_store.py
│   ├── test_local_volume_archive_store.py
│   └── test_integration_mongodb.py
├── setup.py
└── README.md
```

### Adding a New Backend

1. Create new implementation file (e.g., `s3_archive_store.py`)
2. Implement the `ArchiveStore` interface
3. Register in `create_archive_store()` factory
4. Add dependencies to `setup.py` extras
5. Write tests

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the repository root.
