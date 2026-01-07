# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Helper utilities for integrating ArchiveStore with existing services.

This module provides backward-compatible wrappers that allow services to
adopt the ArchiveStore pattern incrementally without breaking existing
functionality.
"""

from pathlib import Path

from .archive_store import ArchiveStore, create_archive_store


class ArchiveAccessor:
    """Helper class for backward-compatible archive access.

    This class provides methods that work with both the old file-path-based
    approach and the new archive-store-based approach. It attempts to use
    the archive store first, then falls back to direct file access.

    Example:
        >>> accessor = ArchiveAccessor()
        >>> # Try archive store first, fall back to file path
        >>> content = accessor.get_archive_content(
        ...     archive_id="abc123",
        ...     fallback_file_path="/data/raw_archives/source/file.mbox"
        ... )
    """

    def __init__(self, archive_store: ArchiveStore | None = None, enable_fallback: bool = True):
        """Initialize archive accessor.

        Args:
            archive_store: Optional ArchiveStore instance. If None, archive-store lookups are disabled.
            enable_fallback: If True, falls back to direct file access when archive
                           store access fails. Default True for backward compatibility.
        """
        self.enable_fallback = enable_fallback

        # Use provided archive store only; do not auto-create from environment
        self.archive_store = archive_store

    def get_archive_content(
        self,
        archive_id: str | None = None,
        fallback_file_path: str | None = None
    ) -> bytes | None:
        """Get archive content, trying archive store first then file path.

        Args:
            archive_id: Archive identifier for archive store lookup
            fallback_file_path: File path to use if archive store fails

        Returns:
            Archive content as bytes, or None if not found

        Raises:
            ArchiveStoreError: If neither method succeeds and fallback is disabled
        """
        # Try archive store if available and archive_id provided
        if self.archive_store and archive_id:
            try:
                content = self.archive_store.get_archive(archive_id)
                if content is not None:
                    return content
            except Exception:
                # Catch all exceptions, not just ArchiveStoreError
                # This makes the accessor resilient to any store errors
                if not self.enable_fallback:
                    raise

        # Fall back to direct file access if enabled
        if self.enable_fallback and fallback_file_path:
            return self._read_file(fallback_file_path)

        return None

    def check_archive_availability(
        self,
        archive_id: str | None = None,
        fallback_file_path: str | None = None
    ) -> tuple[bool, str]:
        """Check if archive is available and how it can be accessed.

        Args:
            archive_id: Archive identifier for archive store lookup
            fallback_file_path: File path to check

        Returns:
            Tuple of (available: bool, method: str) where method is one of:
            - "archive_store": Available via archive store
            - "file_path": Available via direct file access
            - "unavailable": Not found
        """
        # Try archive store first
        if self.archive_store and archive_id:
            try:
                if self.archive_store.archive_exists(archive_id):
                    return (True, "archive_store")
            except Exception:
                # Catch all exceptions for resilience
                pass

        # Try file path
        if fallback_file_path and Path(fallback_file_path).exists():
            return (True, "file_path")

        return (False, "unavailable")

    @staticmethod
    def _read_file(file_path: str) -> bytes | None:
        """Read file content from disk.

        Args:
            file_path: Path to file

        Returns:
            File content as bytes, or None if file doesn't exist
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return None
            with open(path, "rb") as f:
                return f.read()
        except Exception:
            return None


def create_archive_accessor(
    store_type: str | None = None,
    enable_fallback: bool = True,
    **kwargs
) -> ArchiveAccessor:
    """Create an ArchiveAccessor with specified configuration.

    Args:
        store_type: Type of archive store ("local", "mongodb", etc.)
        enable_fallback: Enable fallback to direct file access
        **kwargs: Additional arguments passed to archive store creation

    Returns:
        Configured ArchiveAccessor instance

    Example:
        >>> # Explicit configuration
        >>> accessor = create_archive_accessor(
        ...     store_type="local",
        ...     base_path="/data/raw_archives"
        ... )
    """
    archive_store = None
    if store_type is not None:
        # Fail fast if creation fails instead of silently disabling archive store usage
        archive_store = create_archive_store(store_type=store_type, **kwargs)

    return ArchiveAccessor(
        archive_store=archive_store,
        enable_fallback=enable_fallback
    )
