# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Exceptions for ingestion service operations."""


class IngestionError(Exception):
    """Base exception for ingestion service errors."""

    pass


class SourceConfigurationError(IngestionError):
    """Raised when source configuration is invalid or missing required fields."""

    pass


class FetchError(IngestionError):
    """Raised when fetching archives from a source fails."""

    def __init__(self, message: str, source_name: str | None = None, retry_count: int = 0):
        """Initialize FetchError with context.

        Args:
            message: Error message
            source_name: Name of the source that failed (optional)
            retry_count: Number of retries attempted (optional)
        """
        super().__init__(message)
        self.source_name = source_name
        self.retry_count = retry_count


class ChecksumPersistenceError(IngestionError):
    """Raised when checksum metadata cannot be saved."""

    pass


class ArchivePublishError(IngestionError):
    """Raised when publishing archive events fails."""

    def __init__(self, message: str, archive_id: str | None = None):
        """Initialize ArchivePublishError with context.

        Args:
            message: Error message
            archive_id: Archive ID that failed to publish (optional)
        """
        super().__init__(message)
        self.archive_id = archive_id
