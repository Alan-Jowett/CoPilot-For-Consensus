<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Cosmos DB Per-Collection Container Routing

## Overview

Each collection type (messages, chunks, reports, etc.) is stored in its own Cosmos DB container, enabling independent management of source and derived artifacts.

Note: this document covers Cosmos DB *document store* containers. The system also uses a *vector store* (Qdrant by default) where the vector collection is commonly named `embeddings`.

## Container Mapping

Collections map to containers as follows:

| Collection | Container Name | Partition Key | Type |
|------------|---------------|---------------|------|
| messages   | messages      | /id          | Source |
| archives   | archives      | /id          | Source |
| chunks     | chunks        | /id          | Derived |
| reports    | reports       | /id          | Derived |
| summaries  | summaries     | /id          | Derived |
| threads    | threads       | /id          | Derived |
| *unknown*  | {collection}  | /id          | Dynamic |

Vector store note (not Cosmos DB):

| Vector Store (Qdrant) Collection | Purpose |
|----------------------------------|---------|
| embeddings                        | Stores embedding vectors and metadata |

## Configuration

```python
from copilot_config.generated.adapters.document_store import (
    DriverConfig_DocumentStore_AzureCosmosdb
)
from copilot_storage.azure_cosmos_document_store import AzureCosmosDocumentStore

config = DriverConfig_DocumentStore_AzureCosmosdb(
    endpoint="https://myaccount.documents.azure.com:443/",
    key="your-key",  # or omit for managed identity
)

store = AzureCosmosDocumentStore.from_config(config)
```

## Benefits

1. **Clean Experimentation**
   ```bash
   # Delete all chunks without affecting messages
   az cosmosdb sql container delete \
     --account-name <account-name> \
     --database-name copilot \
     --name chunks \
     --resource-group <resource-group>
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
Containers are created on-demand when first accessed, then cached for subsequent operations.

### Query Behavior
Queries run cross-partition within the collection's container (no collection field filtering needed).

### Partition Key
All containers use `/id` (document ID) as the partition key.

## Testing

```bash
cd adapters/copilot_storage
pytest tests/test_azure_cosmos_container_routing.py -v
pytest tests/test_azure_cosmos_document_store.py -v
```

## References

- Schema: `docs/schemas/configs/adapters/drivers/document_store/azure_cosmosdb.json`
- Implementation: `adapters/copilot_storage/copilot_storage/azure_cosmos_document_store.py`
- Tests: `adapters/copilot_storage/tests/test_azure_cosmos_container_routing.py`
