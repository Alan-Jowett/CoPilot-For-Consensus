<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# copilot-schema-validation

JSON schema validation library for Copilot-for-Consensus events and documents.

This adapter provides schema validation functionality for event messages and document storage in the Copilot-for-Consensus system. It uses JSON Schema validation for both events and documents against schemas loaded from the filesystem.

**Important**: Schema validation for documents is handled entirely at the application layer through the `ValidatingDocumentStore` wrapper. MongoDB-level validators have been removed to avoid duplication and keep validation centralized in the application code.

## Features

- **File-based Schema Provider**: Load schemas from the filesystem
- **JSON Schema Validation**: Full JSON Schema validation with support for schema references
- **Caching**: Built-in schema caching for performance
- **No dependency on other adapters**: Eliminates circular dependencies with other adapters
- **Application-layer validation**: Works with `ValidatingDocumentStore` to provide schema validation before database writes
- **Centralized validation**: Single source of truth for validation logic, avoiding duplication between application and database layers

## Installation

```bash
pip install ./adapters/copilot_schema_validation
```

## Usage

### File-based Schema Provider

```python
from copilot_schema_validation import FileSchemaProvider, validate_json

# Load schemas from filesystem
provider = FileSchemaProvider()

# Get a schema
schema = provider.get_schema("ArchiveIngested")

# Validate a document
document = {
    "event_type": "ArchiveIngested",
    "event_id": "123e4567-e89b-12d3-a456-426614174000",
    "timestamp": "2025-01-01T00:00:00Z",
    "version": "1.0",
    "data": {
        "archive_id": "archive-123"
    }
}

is_valid, errors = validate_json(document, schema)
```

### Document Store Validation

For document storage, use `ValidatingDocumentStore` from `copilot_storage` to wrap any document store with schema validation:

```python
from copilot_storage import create_document_store, ValidatingDocumentStore
from copilot_schema_validation import FileSchemaProvider
from pathlib import Path

# Create base document store
base_store = create_document_store(store_type="mongodb", host="localhost")
base_store.connect()

# Wrap with schema validation
# Point to documents schema directory (relative to service root)
schema_provider = FileSchemaProvider(
    schema_dir=Path(__file__).parent.parent / "docs" / "schemas" / "documents"
)
validating_store = ValidatingDocumentStore(
    store=base_store,
    schema_provider=schema_provider,
    strict=True,  # Raise error on validation failure
)

# Now all document operations are validated
# This will raise DocumentValidationError if document doesn't match schema
doc_id = validating_store.insert_document("messages", {
    "message_id": "msg123",
    "content": "Hello world",
    # ... other required fields
})
```

**Note**: Schema validation for documents happens entirely at the application layer (via `ValidatingDocumentStore`). MongoDB collections do NOT have validators to avoid duplication and ensure validation logic is centralized in the application code.

## Testing

Run tests with pytest:

```bash
cd adapters/copilot_schema_validation
pytest tests/ -v
```

For unit tests only:

```bash
pytest tests/ -v -m "not integration"
```

## Development

Install in development mode:

```bash
pip install -e ./adapters/copilot_schema_validation[dev]
```

Run linting and type checking:

```bash
pylint copilot_schema_validation/
mypy copilot_schema_validation/
```

## History of Changes

- **Removed DocumentStoreSchemaProvider**: The `DocumentStoreSchemaProvider` class and its MongoDB integration have been removed to eliminate the circular dependency between `copilot_schema_validation` and `copilot_storage`. All applications now use `FileSchemaProvider` to load schemas from the filesystem.
- **Removed MongoDB-level validators**: MongoDB collection validators have been removed to centralize validation at the application layer. All document validation is now handled through `ValidatingDocumentStore` wrapper, which uses this adapter for schema validation. This avoids duplication between database-level and application-level validation logic, simplifies MongoDB setup, and keeps schema evolution managed in the application layer where schemas already live.
