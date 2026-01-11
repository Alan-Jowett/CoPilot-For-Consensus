# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Archive Store Adapter.

A shared library for archive storage across microservices
in the Copilot-for-Consensus system.

This adapter enables deployment-time selection of archive storage backends,
supporting local volumes, MongoDB GridFS, cloud storage (Azure Blob, S3), etc.

Minimal exports - services should only use create_archive_store():

    from copilot_config import load_service_config
    from copilot_archive_store import create_archive_store

    config = load_service_config("parsing")
    archive_adapter = config.get_adapter("archive_store")
    store = create_archive_store(archive_adapter.driver_name, archive_adapter.driver_config)
"""

__version__ = "0.1.0"

from .archive_store import (
    ArchiveNotFoundError,
    ArchiveStore,
    ArchiveStoreConnectionError,
    ArchiveStoreError,
    ArchiveStoreNotConnectedError,
    create_archive_store,
)

__all__ = [
    # Factory function (all services should use this)
    "create_archive_store",
    # Base class (for type hints)
    "ArchiveStore",
    # Exceptions (for error handling)
    "ArchiveStoreError",
    "ArchiveStoreNotConnectedError",
    "ArchiveStoreConnectionError",
    "ArchiveNotFoundError",
]

