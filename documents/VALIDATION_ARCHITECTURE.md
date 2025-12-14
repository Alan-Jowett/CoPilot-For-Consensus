<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Validation Architecture

This document describes how data validation is handled in the Copilot-for-Consensus system.

## Overview

All data validation in the system happens at the **application layer** through adapter components. There is **no database-level validation** to ensure validation logic remains centralized, consistent, and easy to evolve.

## Validation Layers

### 1. Event Validation

Event messages flowing through the message bus are validated using `ValidatingEventPublisher` and `ValidatingEventSubscriber`:

```python
from copilot_events import create_publisher, ValidatingEventPublisher
from copilot_schema_validation import FileSchemaProvider
from pathlib import Path

# Create base publisher
base_publisher = create_publisher(message_bus_type="rabbitmq", host="localhost")

# Wrap with validation
# Default schema_dir points to events schemas, or specify explicitly
schema_provider = FileSchemaProvider()  # Defaults to documents/schemas/events
publisher = ValidatingEventPublisher(
    publisher=base_publisher,
    schema_provider=schema_provider,
    strict=True,
)

# Published events are validated against their schemas
publisher.publish(event)  # Raises ValidationError if invalid
```

**Location**: `adapters/copilot_events/`

### 2. Document Validation

Documents stored in MongoDB are validated using `ValidatingDocumentStore`:

```python
from copilot_storage import create_document_store, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider
from pathlib import Path

# Create base document store
base_store = create_document_store(store_type="mongodb", host="localhost")
base_store.connect()

# Wrap with validation
# Point to documents schema directory
document_schema_provider = FileSchemaProvider(
    schema_dir=Path(__file__).parent.parent / "documents" / "schemas" / "documents"
)
document_store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=document_schema_provider,
    strict=True,
)

# Document operations are validated
document_store.insert_document("messages", message_doc)  # Raises DocumentValidationError if invalid
```

**Location**: `adapters/copilot_storage/validating_document_store.py`

### 3. Schema Provider

Both event and document validation use `FileSchemaProvider` to load JSON schemas from the filesystem:

```python
from copilot_schema_validation import FileSchemaProvider
from pathlib import Path

# For event schemas (default)
event_provider = FileSchemaProvider()  # Defaults to documents/schemas/events
schema = event_provider.get_schema("ArchiveIngested")

# For document schemas (specify directory)
doc_provider = FileSchemaProvider(
    schema_dir=Path(__file__).parent.parent / "documents" / "schemas" / "documents"
)
schema = doc_provider.get_schema("Messages")  # Collection name converted to PascalCase
```

**Location**: `adapters/copilot_schema_validation/`

## Design Rationale

### Why Application-Layer Validation Only?

1. **Single Source of Truth**: All validation logic lives in the application layer, making it easier to maintain and evolve schemas.

2. **Avoids Duplication**: Previously, we had both MongoDB validators and application-layer validation. This led to:
   - Duplicated validation logic
   - Risk of drift between database and application schemas
   - Complex synchronization requirements

3. **Simpler Database Setup**: MongoDB collections are created without validators, simplifying:
   - Database initialization scripts
   - Migrations and schema evolution
   - Testing and local development

4. **Better Error Messages**: Application-layer validation can provide more context-rich error messages to help with debugging.

5. **Technology Independence**: Validation logic is not tied to MongoDB specifics, making it easier to:
   - Switch database backends if needed
   - Test with in-memory stores
   - Maintain consistent validation across different storage types

### What About Performance?

Application-layer validation has minimal performance impact:

- Schemas are cached after first load
- Validation is performed once before database operations
- MongoDB's indexing still provides performance optimization for queries
- The validation overhead is negligible compared to network I/O

### What About Data Integrity?

While we don't have database-level validation, data integrity is maintained through:

1. **Strict Application Validation**: All write paths go through `ValidatingDocumentStore` with `strict=True`
2. **Unique Indexes**: MongoDB indexes enforce uniqueness constraints (e.g., `message_id`, `archive_id`)
3. **Type Safety**: TypeScript/Python type hints in application code
4. **Integration Tests**: Comprehensive tests verify validation logic works correctly

