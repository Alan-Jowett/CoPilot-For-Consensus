# Copilot Storage SDK

A shared Python library for document storage across microservices in the Copilot-for-Consensus system.

## Features

- **Abstract Document Store Interface**: Common interface for NoSQL document storage backends
- **MongoDB Implementation**: Production-ready MongoDB document store
- **In-Memory Document Store**: Testing document store that works in-memory
- **Factory Pattern**: Simple factory function for creating document stores

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
        "status": "processed",
        "timestamp": "2025-01-01T00:00:00Z"
    })
    store.disconnect()
```

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

### InMemoryDocumentStore

Testing implementation with:
- In-memory dict-based storage
- Simple equality-based filtering
- Fast execution for unit tests
- Utility methods for clearing data
- Zero external dependencies

## Development

### Running Tests

```bash
pytest tests/ -v
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

- Python 3.11+
- pymongo (for MongoDB)

## License

MIT License - see LICENSE file for details.

## Contributing

See CONTRIBUTING.md in the main repository for contribution guidelines.
