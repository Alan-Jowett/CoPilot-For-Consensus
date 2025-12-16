# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""MongoDB GridFS-based archive store implementation (stub)."""

from typing import Optional, List, Dict, Any

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

    async def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive content (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    async def get_archive(self, archive_id: str) -> Optional[bytes]:
        """Retrieve archive content (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    async def get_archive_by_hash(self, content_hash: str) -> Optional[str]:
        """Retrieve archive ID by hash (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    async def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    async def delete_archive(self, archive_id: str) -> bool:
        """Delete archive (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")

    async def list_archives(self, source_name: str) -> List[Dict[str, Any]]:
        """List archives for a source (not implemented)."""
        raise NotImplementedError("MongoDB backend not yet implemented")
