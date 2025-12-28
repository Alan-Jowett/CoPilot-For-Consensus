<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Copilot Storage Adapter

A shared Python library for document storage across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Document Store Interface**: Common interface for NoSQL document storage backends
- **MongoDB Implementation**: Production-ready MongoDB document store
- **Azure Cosmos DB Implementation**: Production-ready Azure Cosmos DB document store
- **In-Memory Document Store**: Testing document store that works in-memory
- **Factory Pattern**: Simple factory function for creating document stores
- **Schema Validation**: ValidatingDocumentStore wrapper for enforcing schema validation on document operations

## Installation

### For Development (Editable Mode)

From the copilot_storage directory:

```bash
pip install -e .
```

### For Production

```bash
pip install copilot-storage
```

## Usage

### Using Document Stores

```python
from copilot_storage import create_document_store

# Create in-memory store for testing/local dev
store = create_document_store(store_type="inmemory")
store.connect()

# Insert document
doc_id = store.insert_document("users", {
    "name": "Alice",
    "email": "alice@example.com",
    "age": 30
})

# Get document by ID
user = store.get_document("users", doc_id)
print(user["name"])  # Alice

# Query documents
results = store.query_documents("users", {"age": 30})

# Update document
store.update_document("users", doc_id, {"age": 31})

# Delete document
store.delete_document("users", doc_id)

store.disconnect()
```

### Using MongoDB Store

```python
import os
from copilot_storage import create_document_store

# Create MongoDB store using environment variables for credentials
store = create_document_store(
    store_type="mongodb",
    host="mongodb",
    port=27017,
    username=os.getenv("MONGODB_USERNAME"),
    password=os.getenv("MONGODB_PASSWORD"),
    database="copilot_db"
)

# Connect and use
if store.connect():
    doc_id = store.insert_document("archives", {
        "archive_id": "abc-123",
        "status": "completed",
        "timestamp": "2025-01-01T00:00:00Z"
    })
    store.disconnect()
```

### Using Azure Cosmos DB Store

```python
import os
from copilot_storage import create_document_store

# Create Azure Cosmos DB store using environment variables for credentials
store = create_document_store(
    store_type="azurecosmos",
    endpoint=os.getenv("COSMOS_ENDPOINT"),  # e.g., https://myaccount.documents.azure.com:443/
    key=os.getenv("COSMOS_KEY"),
    database="copilot_db",
    container="documents",
    partition_key="/collection"
)

# Connect and use
store.connect()
doc_id = store.insert_document("archives", {
    "archive_id": "abc-123",
    "status": "completed",
    "timestamp": "2025-01-01T00:00:00Z"
})
store.disconnect()
```

### Validating Documents with Schema Validation

**Note:** To use `ValidatingDocumentStore`, you need to install the validation extra: `pip install copilot-storage[validation]`

The `ValidatingDocumentStore` wrapper enforces schema validation on document operations:

```python
from copilot_storage import create_document_store, ValidatingDocumentStore

# Create base store
base_store = create_document_store("inmemory")
base_store.connect()

# Create a simple schema provider
class SchemaProvider:
    def __init__(self):
        self.schemas = {
            "User": {
                "type": "object",
                "properties": {
                    "user_id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                    "age": {"type": "integer", "minimum": 0}
                },
                "required": ["user_id", "name", "email"]
            }
        }

    def get_schema(self, schema_name):
        return self.schemas.get(schema_name)

schema_provider = SchemaProvider()

# Wrap store with validation
validating_store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=schema_provider,
    strict=True,  # Raise error on validation failure
    validate_reads=False  # Don't validate on reads (for performance)
)

# Valid document passes validation
valid_user = {
    "user_id": "user-123",
    "name": "Alice Smith",
    "email": "alice@example.com",
    "age": 30
}
doc_id = validating_store.insert_document("user", valid_user)

# Invalid document raises DocumentValidationError in strict mode
invalid_user = {
    "user_id": "user-456",
    "name": "Bob Jones",
    # Missing required field: email
}

try:
    validating_store.insert_document("user", invalid_user)
except DocumentValidationError as e:
    print(f"Validation failed: {e.errors}")

# Non-strict mode: logs warning but allows insert
permissive_store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=schema_provider,
    strict=False  # Log warning but continue
)
permissive_store.insert_document("user", invalid_user)

# Enable read validation for debugging
debug_store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=schema_provider,
    validate_reads=True  # Validate documents on read
)
user = debug_store.get_document("user", doc_id)  # Validates retrieved document
```

