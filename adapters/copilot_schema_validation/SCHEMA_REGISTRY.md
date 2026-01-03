<!-- SPDX-License-Identifier: MIT
  Copyright (c) 2025 Copilot-for-Consensus contributors -->
# Schema Registry

The Schema Registry provides centralized management and versioned access to all JSON schemas in the Copilot-for-Consensus system.

## Overview

The schema registry maps `(type, version)` pairs to their corresponding JSON Schema file paths, enabling:
- **Dynamic validation** based on type and version
- **Schema evolution** support with multiple versions in parallel
- **Centralized schema management** with a single source of truth
- **Better contributor onboarding** through clear documentation

## Installation

The schema registry is part of the `copilot_schema_validation` adapter:

```python
from copilot_schema_validation import (
    get_schema_path,
    load_schema,
    list_schemas,
    validate_registry,
    SCHEMA_REGISTRY,
)
```

## Usage

### Loading a Schema

```python
from copilot_schema_validation import load_schema

# Load a schema by type and version
schema = load_schema("ArchiveIngested", "v1")
print(schema["title"])  # "ArchiveIngested Event"
```

### Getting a Schema Path

```python
from copilot_schema_validation import get_schema_path

# Get the absolute path to a schema file
path = get_schema_path("Archive", "v1")
# Returns: "/path/to/docs/schemas/documents/archives.schema.json"
```

### Listing All Schemas

```python
from copilot_schema_validation import list_schemas

# Get all registered schemas
schemas = list_schemas()
for schema_type, version, path in schemas:
    print(f"{schema_type} {version}: {path}")
```

### Validating the Registry

```python
from copilot_schema_validation import validate_registry

# Validate that all registered schemas exist and are valid JSON
valid, errors = validate_registry()
if not valid:
    for error in errors:
        print(f"Error: {error}")
```

### Accessing the Registry Dictionary

```python
from copilot_schema_validation import SCHEMA_REGISTRY

# Direct access to the registry mapping
for key, path in SCHEMA_REGISTRY.items():
    version, schema_type = key.split(".", 1)
    print(f"{schema_type} ({version}): {path}")
```

## Command-Line Interface

The schema registry includes a CLI tool for validation and inspection:

### Validate All Schemas

```bash
python3 scripts/validate_schema_registry.py validate
```

Output:
```
INFO: Validating schema registry...
INFO: ✓ All 21 registered schemas are valid
```

### List Schemas

```bash
# Table format (default)
python3 scripts/validate_schema_registry.py list

# CSV format
python3 scripts/validate_schema_registry.py list --format csv

# JSON format
python3 scripts/validate_schema_registry.py list --format json
```

### Show Schema Information

```bash
python3 scripts/validate_schema_registry.py info ArchiveIngested v1
```

Output:
```
Schema: ArchiveIngested (version v1)
  Relative path: events/ArchiveIngested.schema.json
  Absolute path: /path/to/docs/schemas/events/ArchiveIngested.schema.json
  Exists: ✓
  Title: ArchiveIngested Event
  Schema ID: https://alan-jowett.github.io/...
```

### Generate Markdown Documentation

```bash
python3 scripts/validate_schema_registry.py markdown > docs/SCHEMAS.md
```

This generates a formatted markdown document with all registered schemas organized by category.

## Schema Naming Convention

Schemas are registered using the format `version.Type`:

- **Version**: Schema version (e.g., `v1`, `v2`)
- **Type**: Schema type name in PascalCase (e.g., `ArchiveIngested`, `Archive`)

Example registry keys:
- `v1.ArchiveIngested` → Event schema
- `v1.Archive` → Document schema
- `v1.UserRoles` → Role store schema

## Adding New Schemas

To register a new schema:

1. **Add the schema file** to the appropriate directory:
   - Events: `docs/schemas/events/`
   - Documents: `docs/schemas/documents/`
   - Role store: `docs/schemas/role_store/`

2. **Register in `schema_registry.py`**:
   ```python
   SCHEMA_REGISTRY = {
       # ... existing entries ...
       "v1.NewEventType": "events/NewEventType.schema.json",
   }
   ```

3. **Validate the registry**:
   ```bash
   python3 scripts/validate_schema_registry.py validate
   ```

4. **Run tests**:
   ```bash
   cd adapters/copilot_schema_validation
   python3 -m pytest tests/test_schema_registry.py -v
   ```

## Schema Evolution

When evolving schemas to new versions:

1. **Create the new schema file** with version suffix (if organizing by version):
   ```
   docs/schemas/events/v2/ArchiveIngested.schema.json
   ```

2. **Register both versions**:
   ```python
   SCHEMA_REGISTRY = {
       "v1.ArchiveIngested": "events/ArchiveIngested.schema.json",
       "v2.ArchiveIngested": "events/v2/ArchiveIngested.schema.json",
   }
   ```

3. **Update services** to use the appropriate version:
   ```python
   # Old version
   schema_v1 = load_schema("ArchiveIngested", "v1")

   # New version
   schema_v2 = load_schema("ArchiveIngested", "v2")
   ```

## Error Handling

The schema registry provides clear error messages:

### Schema Not Registered

```python
try:
    schema = load_schema("NonExistent", "v1")
except KeyError as e:
    # Error: Schema not registered: v1.NonExistent
    # Available schemas: v1.Archive, v1.ArchiveIngested, ...
    pass
```

### Schema File Not Found

```python
try:
    path = get_schema_path("MissingSchema", "v1")
except FileNotFoundError as e:
    # Error: Schema file not found: /path/to/schema.json
    # Registry points to: events/MissingSchema.schema.json
    pass
```

### Invalid JSON

```python
try:
    schema = load_schema("InvalidSchema", "v1")
except json.JSONDecodeError as e:
    # Error: Invalid JSON in schema file
    pass
```

## Integration with Existing Code

The schema registry works alongside the existing `FileSchemaProvider`:

```python
from copilot_schema_validation import FileSchemaProvider, load_schema

# Existing approach (by event type name only)
provider = FileSchemaProvider()
schema = provider.get_schema("ArchiveIngested")

# New approach (with explicit versioning)
schema = load_schema("ArchiveIngested", "v1")
```

Both approaches are supported for backward compatibility. The registry is recommended for new code that requires version awareness.

## Testing

The schema registry includes comprehensive tests:

```bash
cd adapters/copilot_schema_validation
python3 -m pytest tests/test_schema_registry.py -v
```

Test coverage includes:
- Schema path resolution
- Schema loading and caching
- Error handling for missing/invalid schemas
- Registry validation
- Metadata retrieval
- All registered schemas are loadable

## Contributing

When adding new schemas or modifying the registry:

1. Update `SCHEMA_REGISTRY` in `schema_registry.py`
2. Add appropriate test cases in `test_schema_registry.py`
3. Run the validation script to ensure all schemas are valid
4. Update the generated documentation with `markdown` command
5. Ensure all tests pass

## Related Documentation

- [Schema Versioning Guide](../docs/SCHEMAS.md) - Auto-generated list of all schemas
- [Event Envelope Schema](../docs/schemas/events/event-envelope.schema.json)
- [Architecture Documentation](../docs/architecture/overview.md)
