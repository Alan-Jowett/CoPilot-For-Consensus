<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Data Storage and Archive Management

Architecture of the archive storage abstraction layer enabling deployment-time backend selection.

## Archive Storage Pattern

### Problem

Original flow requires shared filesystem:
```
Ingestion (writes) → Shared volume → Parsing (reads)
```

Limitation: Not suitable for multi-node clusters without network-attached storage.

### Solution: ArchiveStore Adapter

Interface-based abstraction supporting multiple backends:

```python
class ArchiveStore(ABC):
    def store(self, path: str, content: bytes) -> str:
        """Store archive, return storage_id"""
    
    def retrieve(self, storage_id: str) -> bytes:
        """Retrieve archive by storage_id"""
    
    def delete(self, storage_id: str) -> None:
        """Delete archive"""
```

### Supported Backends

| Backend | Environment | Use Case | Scaling |
|---------|-------------|----------|---------|
| **Local Volume** | `ARCHIVE_STORE_BACKEND=local` | Development | Single-machine |
| **Azure Blob** | `ARCHIVE_STORE_BACKEND=azure` | Production Azure | Cloud-managed |
| **S3** | `ARCHIVE_STORE_BACKEND=s3` | Production AWS | Cloud-managed |
| **NFS** | `ARCHIVE_STORE_BACKEND=nfs` | On-premises | Network attached |

### Event Flow with Adapter

```
Ingestion → store() → storage_id
              ↓
ArchiveIngestedEvent (includes storage_id)
              ↓
Parsing → retrieve(storage_id) → archive content
```

**Benefits**:
- Services unaware of backend (factory pattern)
- Backend swap without code changes
- Multi-node and cloud-native friendly

## Configuration

**.env example** (Azure Blob):
```
ARCHIVE_STORE_BACKEND=azure
AZURE_STORAGE_ACCOUNT_NAME=myaccount
AZURE_STORAGE_ACCOUNT_KEY=<key>
AZURE_STORAGE_CONTAINER=archives
```

For detailed implementation, see [adapters/copilot_archive_store/README.md](../../adapters/copilot_archive_store/README.md).