The `ValidatingDocumentStore` automatically converts collection names to schema names using PascalCase:
- `user` → `User`
- `archive_metadata` → `ArchiveMetadata`
- `thread_summaries` → `ThreadSummaries`

See [examples/validating_document_store_example.py](examples/validating_document_store_example.py) for a complete demonstration.

## Document Store Interface

The `DocumentStore` abstract base class defines the contract:

- `connect() -> bool`: Establish connection to the store
- `disconnect() -> None`: Close connection
- `insert_document(collection, doc) -> str`: Insert a document and return its ID
- `get_document(collection, doc_id) -> Optional[Dict]`: Retrieve a document by ID
- `query_documents(collection, filter_dict, limit) -> List[Dict]`: Query documents matching filter
- `update_document(collection, doc_id, patch) -> bool`: Update a document
- `delete_document(collection, doc_id) -> bool`: Delete a document

## Implementations

### MongoDocumentStore

Production MongoDB implementation with:
- Connection pooling via pymongo
- Automatic ObjectId handling
- Error handling and logging
- Support for authentication
- Standard MongoDB query syntax

### AzureCosmosDocumentStore

Production Azure Cosmos DB implementation with:
- Azure Cosmos DB Core (SQL) API
- Automatic partition key management (uses collection name as partition key)
- Throttling and error handling
- Support for account key or managed identity authentication
- SQL query translation for common operations
- Simplified aggregation pipeline support ($match, $limit)

**Configuration via Environment Variables:**
- `COSMOS_ENDPOINT`: Cosmos DB endpoint URL (required)
- `COSMOS_KEY`: Cosmos DB account key (required)
- `COSMOS_DATABASE`: Database name (default: "copilot")
- `COSMOS_CONTAINER`: Container name (default: "documents")
- `COSMOS_PARTITION_KEY`: Partition key path (default: "/collection")

**Deployment Considerations:**
- **Throughput**: Configure appropriate Request Units (RU/s) for your workload
- **Indexing**: Customize indexing policy for query performance
- **Partitioning**: Uses `/collection` as partition key for multi-collection support in a single container
- **Consistency**: Choose consistency level based on requirements (default: Session)
- **Backup**: Enable automatic backups for production environments
- **Security**: Use Azure Managed Identity instead of account keys when possible

See [examples/azure_cosmos_document_store_example.py](examples/azure_cosmos_document_store_example.py) for a complete demonstration.

### InMemoryDocumentStore

Testing implementation with:
- In-memory dict-based storage
- Simple equality-based filtering
- Fast execution for unit tests
- Utility methods for clearing data
- Zero external dependencies

### ValidatingDocumentStore

Schema validation wrapper that:
- Validates documents against JSON schemas on insert and update operations
- Supports both strict (raise error) and non-strict (log warning) modes
- Optional validation on read operations (debug mode)
- Works with FileSchemaProvider for event schema validation
- Composes cleanly with any DocumentStore implementation
- Provides structured DocumentValidationError with detailed error messages
- Automatically maps collection names to schema names (snake_case → PascalCase)

## Development

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run only unit tests (exclude integration tests)
pytest tests/ -v -m "not integration"

# Run integration tests for specific backends
pytest tests/test_integration_mongodb.py -v  # MongoDB integration tests
pytest tests/test_integration_azurecosmos.py -v  # Azure Cosmos DB integration tests
```

### Code Coverage

```bash
pytest tests/ --cov=copilot_storage --cov-report=html
```

### Linting

```bash
pylint copilot_storage/
```

## Requirements

- Python 3.10+
- pymongo (for MongoDB)
- azure-cosmos (for Azure Cosmos DB)
- copilot-schema-validation (optional: for ValidatingDocumentStore - install with `pip install copilot-storage[validation]`)

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
