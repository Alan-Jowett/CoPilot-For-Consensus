# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Local volume-based archive store implementation."""

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .archive_store import (
    ArchiveStore,
    ArchiveStoreError,
)


class LocalVolumeArchiveStore(ArchiveStore):
    """Local filesystem-based archive storage.

    This implementation maintains the current behavior of storing archives
    in a local directory structure: {base_path}/{source_name}/{filename}

    Metadata is stored in a separate JSON file for efficient querying.
    """

    def __init__(self, base_path: str = None):
        """Initialize local volume archive store.

        Args:
            base_path: Base directory for archive storage.
                      Defaults to ARCHIVE_STORE_PATH env var or "/data/raw_archives"
        """
        if base_path is None:
            base_path = os.getenv("ARCHIVE_STORE_PATH", "/data/raw_archives")

        self.base_path = Path(base_path)
        self.metadata_path = self.base_path / "metadata" / "archives.json"

        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # Load metadata index
        self._metadata: dict[str, dict[str, Any]] = {}
        self._load_metadata()

    def _load_metadata(self) -> None:
        """Load metadata index from disk."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path) as f:
                    self._metadata = json.load(f)
            except Exception as e:
                # Start with empty metadata if load fails
                self._metadata = {}
                # Log warning but don't fail initialization
                import logging
                logging.warning(f"Failed to load archive metadata: {e}")

    def _save_metadata(self) -> None:
        """Save metadata index to disk."""
        try:
            with open(self.metadata_path, "w") as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            raise ArchiveStoreError(f"Failed to save metadata: {e}")

    def _calculate_hash(self, content: bytes) -> str:
        """Calculate SHA256 hash of content."""
        return hashlib.sha256(content).hexdigest()

    def store_archive(self, source_name: str, file_path: str, content: bytes) -> str:
        """Store archive content in local filesystem.

        Args:
            source_name: Name of the source
            file_path: Original file path or name
            content: Raw archive content

        Returns:
            Archive ID (first 16 chars of content hash)
        """
        try:
            # Calculate content hash for deduplication and ID generation
            content_hash = self._calculate_hash(content)
            archive_id = content_hash[:16]

            # Create source directory
            source_dir = self.base_path / source_name
            source_dir.mkdir(parents=True, exist_ok=True)

            # Extract filename from file_path
            filename = Path(file_path).name

            # Store file on disk
            target_path = source_dir / filename
            with open(target_path, "wb") as f:
                f.write(content)

            # Update metadata
            self._metadata[archive_id] = {
                "archive_id": archive_id,
                "source_name": source_name,
                "file_path": str(target_path),
                "original_path": file_path,
                "content_hash": content_hash,
                "size_bytes": len(content),
                "stored_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }
            self._save_metadata()

            return archive_id

        except Exception as e:
            raise ArchiveStoreError(f"Failed to store archive: {e}")

    def get_archive(self, archive_id: str) -> bytes | None:
        """Retrieve archive content from local filesystem.

        Args:
            archive_id: Unique archive identifier

        Returns:
            Archive content as bytes, or None if not found
        """
        try:
            metadata = self._metadata.get(archive_id)
            if not metadata:
                return None

            file_path = Path(metadata["file_path"])
            if not file_path.exists():
                # Metadata exists but file is missing
                return None

            with open(file_path, "rb") as f:
                return f.read()

        except Exception as e:
            raise ArchiveStoreError(f"Failed to retrieve archive: {e}")

    def get_archive_by_hash(self, content_hash: str) -> str | None:
        """Retrieve archive ID by content hash.

        Args:
            content_hash: SHA256 hash of the archive content

        Returns:
            Archive ID if found, None otherwise
        """
        for archive_id, metadata in self._metadata.items():
            if metadata.get("content_hash") == content_hash:
                return archive_id
        return None

    def archive_exists(self, archive_id: str) -> bool:
        """Check if archive exists.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive exists (both metadata and file), False otherwise
        """
        metadata = self._metadata.get(archive_id)
        if not metadata:
            return False

        file_path = Path(metadata["file_path"])
        return file_path.exists()

    def delete_archive(self, archive_id: str) -> bool:
        """Delete archive from local filesystem.

        Args:
            archive_id: Unique archive identifier

        Returns:
            True if archive was deleted, False if not found
        """
        try:
            metadata = self._metadata.get(archive_id)
            if not metadata:
                return False

            # Delete file
            file_path = Path(metadata["file_path"])
            if file_path.exists():
                file_path.unlink()

            # Remove from metadata
            del self._metadata[archive_id]
            self._save_metadata()

            return True

        except Exception as e:
            raise ArchiveStoreError(f"Failed to delete archive: {e}")

    def list_archives(self, source_name: str) -> list[dict[str, Any]]:
        """List all archives for a given source.

        Args:
            source_name: Name of the source

        Returns:
            List of archive metadata dictionaries
        """
        return [
            metadata
            for metadata in self._metadata.values()
            if metadata.get("source_name") == source_name
        ]
