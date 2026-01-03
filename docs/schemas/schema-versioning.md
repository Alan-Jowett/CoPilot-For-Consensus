<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Schema Versioning Guide

Versioning strategy for JSON schemas (events and documents) to ensure compatibility and safe evolution.

## Schema Types
- **Event Schemas**: Pub/sub messages (ArchiveIngested, SummaryComplete) under `docs/schemas/events/`.
- **Document Schemas**: Database payloads (archives, messages, chunks, threads, summaries) under `docs/schemas/documents/`.

## Directory-Based Versioning
```
documents/
  schemas/
    events/
      event-envelope.schema.json
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
      v2/
        ...
      collections.config.json
```
Each version directory is immutable; breaking changes require a new version (v2, v3...).

## Document Schema Version Field
Schemas include an explicit `"version"` field (e.g., `"v1"`).

| Version | Date | Changes | Breaking? |
|---------|------|---------|-----------|
| v1 | 2025-01-21 | Initial versioned schemas for archives, chunks, messages, summaries, threads | No |

## Event Envelope Versioning
Events wrap payloads in `event-envelope.schema.json` with fields like `event_type`, `event_id`, `timestamp`, and `version` to resolve the correct payload schema.

## Schema Registry
`collections.config.json` maps collections to schema paths (and versions for future parallel support). Example:
```json
{
  "collections": [
    {
      "name": "messages",
      "version": "v1",
      "schema": "/schemas/documents/v1/messages.schema.json"
    }
  ]
}
```

## Change Rules
Backward-compatible (no new version):
- Add optional fields
- Relax constraints
- Add enum values
- Documentation-only updates

Breaking (new version required):
- Remove required fields or enum values
- Change field types
- Tighten constraints
- Rename fields

Process for breaking changes:
1) Create new version directory (e.g., `v2/`).
2) Update schema `version` field.
3) Provide migration scripts.
4) Update code references.
5) Add regression/compat tests.

## Validation & Testing
```python
from copilot_schema_validation import FileSchemaProvider, validate_json
from pathlib import Path

schema_dir = Path("docs/schemas/documents/v1")
provider = FileSchemaProvider(schema_dir=schema_dir)
messages_schema = provider.get_schema("messages")
is_valid, errors = validate_json(document, messages_schema)
```

Recommended tests: regression, migration, compatibility, and schema validation (see `adapters/copilot_schema_validation/tests/`).

## Contributor Tips
- Validate payloads against the correct version.
- Prefer new versions over mutating existing schemas.
- Update `collections.config.json` when paths change.
- Add tests and document version changes here.

## References
- [Schema index](README.md)
- [Forward progress](../../documents/FORWARD_PROGRESS.md)
- [JSON Schema Specification](https://json-schema.org/specification.html)
- Examples: `adapters/copilot_schema_validation/tests/`
