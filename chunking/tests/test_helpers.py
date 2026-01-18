# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test helper utilities for schema validation and event testing."""

from pathlib import Path
from typing import Any

from copilot_schema_validation import create_schema_provider, validate_json


def get_schema_provider(schema_type: str = "events"):
    """Get a schema provider for testing.

    Args:
        schema_type: Type of schemas to load ("events" or "documents")

    Returns:
        Schema provider instance configured with repository schemas.
    """
    if schema_type == "documents":
        schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
        return create_schema_provider(schema_dir=schema_dir, schema_type="documents")
    return create_schema_provider()


def validate_event_against_schema(event: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validate an event against its JSON schema.

    Args:
        event: Event dictionary containing event_type and other fields

    Returns:
        Tuple of (is_valid, error_messages)
    """
    event_type = event.get("event_type")
    if not event_type:
        return False, ["Event missing 'event_type' field"]

    schema_provider = get_schema_provider()
    schema = schema_provider.get_schema(event_type)

    if schema is None:
        return False, [f"No schema found for event type '{event_type}'"]

    return validate_json(event, schema, schema_provider=schema_provider)


def assert_valid_event_schema(event: dict[str, Any]) -> None:
    """Assert that an event is valid according to its JSON schema.

    Args:
        event: Event dictionary to validate

    Raises:
        AssertionError: If validation fails
    """
    is_valid, errors = validate_event_against_schema(event)
    assert is_valid, f"Event validation failed: {'; '.join(errors)}"


def validate_document_against_schema(document: dict[str, Any], collection: str) -> tuple[bool, list[str]]:
    """Validate a document against its JSON schema.

    Args:
        document: Document dictionary to validate
        collection: Collection name (e.g., "messages", "chunks", "threads")

    Returns:
        Tuple of (is_valid, error_messages)
    """
    schema_provider = get_schema_provider(schema_type="documents")
    schema = schema_provider.get_schema(collection)

    if schema is None:
        return False, [f"No schema found for collection '{collection}'"]

    return validate_json(document, schema, schema_provider=schema_provider)


def assert_valid_document_schema(document: dict[str, Any], collection: str) -> None:
    """Assert that a document is valid according to its JSON schema.

    Args:
        document: Document dictionary to validate
        collection: Collection name (e.g., "messages", "chunks", "threads")

    Raises:
        AssertionError: If validation fails
    """
    is_valid, errors = validate_document_against_schema(document, collection)
    assert is_valid, f"Document validation failed for collection '{collection}': {'; '.join(errors)}"
