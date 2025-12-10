# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Ingestion-specific data models.

Note: Event models (ArchiveIngestedEvent, ArchiveIngestionFailedEvent) 
have been moved to the shared copilot_events SDK.
"""

from dataclasses import dataclass


@dataclass
class ArchiveMetadata:
    """Metadata for an ingested archive."""
    archive_id: str
    source_name: str
    source_type: str
    source_url: str
    file_path: str
    file_size_bytes: int
    file_hash_sha256: str
    ingestion_started_at: str
    ingestion_completed_at: str
    status: str = "success"  # "success" or "failed"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "archive_id": self.archive_id,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "source_url": self.source_url,
            "file_path": self.file_path,
            "file_size_bytes": self.file_size_bytes,
            "file_hash_sha256": self.file_hash_sha256,
            "ingestion_started_at": self.ingestion_started_at,
            "ingestion_completed_at": self.ingestion_completed_at,
            "status": self.status,
        }
