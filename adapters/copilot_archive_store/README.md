<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Archive Store Adapter

A shared archive storage library for the Copilot-for-Consensus microservices ecosystem.

## Overview

The `copilot-archive-store` adapter provides an abstraction layer for storing and retrieving mailbox archives, enabling deployment-time selection of the storage backend without code changes.

### Supported Backends

- **Local Volume** (Default): Filesystem-based storage for single-node deployments
- **Azure Blob Storage**: Cloud storage for Azure deployments with scalability and high availability
- **MongoDB GridFS** (Planned): Database-backed storage for multi-node clusters
- **AWS S3** (Future): Cloud storage for AWS deployments

## Installation

### Basic Installation

```bash
pip install -e /app/adapters/copilot_archive_store
```

### With Azure Blob Storage Support

```bash
pip install -e "/app/adapters/copilot_archive_store[azure]"
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

### Azure Blob Storage

```python
from copilot_archive_store import create_archive_store

# Create Azure Blob Storage-backed store
store = create_archive_store(
    "azure_blob",
    account_name="mystorageaccount",
    account_key="base64encodedkey==",
    container_name="archives",
    prefix="my-deployment"  # optional
)

# Or use SAS token instead of account key
store = create_archive_store(
    "azure_blob",
    account_name="mystorageaccount",
    sas_token="?sv=2022-11-02&ss=b&srt=sco...",
    container_name="archives"
)

# Or use connection string
store = create_archive_store(
    "azure_blob",
    connection_string="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;"
)

# Use the same API as local storage
archive_id = store.store_archive(
    source_name="ietf-wg-example",
    file_path="archive.mbox",
    content=archive_bytes
)
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

### Azure Blob Storage Backend

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ARCHIVE_STORE_TYPE` | - | Set to `azure_blob` |
| `AZURE_STORAGE_ACCOUNT` | - | Azure storage account name (required) |
| `AZURE_STORAGE_KEY` | - | Storage account access key (required if not using SAS token) |
| `AZURE_STORAGE_SAS_TOKEN` | - | SAS token (alternative to account key) |
| `AZURE_STORAGE_CONNECTION_STRING` | - | Full connection string (alternative to account/key) |
| `AZURE_STORAGE_CONTAINER` | `archives` | Container name for archives |
| `AZURE_STORAGE_PREFIX` | `` | Optional path prefix for organizing blobs |

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

## Azure Blob Storage Backend

### Features

- **Cloud-native scalability**: Leverage Azure's globally distributed storage
- **High availability**: Built-in redundancy and durability
- **Content-addressable storage**: Automatic deduplication using SHA256 hashes
- **Flexible authentication**: Support for account keys, SAS tokens, or connection strings
- **Organized storage**: Optional prefix support for multi-tenant deployments
- **Metadata indexing**: Efficient listing and lookup operations

### Configuration Examples

#### Using Environment Variables

```bash
export ARCHIVE_STORE_TYPE=azure_blob
export AZURE_STORAGE_ACCOUNT=mystorageaccount
export AZURE_STORAGE_KEY=base64encodedkey==
export AZURE_STORAGE_CONTAINER=copilot-archives
export AZURE_STORAGE_PREFIX=production/
```

```python
from copilot_archive_store import create_archive_store

# Auto-configure from environment
store = create_archive_store()
```

#### Using SAS Token (Recommended for Limited Access)

```python
from copilot_archive_store import create_archive_store

store = create_archive_store(
    "azure_blob",
    account_name="mystorageaccount",
    sas_token="?sv=2022-11-02&ss=b&srt=sco&sp=rwdlac&se=2025-12-31T23:59:59Z&st=2024-01-01T00:00:00Z&spr=https&sig=...",
    container_name="archives"
)
```

#### Using Connection String

```python
store = create_archive_store(
    "azure_blob",
    connection_string="DefaultEndpointsProtocol=https;AccountName=mystorageaccount;AccountKey=key==;EndpointSuffix=core.windows.net"
)
```

### Storage Organization

Archives are stored with the following blob structure:

```
container-name/
├── [prefix/]metadata/
│   └── archives_index.json       # Metadata index for fast lookups
└── [prefix/]source-name/
    ├── archive1.mbox              # Actual archive files
    └── archive2.mbox
```

### Best Practices

1. **Use SAS tokens** for production deployments to limit access scope
2. **Set a prefix** for multi-tenant or multi-environment deployments
3. **Enable Azure Storage logging** for audit trails
4. **Use lifecycle management** policies to archive or delete old blobs
5. **Consider managed identities** for Azure-hosted deployments (future enhancement)

### Future Enhancements

- Managed identity support via `azure.identity`
- Azure Storage lifecycle management integration
- Blob versioning support
- Azure Key Vault integration for credentials

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the repository root.
