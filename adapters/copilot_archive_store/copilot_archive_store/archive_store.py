# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract archive store interface for archive storage backends."""

from abc import ABC, abstractmethod
from typing import Any

from copilot_config.adapter_factory import create_adapter
from copilot_config.generated.adapters.archive_store import AdapterConfig_ArchiveStore


class ArchiveStoreError(Exception):
    """Base exception for archive store errors."""
    pass


class ArchiveStoreNotConnectedError(ArchiveStoreError):
    """Exception raised when attempting operations on a disconnected store."""
    pass


class ArchiveStoreConnectionError(ArchiveStoreError):
    """Exception raised when connection to the archive store fails."""
    pass


class ArchiveNotFoundError(ArchiveStoreError):
    """Exception raised when an archive is not found."""
    pass


class ArchiveStore(ABC):
    """Abstract interface for archive storage backends.

    This interface abstracts the storage mechanism for mailbox archives,
    allowing deployment-time selection of the backend (local volume, MongoDB,
    cloud storage, etc.).
    """

    @abstractmethod
    def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive content and return unique archive identifier.

        Args:
            source_name: Name of the source (e.g., 'ietf-wg-abc')
            file_path: Original file path or name
            content: Raw archive content as bytes

        Returns:
            Unique archive identifier (can be content hash, UUID, etc.)

        Raises:
            ArchiveStoreError: If storage operation fails
        """
        pass

    @abstractmethod
    def get_archive(self, archive_id: str) -> bytes | None:
        """Retrieve archive content by ID.

        Args:
            archive_id: Unique archive identifier

        Returns:
            Archive content as bytes, or None if not found

        Raises:
            ArchiveStoreError: If retrieval operation fails
        """
        pass

    @abstractmethod
    def get_archive_by_hash(self, content_hash: str) -> str | None:
        """Retrieve archive ID by content hash for deduplication.

        This method enables content-addressable storage and deduplication.
        If an archive with the given content hash exists, returns its ID.

        Args:
            content_hash: SHA256 hash of the archive content

        Returns:
            Archive ID if found, None otherwise

        Raises:
            ArchiveStoreError: If query operation fails
        """
        pass

    @abstractmethod
    def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive exists, False otherwise

        Raises:
            ArchiveStoreError: If check operation fails
        """
        pass

    @abstractmethod
    def delete_archive(self, archive_id: str) -> bool:
        """Delete archive by ID.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive was deleted, False if not found

        Raises:
            ArchiveStoreError: If deletion operation fails
        """
        pass

    @abstractmethod
    def list_archives(self, source_name: str) -> list[dict[str, Any]]:
        """List all archives for a given source.

        Args:
            source_name: Name of the source (e.g., 'ietf-wg-abc')

        Returns:
            List of archive metadata dictionaries, each containing:
                - archive_id: str
                - source_name: str
                - file_path: str
                - content_hash: str
                - size_bytes: int
                - stored_at: str (ISO 8601 timestamp)

        Raises:
            ArchiveStoreError: If list operation fails
        """
        pass


def create_archive_store(config: AdapterConfig_ArchiveStore) -> ArchiveStore:
    """Factory function to create an archive store instance from typed config.

    Args:
        config: Typed adapter configuration for archive_store.

    Returns:
        ArchiveStore instance

    Raises:
        ValueError: If config is missing or archive_store_type is not recognized
    """
    from .azure_blob_archive_store import AzureBlobArchiveStore
    from .local_volume_archive_store import LocalVolumeArchiveStore

    return create_adapter(
        config,
        adapter_name="archive_store",
        get_driver_type=lambda c: c.archive_store_type,
        get_driver_config=lambda c: c.driver,
        drivers={
            "local": LocalVolumeArchiveStore.from_config,
            "azureblob": AzureBlobArchiveStore.from_config,
        },
    )
