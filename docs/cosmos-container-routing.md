# Cosmos DB Container Routing Feature

## Overview

This feature adds support for routing different collection types to separate Cosmos DB containers, enabling better management of source and derived artifacts.

## Motivation

Previously, all collections (messages, archives, chunks, reports, summaries) were stored in a single Cosmos container named "documents" with partition key `/collection`. This created challenges for:

1. **Experimentation**: Couldn't delete derived artifacts (chunks/reports) without deleting source data
2. **Observability**: Azure Monitor metrics were container-wide, not per-artifact-type
3. **Policy Management**: All artifacts shared the same retention/TTL/throughput settings

## Solution

Added `container_routing_mode` configuration with two modes:

### Legacy Mode (Default)
- **Behavior**: All collections go to single "documents" container
- **Partition Key**: `/collection`
- **Use Case**: Existing deployments, backward compatibility

### Per-Type Mode
- **Behavior**: Each collection type routes to its own container
- **Partition Key**: `/id` (document ID)
- **Use Case**: New deployments, flexible management

## Configuration

### Environment Variable
```bash
export COSMOS_CONTAINER_ROUTING_MODE=per_type
```

### Code Configuration
```python
from copilot_config.generated.adapters.document_store import (
    DriverConfig_DocumentStore_AzureCosmosdb
)

config = DriverConfig_DocumentStore_AzureCosmosdb(
    endpoint="https://myaccount.documents.azure.com:443/",
    key="your-key",
    container_routing_mode="per_type"  # or "legacy" (default)
)

store = AzureCosmosDocumentStore.from_config(config)
```

## Container Mapping

In per-type mode, collections map to containers as follows:

| Collection | Container Name | Partition Key | Type |
|------------|---------------|---------------|------|
| messages   | messages      | /id          | Source |
| archives   | archives      | /id          | Source |
| chunks     | chunks        | /id          | Derived |
| reports    | reports       | /id          | Derived |
| summaries  | summaries     | /id          | Derived |
| embeddings | embeddings    | /id          | Derived |
| threads    | threads       | /id          | Derived |
| *unknown*  | {collection}  | /id          | Dynamic |

## Benefits

1. **Clean Experimentation**
   ```bash
   # Delete all chunks without affecting messages
   az cosmosdb mongodb collection delete --name chunks ...
   ```

2. **Per-Container Metrics**
   - Azure Monitor exposes metrics per container
   - Query `microsoft.documentdb/databaseaccounts` with container dimension

3. **Flexible Policies**
   - Set different TTL per container
   - Allocate more RU/s to frequently-accessed containers
   - Apply retention policies independently

## Implementation Details

### Container Creation
- **Legacy mode**: Container created during `connect()`
- **Per-type mode**: Containers created on first access, cached thereafter

### Query Behavior
- **Legacy mode**: Queries filtered by `c.collection = @collection`, partition-scoped
- **Per-type mode**: Queries run cross-partition within container

### Backward Compatibility
- Default mode is "legacy"
- Existing deployments continue working unchanged
- Tests confirm no regressions (155/159 tests passing)

## Testing

Run the test suite:
```bash
cd adapters/copilot_storage
pytest tests/test_azure_cosmos_container_routing.py -v  # New tests (21)
pytest tests/test_azure_cosmos_document_store.py -v     # Existing tests (62)
```

## Migration Path

1. **Phase 1 (This PR)**: Implement routing mode, keep legacy as default
2. **Phase 2 (Future)**: Optional read-fallback/dual-write during migration
3. **Phase 3 (Future)**: Backfill existing data into per-type containers
4. **Phase 4 (Future)**: Cutover reads, deprecate legacy mode

## Known Limitations

- Per-type mode uses cross-partition queries (higher RU cost)
- Migration from legacy to per-type requires data backfill
- More containers increases IaC/ops surface area

## References

- Schema: `docs/schemas/configs/adapters/drivers/document_store/azure_cosmosdb.json`
- Implementation: `adapters/copilot_storage/copilot_storage/azure_cosmos_document_store.py`
- Tests: `adapters/copilot_storage/tests/test_azure_cosmos_container_routing.py`
