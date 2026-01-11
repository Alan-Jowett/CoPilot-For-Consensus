# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Abstract archive store interface for archive storage backends."""

from abc import ABC, abstractmethod
from typing import Any

from copilot_config import DriverConfig


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


def create_archive_store(driver_name: str, driver_config: DriverConfig) -> ArchiveStore:
    """Factory function to create an archive store instance from DriverConfig.

    Args:
        driver_name: Type of archive store ("local", "mongodb", "azure_blob")
        driver_config: DriverConfig object with archive store configuration

    Returns:
        ArchiveStore instance

    Raises:
        ValueError: If driver_name is not recognized
        ValueError: If required configuration is missing

    Examples:
        >>> from copilot_config import load_service_config
        >>> config = load_service_config("parsing")
        >>> archive_adapter = config.get_adapter("archive_store")
        >>> store = create_archive_store(archive_adapter.driver_name, archive_adapter.driver_config)
    """
    if not driver_name:
        raise ValueError("driver_name is required for create_archive_store (choose: 'local', 'mongodb', 'azure_blob')")

    if driver_name == "local":
        from .local_volume_archive_store import LocalVolumeArchiveStore
        return LocalVolumeArchiveStore.from_config(driver_config)
    elif driver_name == "mongodb":
        from .mongodb_archive_store import MongoDBArchiveStore
        return MongoDBArchiveStore.from_config(driver_config)
    elif driver_name == "azure_blob":
        from .azure_blob_archive_store import AzureBlobArchiveStore
        return AzureBlobArchiveStore.from_config(driver_config)
    elif driver_name == "s3":
        # Future implementation
        raise NotImplementedError("S3 backend not yet implemented")
    else:
        raise ValueError(f"Unknown archive store driver: {driver_name}")
