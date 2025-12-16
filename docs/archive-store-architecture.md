<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# ArchiveStore Adapter Pattern - Architecture & Integration Guide

## Overview

The ArchiveStore adapter pattern provides an abstraction layer for archive storage, enabling deployment-time selection of storage backends without code changes. This document explains the architecture, integration points, and deployment strategies.

## Current Architecture (Before Adapter)

### Ingestion Flow
```
┌─────────────────┐
│  Fetcher        │ Fetches from source (IMAP, rsync, etc.)
│  (rsync, IMAP)  │ Writes to: /data/raw_archives/{source}/file.mbox
└────────┬────────┘
         │ file_paths
         ▼
┌─────────────────┐
│  Ingestion      │ Publishes ArchiveIngestedEvent with:
│  Service        │   - archive_id (hash-based)
└────────┬────────┘   - file_path (/data/raw_archives/{source}/file.mbox)
         │
         │ ArchiveIngestedEvent
         ▼
┌─────────────────┐
│  Message Bus    │
│  (RabbitMQ)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Parsing        │ Reads file from file_path directly
│  Service        │ Parses mbox → JSON messages
└─────────────────┘
```

### Storage
- **Volume Mount**: Shared Docker volume `raw_archives` 
- **Ingestion**: Mounts as `/data/raw_archives` (read-write)
- **Parsing**: Mounts as `/data/raw_archives:ro` (read-only)
- **Limitation**: Requires shared filesystem, not suitable for multi-node clusters

## New Architecture (With Adapter)

### ArchiveStore Interface
```python
class ArchiveStore(ABC):
    """Abstract interface for archive storage backends."""
    
    def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive and return archive_id."""
        
    def get_archive(self, archive_id: str) -> Optional[bytes]:
        """Retrieve archive content by ID."""
        
    def get_archive_by_hash(self, content_hash: str) -> Optional[str]:
        """Retrieve archive ID by content hash (deduplication)."""
        
    def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists."""
        
    def delete_archive(self, archive_id: str) -> bool:
        """Delete archive."""
        
    def list_archives(self, source_name: str) -> List[Dict[str, Any]]:
        """List all archives for a source."""
```

### Backends

#### 1. LocalVolumeArchiveStore (Default)
- **Purpose**: Backward compatibility, single-node deployments
- **Storage**: Local filesystem at `/data/raw_archives/{source}/{file}`
- **Metadata**: JSON index at `/data/raw_archives/metadata/archives.json`
- **Use Case**: Development, testing, single-node production

**Structure**:
```
/data/raw_archives/
├── metadata/
│   └── archives.json          # Archive metadata index
├── ietf-quic/
│   ├── archive1.mbox
│   └── archive2.mbox
└── ietf-tls/
    └── archive3.mbox
```

**Metadata Format**:
```json
{
  "a1b2c3d4e5f6g7h8": {
    "archive_id": "a1b2c3d4e5f6g7h8",
    "source_name": "ietf-quic",
    "file_path": "/data/raw_archives/ietf-quic/archive1.mbox",
    "original_path": "archive1.mbox",
    "content_hash": "a1b2c3d4e5f6g7h8...",
    "size_bytes": 1024000,
    "stored_at": "2025-01-15T10:30:00Z"
  }
}
```

#### 2. MongoDBArchiveStore (Planned)
- **Purpose**: Multi-node clusters, stateless services
- **Storage**: MongoDB GridFS (files > 16MB) or collection (smaller files)
- **Use Case**: Kubernetes, Docker Swarm, cloud deployments
- **Benefits**: 
  - No shared volume required
  - Built-in replication
  - Content-addressable storage
  - Automatic deduplication

#### 3. Cloud Backends (Future)
- **AzureBlobArchiveStore**: Azure Blob Storage
- **S3ArchiveStore**: AWS S3
- **Use Case**: Cloud-native deployments, cost optimization

## Integration Strategy

### Phase 1: Foundation ✅ COMPLETE
- Created `copilot_archive_store` adapter module
- Implemented `ArchiveStore` ABC interface
- Implemented `LocalVolumeArchiveStore`
- Comprehensive test suite (23 tests passing)
- Factory pattern with environment-based configuration

### Phase 2: Service Integration (Current)

#### Option A: Minimal Integration (Recommended for v1)
**Keep current flow, add optional archive store support**

Pros:
- Zero breaking changes
- Incremental adoption
- Easy rollback

Implementation:
1. Parsing service optionally uses archive store for reading
2. Falls back to direct file access if archive store unavailable
3. Ingestion continues writing files directly (backward compatible)

#### Option B: Full Integration
**Refactor both services to use archive store exclusively**

Pros:
- Cleaner architecture
- Better abstraction

Cons:
- Requires careful migration
- More testing needed
- Potential downtime

**Recommendation**: Start with Option A, migrate to Option B in v2

