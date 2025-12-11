<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# copilot-schema-validation

JSON schema validation library for Copilot-for-Consensus events.

This adapter provides schema validation functionality for event messages in the Copilot-for-Consensus system. It supports multiple schema providers (filesystem, document store) and uses JSON Schema validation for event validation.

## Features

- **Multiple Schema Providers**: Load schemas from files or document stores
- **JSON Schema Validation**: Full JSON Schema validation with support for schema references
- **Flexible Storage**: Works with any DocumentStore backend (MongoDB, etc.)
- **Caching**: Built-in schema caching for performance

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

### Document Store Schema Provider

```python
from copilot_schema_validation import DocumentStoreSchemaProvider, validate_json

# Load schemas from MongoDB
provider = DocumentStoreSchemaProvider(
    mongo_uri="mongodb://localhost:27017"
)

schema = provider.get_schema("ArchiveIngested")
is_valid, errors = validate_json(document, schema, schema_provider=provider)
```

## Testing

Run tests with pytest:

```bash
cd adapters/copilot_schema_validation
pytest tests/ -v
```

For unit tests only (skip integration tests):

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
