# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Archive Store Adapter.

A shared library for archive storage across microservices
in the Copilot-for-Consensus system.

This adapter enables deployment-time selection of archive storage backends,
supporting local volumes, MongoDB GridFS, cloud storage (Azure Blob, S3), etc.
"""

__version__ = "0.1.0"

from .archive_store import (
    ArchiveStore,
    ArchiveStoreError,
    ArchiveStoreNotConnectedError,
    ArchiveStoreConnectionError,
    ArchiveNotFoundError,
    create_archive_store,
)
from .local_volume_archive_store import LocalVolumeArchiveStore
from .accessor import ArchiveAccessor, create_archive_accessor

__all__ = [
    # Version
    "__version__",
    # Archive Stores
    "ArchiveStore",
    "LocalVolumeArchiveStore",
    "create_archive_store",
    # Accessor Helper
    "ArchiveAccessor",
    "create_archive_accessor",
    # Exceptions
    "ArchiveStoreError",
    "ArchiveStoreNotConnectedError",
    "ArchiveStoreConnectionError",
    "ArchiveNotFoundError",
]
