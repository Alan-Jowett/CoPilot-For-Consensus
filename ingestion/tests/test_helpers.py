# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test helper utilities for schema validation and event testing."""

import os
import tempfile
from types import SimpleNamespace
from typing import Any

from copilot_schema_validation import create_schema_provider, validate_json
from copilot_archive_store.local_volume_archive_store import LocalVolumeArchiveStore


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
        "metrics_type": "noop",
        "retry_max_attempts": 3,
        "retry_backoff_seconds": 1,
        "error_reporter_type": "console",
        "sentry_dsn": None,
        "sentry_environment": "test",
        "archive_store_type": "local",
        "sources": [],
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def make_archive_store(base_path: str) -> LocalVolumeArchiveStore:
    """Create a local archive store for tests."""
    return LocalVolumeArchiveStore(base_path=base_path)


def make_source(**overrides) -> dict:
    # Use the system temporary directory to avoid hardcoded paths
    default_tmp_file = os.path.join(tempfile.gettempdir(), "test.mbox")
    source = {
        "name": overrides.pop("name", "test-source"),
        "source_type": overrides.pop("source_type", "local"),
        "url": overrides.pop("url", default_tmp_file),
        "enabled": overrides.pop("enabled", True),
    }
    source.update(overrides)
    return source


def get_schema_provider():
    """Get a schema provider for testing.

    Returns:
        SchemaProvider instance configured with repository schemas
    """
    from pathlib import Path
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "events"
    return create_schema_provider(schema_dir=str(schema_dir))


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
