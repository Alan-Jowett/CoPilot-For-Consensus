# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test helper utilities for schema validation and event testing."""

from typing import Dict, Any
from types import SimpleNamespace
from copilot_schema_validation import FileSchemaProvider, validate_json


def make_config(**overrides):
    defaults = {
        "storage_path": "/data/raw_archives",
        "message_bus_host": "messagebus",
        "message_bus_port": 5672,
        "message_bus_user": "guest",
        "message_bus_password": "guest",
        "message_bus_type": "rabbitmq",
        "log_level": "INFO",
        "log_type": "stdout",
        "logger_name": "ingestion-test",
        "metrics_backend": "noop",
        "retry_max_attempts": 3,
        "retry_backoff_seconds": 1,
        "error_reporter_type": "console",
        "sentry_dsn": None,
        "sentry_environment": "test",
        "sources": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_source(**overrides) -> dict:
    source = {
        "name": overrides.pop("name", "test-source"),
        "source_type": overrides.pop("source_type", "local"),
        "url": overrides.pop("url", "/tmp/test.mbox"),
        "enabled": overrides.pop("enabled", True),
    }
    source.update(overrides)
    return source


def get_schema_provider():
    """Get a FileSchemaProvider for testing.
    
    Returns:
        FileSchemaProvider instance configured with repository schemas
    """
    from pathlib import Path
    schema_dir = Path(__file__).parent.parent.parent / "documents" / "schemas" / "events"
    return FileSchemaProvider(schema_dir=schema_dir)


def validate_event_against_schema(event: Dict[str, Any]) -> tuple[bool, list[str]]:
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


def assert_valid_event_schema(event: Dict[str, Any]) -> None:
    """Assert that an event is valid according to its JSON schema.
    
    Args:
        event: Event dictionary to validate
        
    Raises:
        AssertionError: If validation fails
    """
    is_valid, errors = validate_event_against_schema(event)
    assert is_valid, f"Event validation failed: {'; '.join(errors)}"
