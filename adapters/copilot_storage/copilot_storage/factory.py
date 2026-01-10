# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating document store instances based on configuration."""

from __future__ import annotations

import logging
from typing import Any

from copilot_config import DriverConfig

from .azure_cosmos_document_store import AzureCosmosDocumentStore
from .document_store import DocumentStore
from .inmemory_document_store import InMemoryDocumentStore
from .mongo_document_store import MongoDocumentStore
from .validating_document_store import ValidatingDocumentStore

logger = logging.getLogger(__name__)


def _get_schema_provider() -> Any | None:
    """Attempt to load a schema provider for validation.

    This factory uses a fixed schema type of 'documents' for all document store
    instances. This is intentional as the factory creates document stores, which
    should always validate against document schemas regardless of the driver type.

    Returns:
        None if schema validation is not available.
    """

    try:
        from copilot_schema_validation import create_schema_provider  # type: ignore[import-not-found]

        return create_schema_provider(schema_type="documents")
    except ImportError:
        logger.warning(
            "copilot_schema_validation not available; document store will not validate schemas"
        )
        return None


def create_document_store(
    driver_name: str,
    driver_config: DriverConfig,
    enable_validation: bool = True,
    strict_validation: bool = True,
    validate_reads: bool = False,
) -> DocumentStore:
    """Create a document store instance.

    Args:
        driver_name: Backend type (required). Options: "mongodb", "azurecosmos", "cosmos", "cosmosdb", "inmemory".
        driver_config: Backend configuration as DriverConfig instance.
        enable_validation: If True (default), wraps the store in ValidatingDocumentStore.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but operations proceed.
        validate_reads: If True, validate documents on reads (get_document). Has performance impact.

    Returns:
        DocumentStore instance.

    Raises:
        ValueError: If driver_name is unknown.
    """

    driver_lower = driver_name.lower()

    schema_provider: Any | None = None
    if enable_validation:
        schema_provider = getattr(driver_config, "schema_provider", None)
        if schema_provider is None:
            schema_provider = _get_schema_provider()

    if driver_lower == "mongodb":
        backend = MongoDocumentStore.from_config(driver_config)
        if enable_validation:
            return ValidatingDocumentStore(
                store=backend,
                schema_provider=schema_provider,
                strict=bool(strict_validation),
                validate_reads=bool(validate_reads),
            )
        return backend

    if driver_lower == "azurecosmos":
        backend = AzureCosmosDocumentStore.from_config(driver_config)
        if enable_validation:
            return ValidatingDocumentStore(
                store=backend,
                schema_provider=schema_provider,
                strict=bool(strict_validation),
                validate_reads=bool(validate_reads),
            )
        return backend

    if driver_lower == "inmemory":
        backend = InMemoryDocumentStore.from_config(driver_config)
        if enable_validation:
            return ValidatingDocumentStore(
                store=backend,
                schema_provider=schema_provider,
                strict=bool(strict_validation),
                validate_reads=bool(validate_reads),
            )
        return backend

    raise ValueError(f"Unknown document store driver: {driver_name}")