### Phase 3: MongoDB Implementation
Once LocalVolumeArchiveStore is integrated and tested:
1. Implement MongoDBArchiveStore with GridFS
2. Add configuration support
3. Multi-node testing
4. Performance benchmarking
5. Migration tooling

### Phase 4: Deployment & Documentation
- Docker Compose configurations for all backends
- Kubernetes deployment guides
- Performance tuning guides
- Migration procedures

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ARCHIVE_STORE_TYPE` | `local` | Backend type: `local`, `mongodb`, `azure_blob`, `s3` |
| `ARCHIVE_STORE_PATH` | `/data/raw_archives` | Base path for local storage |
| `MONGODB_HOST` | `documentdb` | MongoDB host (for mongodb backend) |
| `MONGODB_PORT` | `27017` | MongoDB port |
| `ARCHIVE_STORE_DB` | `copilot_archives` | MongoDB database name |

### Docker Compose Examples

#### Local Volume (Current, Default)
```yaml
services:
  ingestion:
    environment:
      - ARCHIVE_STORE_TYPE=local
      - ARCHIVE_STORE_PATH=/data/raw_archives
    volumes:
      - raw_archives:/data/raw_archives
  
  parsing:
    environment:
      - ARCHIVE_STORE_TYPE=local
      - ARCHIVE_STORE_PATH=/data/raw_archives
    volumes:
      - raw_archives:/data/raw_archives:ro
```

#### MongoDB Backend (Future)
```yaml
services:
  ingestion:
    environment:
      - ARCHIVE_STORE_TYPE=mongodb
      - MONGODB_HOST=documentdb
      - MONGODB_PORT=27017
      - ARCHIVE_STORE_DB=copilot_archives
    # No volume mount needed!
  
  parsing:
    environment:
      - ARCHIVE_STORE_TYPE=mongodb
      - MONGODB_HOST=documentdb
      - MONGODB_PORT=27017
      - ARCHIVE_STORE_DB=copilot_archives
    # No volume mount needed!
```

## Benefits

### Scalability
- **Multi-node clusters**: No shared filesystem required with MongoDB/cloud backends
- **Horizontal scaling**: Stateless services can scale independently
- **Load distribution**: Archive storage distributed across cluster

### Flexibility
- **Deployment-time selection**: Change backend via configuration
- **Multi-backend support**: Different backends for different environments
- **Easy migration**: Switch backends without code changes

### Operational
- **Deduplication**: Content-addressable storage prevents duplicate archives
- **Integrity**: SHA256 content hashing ensures data integrity
- **Observability**: Adapter pattern enables per-backend metrics and logging
- **Testing**: Mock storage backends for unit/integration tests

### Cost
- **Cloud optimization**: Use appropriate storage tier (S3 Glacier, Azure Cool, etc.)
- **Resource efficiency**: Deduplication reduces storage costs
- **Pay-per-use**: Cloud backends offer flexible pricing

## Migration Path

### From Local Volume to MongoDB

1. **Preparation**
   - Deploy MongoDB instance
   - Configure connection parameters
   - Test connectivity

2. **Data Migration**
   - Option A: Run both backends in parallel during transition
   - Option B: Batch upload existing archives to MongoDB
   - Option C: Lazy migration (upload on access)

3. **Cutover**
   - Update docker-compose environment variables
   - Restart services
   - Monitor logs and metrics

4. **Cleanup**
   - Verify all archives accessible
   - Remove local volume mount (optional)

## Testing Strategy

### Unit Tests
- ✅ Interface contract tests (10 tests)
- ✅ LocalVolumeArchiveStore implementation tests (13 tests)
- ✅ ArchiveAccessor helper tests (12 tests)
- ✅ **Total: 35 tests, all passing**
- ⏳ MongoDBArchiveStore implementation tests (planned)

### Integration Tests
- ⏳ Ingestion → Parsing flow with LocalVolumeArchiveStore
- ⏳ Ingestion → Parsing flow with MongoDBArchiveStore
- ⏳ Multi-service coordination tests

### Performance Tests
- ⏳ Throughput benchmarks (archives/second)
- ⏳ Latency measurements (read/write)
- ⏳ Scalability tests (multi-node)

## Future Enhancements

### Archive Lifecycle Management
- Automatic cleanup of old archives
- Tiered storage (hot/warm/cold)
- Archive expiration policies

### Advanced Features
- Archive compression (gzip, zstd)
- Encryption at rest
- Access control and audit logging
- Archive versioning

### Cloud Integrations
- AWS S3 with lifecycle policies
- Azure Blob with archival tiers
- Google Cloud Storage support
- MinIO compatibility

## References

- [ArchiveStore Interface Documentation](../adapters/copilot_archive_store/README.md)
- [Issue #XX - ArchiveStore Adapter Pattern](https://github.com/Alan-Jowett/CoPilot-For-Consensus/issues/XX)
- [Docker Volume Documentation](https://docs.docker.com/storage/volumes/)
- [MongoDB GridFS Documentation](https://www.mongodb.com/docs/manual/core/gridfs/)