## Service Integration

All services that write to MongoDB use `ValidatingDocumentStore`:

- **Parsing Service**: Validates messages and threads before storage
- **Chunking Service**: Validates chunks before storage
- **Embedding Service**: Validates embeddings metadata
- **Summarization Service**: Validates summaries
- **Orchestrator Service**: Validates orchestration metadata
- **Reporting Service**: Validates reports

Example from parsing service:

```python
# parsing/main.py
from copilot_storage import create_document_store, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider

# Create and connect base store
base_document_store = create_document_store(
    store_type=config.doc_store_type,
    host=config.doc_store_host,
    port=config.doc_store_port,
    database=config.doc_store_name,
)
base_document_store.connect()

# Wrap with schema validation
document_schema_provider = FileSchemaProvider(
    schema_dir=Path(__file__).parent.parent / "documents" / "schemas" / "documents"
)
document_store = ValidatingDocumentStore(
    store=base_document_store,
    schema_provider=document_schema_provider,
    strict=True,
)
```

## MongoDB Collections

MongoDB collections are initialized with:

- **Collections**: Created without validators
- **Indexes**: Created for performance and uniqueness constraints
- **No Validators**: Validation is handled at application layer

See `infra/init/mongo-init.js` for collection and index initialization.

## Testing

### Unit Tests

- `adapters/copilot_storage/tests/test_validating_document_store.py`: Tests validation logic with mock schemas
- `adapters/copilot_schema_validation/tests/`: Tests schema loading and validation

### Integration Tests

- `adapters/copilot_storage/tests/test_integration_mongodb.py`: Verifies MongoDB collections have no validators and accepts any document structure when using raw store

Example test:

```python
def test_mongodb_has_no_collection_validators(mongodb_store, clean_collection):
    """Verify that MongoDB collections do not have validators."""
    # Insert test document to create collection
    mongodb_store.insert_document(clean_collection, {"test": "data"})
    
    # Get collection info
    collection_infos = list(mongodb_store.database.list_collections(
        filter={"name": clean_collection}
    ))
    
    # Verify no validator is present
    if collection_infos:
        collection_info = collection_infos[0]
        assert "options" not in collection_info or "validator" not in collection_info.get("options", {}), \
            "MongoDB collection should NOT have a validator"
```

## Schema Evolution

When schemas need to change:

1. **Update JSON Schema**: Modify schema files in `documents/schemas/events/` or `documents/schemas/documents/`
2. **Update Application Code**: Ensure services handle new/changed fields
3. **Deploy**: No database migrations needed - validation happens at application layer
4. **Backward Compatibility**: Consider using optional fields and default values for gradual rollouts

## Error Handling

When validation fails:

```python
from copilot_storage import DocumentValidationError

try:
    document_store.insert_document("messages", invalid_message)
except DocumentValidationError as e:
    logger.error(
        "Document validation failed",
        collection=e.collection,
        errors=e.errors,
    )
    # Handle error appropriately
```

Validation errors include:
- Collection name where validation failed
- List of specific validation error messages
- Full context for debugging

## Migration from MongoDB Validators

If you're reviewing historical commits, note that:

1. **Before**: MongoDB collections had `$jsonSchema` validators that duplicated application validation logic
2. **After**: MongoDB collections have no validators; all validation happens via `ValidatingDocumentStore`
3. **Migration**: Simply removed validator creation from `infra/init/mongo-init.js` and ensured all services use `ValidatingDocumentStore`

No data migration was needed since we're removing constraints, not adding them.

## References

- [JSON Schema Specification](https://json-schema.org/)
- [MongoDB Schema Validation](https://www.mongodb.com/docs/manual/core/schema-validation/) - Not used in this project
- `adapters/copilot_schema_validation/README.md` - Schema validation adapter documentation
- `adapters/copilot_storage/README.md` - Document store adapter documentation
