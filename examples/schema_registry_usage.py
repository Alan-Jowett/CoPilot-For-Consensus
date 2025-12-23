#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example demonstrating schema registry usage.

This example shows how to use the schema registry for:
- Loading schemas by type and version
- Validating documents against schemas
- Listing available schemas
- Handling different schema versions
"""

import sys
from pathlib import Path

# Add adapter to path for standalone execution
sys.path.insert(0, str(Path(__file__).parent.parent / "adapters" / "copilot_schema_validation"))

from copilot_schema_validation import (
    get_schema_path,
    list_schemas,
    load_schema,
    validate_json,
    validate_registry,
)


def example_basic_usage():
    """Example 1: Basic schema loading and validation."""
    print("=" * 70)
    print("Example 1: Basic Schema Loading and Validation")
    print("=" * 70)

    # Load a schema
    schema = load_schema("ArchiveIngested", "v1")
    print(f"\nLoaded schema: {schema['title']}")
    print(f"Schema ID: {schema.get('$id', 'N/A')}")

    # Example event that conforms to the schema
    # Note: This is raw JSON, not a Pydantic model instance
    # The version field must match the schema (string like "v1")
    valid_event = {
        "event_type": "ArchiveIngested",
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "timestamp": "2025-12-21T12:00:00Z",
        "version": "v1",
        "data": {
            "archive_id": "a1b2c3d4e5f6789a",
            "source_name": "ietf-announce",
            "source_type": "rsync",
            "source_url": "rsync://rsync.ietf.org/ietf-mail-archive/",
            "file_path": "/archives/ietf-announce.mbox",
            "file_size_bytes": 1048576,
            "file_hash_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "ingestion_started_at": "2025-12-21T11:00:00Z",
            "ingestion_completed_at": "2025-12-21T12:00:00Z"
        }
    }

    # Validate the event
    is_valid, errors = validate_json(valid_event, schema)
    print(f"\nValidation result: {'✓ Valid' if is_valid else '✗ Invalid'}")
    if errors:
        print("Errors:")
        for error in errors:
            print(f"  - {error}")

    # Example of invalid event (missing required field)
    invalid_event = {
        "event_type": "ArchiveIngested",
        "event_id": "123e4567-e89b-12d3-a456-426614174000",
        "timestamp": "2025-12-21T12:00:00Z",
        "version": "v1",
        "data": {
            "archive_id": "a1b2c3d4e5f6789a",
            "source_name": "ietf-announce",
            # Missing required fields...
        }
    }

    is_valid, errors = validate_json(invalid_event, schema)
    print(f"\nInvalid event validation: {'✓ Valid' if is_valid else '✗ Invalid (expected)'}")
    if errors:
        print("Expected errors:")
        for error in errors[:3]:  # Show first 3 errors
            print(f"  - {error}")

    print()


def example_list_schemas():
    """Example 2: Listing all available schemas."""
    print("=" * 70)
    print("Example 2: Listing Available Schemas")
    print("=" * 70)

    schemas = list_schemas()

    # Group by category
    events = [s for s in schemas if "events/" in s[2]]
    documents = [s for s in schemas if "documents/" in s[2]]

    print(f"\nTotal schemas: {len(schemas)}")
    print(f"Event schemas: {len(events)}")
    print(f"Document schemas: {len(documents)}")

    print("\nEvent Schemas:")
    for schema_type, version, path in events[:5]:  # Show first 5
        print(f"  - {schema_type:30} {version:5} {path}")
    remaining_events = len(events) - 5
    if remaining_events > 0:
        print(f"  ... and {remaining_events} more")

    print("\nDocument Schemas:")
    for schema_type, version, path in documents:
        print(f"  - {schema_type:30} {version:5} {path}")

    print()


def example_schema_paths():
    """Example 3: Working with schema paths."""
    print("=" * 70)
    print("Example 3: Getting Schema File Paths")
    print("=" * 70)

    schemas_to_check = [
        ("ArchiveIngested", "v1"),
        ("Archive", "v1"),
        ("Message", "v1"),
    ]

    for schema_type, version in schemas_to_check:
        path = get_schema_path(schema_type, version)
        print(f"\n{schema_type} ({version}):")
        print(f"  Path: {path}")
        print(f"  Exists: {Path(path).exists()}")

    print()


def example_validate_registry():
    """Example 4: Validating the entire registry."""
    print("=" * 70)
    print("Example 4: Validating Schema Registry")
    print("=" * 70)

    print("\nValidating all registered schemas...")
    valid, errors = validate_registry()

    if valid:
        print("✓ All schemas are valid!")
    else:
        print(f"✗ Found {len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")

    print()


def example_document_validation():
    """Example 5: Validating a document schema."""
    print("=" * 70)
    print("Example 5: Document Schema Validation")
    print("=" * 70)

    # Load document schema
    schema = load_schema("Archive", "v1")
    print(f"\nLoaded schema: {schema['title']}")

    # Valid archive document
    valid_archive = {
        "_id": "a1b2c3d4e5f67890",
        "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "file_size_bytes": 1048576,
        "source": "ietf-announce",
        "ingestion_date": "2025-12-21T12:00:00Z",
        "status": "processed"
    }

    is_valid, errors = validate_json(valid_archive, schema)
    print(f"\nValidation result: {'✓ Valid' if is_valid else '✗ Invalid'}")
    if errors:
        for error in errors:
            print(f"  - {error}")

    print()


def example_error_handling():
    """Example 6: Error handling."""
    print("=" * 70)
    print("Example 6: Error Handling")
    print("=" * 70)

    # Try to load a non-existent schema
    print("\nAttempting to load non-existent schema...")
    try:
        load_schema("NonExistentType", "v99")
    except KeyError as e:
        print(f"✓ Expected error caught: {str(e)[:80]}...")

    print()


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print(" Schema Registry Usage Examples")
    print("=" * 70 + "\n")

    try:
        example_basic_usage()
        example_list_schemas()
        example_schema_paths()
        example_validate_registry()
        example_document_validation()
        example_error_handling()

        print("=" * 70)
        print("All examples completed successfully!")
        print("=" * 70)
        print()

    except Exception as e:
        print(f"\n✗ Error running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
