# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Test helper utilities for schema validation and event testing."""

import os
import tempfile
from typing import Any

from copilot_schema_validation import create_schema_provider, validate_json
from copilot_archive_store.local_volume_archive_store import LocalVolumeArchiveStore

from copilot_config.generated.adapters.archive_store import (
    AdapterConfig_ArchiveStore,
    DriverConfig_ArchiveStore_Local,
)
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_config.generated.adapters.error_reporter import (
    AdapterConfig_ErrorReporter,
    DriverConfig_ErrorReporter_Silent,
)
from copilot_config.generated.adapters.logger import (
    AdapterConfig_Logger,
    DriverConfig_Logger_Silent,
)
from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
    DriverConfig_MessageBus_Noop,
)
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_Noop,
)
from copilot_config.generated.adapters.secret_provider import (
    AdapterConfig_SecretProvider,
    DriverConfig_SecretProvider_Local,
)
from copilot_config.generated.services.ingestion import ServiceConfig_Ingestion, ServiceSettings_Ingestion


def make_config(**overrides):
    # Some older tests passed "sources" into config; sources are now provided
    # explicitly to IngestionService, so ignore it here.
    overrides.pop("sources", None)

    storage_path = overrides.pop("storage_path", "/data/raw_archives")
    max_retries = overrides.pop("max_retries", 3)
    request_timeout_seconds = overrides.pop("request_timeout_seconds", 60)
    archive_store_type = overrides.pop("archive_store_type", "local")

    if overrides:
        unknown = ", ".join(sorted(overrides.keys()))
        raise TypeError(f"Unknown config override(s): {unknown}")

    settings = ServiceSettings_Ingestion(
        storage_path=storage_path,
        max_retries=max_retries,
        request_timeout_seconds=request_timeout_seconds,
        archive_store_type=archive_store_type,
    )

    return ServiceConfig_Ingestion(
        service_settings=settings,
        archive_store=AdapterConfig_ArchiveStore(
            archive_store_type="local",
            driver=DriverConfig_ArchiveStore_Local(archive_base_path=storage_path),
        ),
        document_store=AdapterConfig_DocumentStore(
            doc_store_type="inmemory",
            driver=DriverConfig_DocumentStore_Inmemory(),
        ),
        error_reporter=AdapterConfig_ErrorReporter(
            error_reporter_type="silent",
            driver=DriverConfig_ErrorReporter_Silent(),
        ),
        logger=AdapterConfig_Logger(
            logger_type="silent",
            driver=DriverConfig_Logger_Silent(level="INFO", name="ingestion-test"),
        ),
        message_bus=AdapterConfig_MessageBus(
            message_bus_type="noop",
            driver=DriverConfig_MessageBus_Noop(),
        ),
        metrics=AdapterConfig_Metrics(
            metrics_type="noop",
            driver=DriverConfig_Metrics_Noop(),
        ),
        secret_provider=AdapterConfig_SecretProvider(
            secret_provider_type="local",
            driver=DriverConfig_SecretProvider_Local(),
        ),
    )


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
