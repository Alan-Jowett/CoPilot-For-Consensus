#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Example usage of the ValidatingEventPublisher.

This script demonstrates how to use the ValidatingEventPublisher
to enforce schema validation on published events.

Note: In a production environment, schemas would typically be stored in
a database or a well-known filesystem location. This example uses a
simple mock schema provider for demonstration purposes.
"""

from copilot_events import (
    create_publisher,
    ValidatingEventPublisher,
    ValidationError,
)


class SimpleSchemaProvider:
    """Simple schema provider for demonstration purposes."""

    def __init__(self):
        """Initialize with example schemas."""
        self.schemas = {
            "ArchiveIngested": {
                "type": "object",
                "properties": {
                    "event_type": {"type": "string", "const": "ArchiveIngested"},
                    "event_id": {"type": "string"},
                    "timestamp": {"type": "string"},
                    "version": {"type": "string"},
                    "data": {
                        "type": "object",
                        "properties": {
                            "archive_id": {"type": "string"},
                            "source_name": {"type": "string"},
                            "file_path": {"type": "string"},
                        },
                        "required": ["archive_id", "source_name", "file_path"]
                    }
                },
                "required": ["event_type", "event_id", "timestamp", "version", "data"]
            }
        }

    def get_schema(self, event_type: str):
        """Return schema for event type or None if not found."""
        return self.schemas.get(event_type)


def main():
    """Demonstrate validating event publisher functionality."""

    print("=" * 60)
    print("ValidatingEventPublisher Examples")
    print("=" * 60)
    print()

    # Create base publisher (using noop for this example)
    base_publisher = create_publisher("noop")
    base_publisher.connect()

    # Create schema provider with example schemas
    schema_provider = SimpleSchemaProvider()

    # Example 1: Strict mode with valid event
    print("Example 1: Publishing valid event in strict mode")
    print("-" * 60)

    validating_publisher = ValidatingEventPublisher(
        publisher=base_publisher,
        schema_provider=schema_provider,
        strict=True
    )

    valid_event = {
        "event_type": "ArchiveIngested",
        "event_id": "a1b2c3d4e5f67890",
        "timestamp": "2025-12-11T00:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "archive-123",
            "source_name": "ietf-quic",
            "file_path": "/data/archives/quic.mbox"
        }
    }

    try:
        validating_publisher.publish(
            "copilot.events",
            "archive.ingested",
            valid_event
        )
        print("✓ Event published successfully")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")
    print()

    # Example 2: Strict mode with invalid event
    print("Example 2: Publishing invalid event in strict mode (will fail)")
    print("-" * 60)

    invalid_event = {
        "event_type": "ArchiveIngested",
        "event_id": "550e8400-e29b-41d4-a716-446655440001",
        "timestamp": "2025-12-11T00:00:00Z",
        "version": "1.0",
        "data": {
            "archive_id": "archive-456",
            # Missing required fields: source_name, file_path
        }
    }

    try:
        validating_publisher.publish(
            "copilot.events",
            "archive.ingested",
            invalid_event
        )
        print("✓ Event published successfully")
    except ValidationError as e:
        print(f"✗ Validation failed (as expected):")
        print(f"   Event Type: {e.event_type}")
        print(f"   Errors:")
        for error in e.errors[:3]:  # Show first 3 errors
            print(f"     - {error}")
    print()

    # Example 3: Non-strict mode with invalid event
    print("Example 3: Publishing invalid event in non-strict mode (will succeed)")
    print("-" * 60)

    permissive_publisher = ValidatingEventPublisher(
        publisher=base_publisher,
        schema_provider=schema_provider,
        strict=False
    )

    try:
        permissive_publisher.publish(
            "copilot.events",
            "archive.ingested",
            invalid_event
        )
        print("✓ Event published despite validation errors")
        print("   (Warnings logged, but publish proceeded)")
    except ValidationError as e:
        print(f"✗ Unexpected validation error: {e}")
    print()

    # Example 4: Without schema provider
    print("Example 4: Publishing without schema provider (no validation)")
    print("-" * 60)

    no_validation_publisher = ValidatingEventPublisher(
        publisher=base_publisher,
        schema_provider=None,
        strict=True
    )

    arbitrary_event = {
        "event_type": "UnknownEvent",
        "anything": "goes",
        "no": "validation"
    }

    try:
        no_validation_publisher.publish(
            "copilot.events",
            "unknown.event",
            arbitrary_event
        )
        print("✓ Event published without validation")
    except ValidationError as e:
        print(f"✗ Unexpected validation error: {e}")
    print()

    # Example 5: Using event models
    print("Example 5: Publishing using event model classes")
    print("-" * 60)

    from copilot_events import ArchiveIngestedEvent

    event_obj = ArchiveIngestedEvent(
        data={
            "archive_id": "archive-789",
            "source_name": "ietf-http",
            "file_path": "/data/archives/http.mbox"
        }
    )

    try:
        validating_publisher.publish(
            "copilot.events",
            "archive.ingested",
            event_obj.to_dict()
        )
        print("✓ Event from model published successfully")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")
    print()

    print("=" * 60)
    print("Examples completed!")
    print("=" * 60)

    base_publisher.disconnect()


if __name__ == "__main__":
    main()
