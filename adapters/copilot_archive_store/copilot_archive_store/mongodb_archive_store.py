# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""MongoDB GridFS-based archive store implementation (stub)."""

from typing import Any

from copilot_config import DriverConfig

from .archive_store import ArchiveStore


class MongoDBArchiveStore(ArchiveStore):
    """MongoDB GridFS-based archive storage (planned implementation).

    This will store archives using MongoDB GridFS for files larger than 16MB,
    and regular collections for smaller files. Enables multi-node deployments
    without shared volumes.

    Note: This is a stub implementation. Full implementation is planned.
    """

    def __init__(self, **kwargs):
        """Initialize MongoDB archive store."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    @classmethod
    def from_config(cls, driver_config: DriverConfig) -> "MongoDBArchiveStore":
        """Create MongoDBArchiveStore from DriverConfig.

        Args:
            driver_config: DriverConfig object containing MongoDB configuration
                          Expected keys: host, port, database, collection, etc.

        Returns:
            MongoDBArchiveStore instance

        Raises:
            NotImplementedError: MongoDB backend not yet implemented
        """
        raise NotImplementedError("MongoDB backend not yet implemented")

    def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive content (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    def get_archive(self, archive_id: str) -> bytes | None:
        """Retrieve archive content (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    def get_archive_by_hash(self, content_hash: str) -> str | None:
        """Retrieve archive ID by hash (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    def delete_archive(self, archive_id: str) -> bool:
        """Delete archive (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    def list_archives(self, source_name: str) -> list[dict[str, Any]]:
        """List archives for a source (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")
