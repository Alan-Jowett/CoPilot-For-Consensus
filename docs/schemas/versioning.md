<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schema Versioning Guide

This document outlines the versioning strategy for all JSON Schemas used in the Copilot for Consensus project, including event schemas and document schemas. It ensures long-term compatibility, contributor clarity, and safe schema evolution.

---

## 📦 Schema Types

We maintain two categories of schemas:

- **Event Schemas**: Define the structure of messages passed through the pub/sub pipeline (e.g., ArchiveIngested, SummaryComplete). Located in `docs/schemas/events/`.
- **Document Schemas**: Define the structure of data stored in the document database (e.g., archives, messages, chunks, threads, summaries). Located in `docs/schemas/documents/`.

---

## 🧱 Versioning Strategy

All document schemas are versioned using a directory-based approach:

```
docs/
  schemas/
    events/
      event-envelope.schema.json  (shared envelope, contains version field)
      ArchiveIngested.schema.json
      SummaryComplete.schema.json
      ...
    documents/
      v1/
        archives.schema.json
        chunks.schema.json
        messages.schema.json
        summaries.schema.json
        threads.schema.json
      v2/  (future versions)
        ...
      collections.config.json
```

Each schema version is immutable. Any breaking change (e.g., removing a field, changing a type) must result in a new version (e.g., v2/).

---

## 📄 Document Schema Versioning

Document schemas (archives, messages, chunks, threads, summaries) now include an explicit `"version"` field:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://alan-jowett.github.io/CoPilot-For-Consensus/schemas/documents/messages.schema.json",
  "version": "v1",
  "title": "messages collection",
  ...
}
```

### Version History

| Version | Date       | Changes | Breaking? |
|---------|------------|---------|-----------|
| v1      | 2025-01-21 | Initial versioned schemas for archives, chunks, messages, summaries, threads | No (initial version) |

---

## 🧩 Event Envelope Versioning

All events are wrapped in a shared envelope defined in `event-envelope.schema.json`, which includes:

```json
{
  "event_type": "ArchiveIngested",
  "event_id": "uuid-v4",
  "timestamp": "ISO-8601-datetime",
  "version": "1.0",
  "data": { ... }
}
```

This allows services to dynamically resolve and validate the correct schema for the payload.

---

## 🔍 Schema Registry

The `collections.config.json` file serves as a schema registry, mapping collection names to their versioned schema paths:

```json
{
  "collections": [
    {
      "name": "messages",
      "schema": "/schemas/documents/v1/messages.schema.json",
      "indexes": [...]
    }
  ]
}
```

This enables:
- Dynamic validation at runtime
- Support for multiple versions in parallel
- Clear contributor expectations

For parallel version support in the future:

```json
{
  "collections": [
    {
      "name": "messages",
      "version": "v1",
      "schema": "/schemas/documents/v1/messages.schema.json"
    },
    {
      "name": "messages",
      "version": "v2",
      "schema": "/schemas/documents/v2/messages.schema.json"
    }
  ]
}
```

---

## 🔄 Making Schema Changes

### Backward-Compatible Changes (No Version Change Required)

- ✅ Adding optional fields
- ✅ Relaxing constraints (e.g., removing minLength)
- ✅ Adding enum values
- ✅ Documentation updates

### Breaking Changes (Require New Version)

- ❌ Removing required fields
- ❌ Changing field types
- ❌ Tightening constraints (e.g., adding minLength to existing field)
- ❌ Renaming fields
- ❌ Removing enum values

All breaking changes require:
1. Creating a new version directory (e.g., `v2/`)
2. Updating the `version` field in schemas
3. Implementing migration scripts for existing data
4. Updating all code references
5. Comprehensive testing

---

## 🧪 Validation and Testing

### Loading Versioned Schemas

```python
from copilot_schema_validation import FileSchemaProvider, validate_json
from pathlib import Path

# Load schema provider for specific version
schema_dir = Path("docs/schemas/documents/v1")
provider = FileSchemaProvider(schema_dir=schema_dir)

# Get and validate against schema
messages_schema = provider.get_schema("messages")
is_valid, errors = validate_json(document, messages_schema)
```

### Testing Strategy

- **Regression tests**: Ensure new versions don't break existing functionality
- **Migration tests**: Validate that migration scripts correctly transform documents
- **Compatibility tests**: Verify that services can handle multiple versions
- **Schema validation tests**: Test that invalid documents are rejected

See `adapters/copilot_schema_validation/tests/test_document_schema_regression.py` for examples.

---

## 📚 Contributor Tips

- Always validate your payloads against the correct schema version
- Use the schema registry to resolve schemas dynamically
- When in doubt, create a new version rather than modifying an existing one
- Update `collections.config.json` when changing schema paths
- Add tests for any schema changes
- Document version changes in this file

---

## 📖 References

- [message-schemas.md](./message-schemas.md) - Complete schema documentation
- [../development/forward-progress.md](../development/forward-progress.md) - Status field lifecycles and retry patterns
- [JSON Schema Specification](https://json-schema.org/specification.html)
- Test examples: `adapters/copilot_schema_validation/tests/`
