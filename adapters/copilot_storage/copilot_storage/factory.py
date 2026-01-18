# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Factory for creating document store instances based on configuration."""

from __future__ import annotations

import logging
from typing import Any, TypeAlias

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_AzureCosmosdb,
    DriverConfig_DocumentStore_Inmemory,
    DriverConfig_DocumentStore_Mongodb,
)

from .azure_cosmos_document_store import AzureCosmosDocumentStore
from .document_store import DocumentStore
from .inmemory_document_store import InMemoryDocumentStore
from .mongo_document_store import MongoDocumentStore
from .validating_document_store import ValidatingDocumentStore

logger = logging.getLogger(__name__)

_DriverConfig: TypeAlias = (
    DriverConfig_DocumentStore_Mongodb | DriverConfig_DocumentStore_AzureCosmosdb | DriverConfig_DocumentStore_Inmemory
)


def _build_mongodb(config: _DriverConfig) -> DocumentStore:
    if not isinstance(config, DriverConfig_DocumentStore_Mongodb):
        raise TypeError("driver config must be DriverConfig_DocumentStore_Mongodb")
    return MongoDocumentStore.from_config(config)


def _build_azure_cosmosdb(config: _DriverConfig) -> DocumentStore:
    if not isinstance(config, DriverConfig_DocumentStore_AzureCosmosdb):
        raise TypeError("driver config must be DriverConfig_DocumentStore_AzureCosmosdb")
    return AzureCosmosDocumentStore.from_config(config)


def _build_inmemory(config: _DriverConfig) -> DocumentStore:
    if not isinstance(config, DriverConfig_DocumentStore_Inmemory):
        raise TypeError("driver config must be DriverConfig_DocumentStore_Inmemory")
    return InMemoryDocumentStore.from_config(config)


def _get_schema_provider() -> Any:
    """Load a schema provider for validation.

    This factory uses a fixed schema type of 'documents' for all document store
    instances. This is intentional as the factory creates document stores, which
    should always validate against document schemas regardless of the driver type.

    Returns:
        Schema provider instance.

    Raises:
        ImportError: If copilot_schema_validation is not installed.
    """

    try:
        from copilot_schema_validation import create_schema_provider  # type: ignore[import-not-found]

        return create_schema_provider(schema_type="documents")
    except ImportError as e:
        raise ImportError(
            "Schema validation requested but copilot_schema_validation is not installed. "
            "Install with: pip install copilot-storage[validation]"
        ) from e


def create_document_store(
    config: AdapterConfig_DocumentStore,
    enable_validation: bool = True,
    strict_validation: bool = True,
    validate_reads: bool = False,
    schema_provider: Any | None = None,
) -> DocumentStore:
    """Create a document store instance.

    Args:
        config: Typed AdapterConfig_DocumentStore instance.
        enable_validation: If True (default), wraps the store in ValidatingDocumentStore.
                          Set to False only for testing or if validation is not needed.
        strict_validation: If True (default), validation errors raise exceptions.
                          If False, validation errors are logged but operations proceed.
        validate_reads: If True, validate documents on reads (get_document). Has performance impact.
        schema_provider: Optional schema provider instance for document validation. If not provided
                         and validation is enabled, one will be created automatically.

    Returns:
        DocumentStore instance.

    Raises:
        ValueError: If config is missing or doc_store_type is unknown.
    """

    base_store = create_adapter(
        config,
        adapter_name="document_store",
        get_driver_type=lambda c: c.doc_store_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "mongodb": _build_mongodb,
            "azure_cosmosdb": _build_azure_cosmosdb,
            "inmemory": _build_inmemory,
        },
    )

    if not enable_validation:
        return base_store

    provider = schema_provider or _get_schema_provider()
    return ValidatingDocumentStore(
        store=base_store,
        schema_provider=provider,
        strict=bool(strict_validation),
        validate_reads=bool(validate_reads),
    )
