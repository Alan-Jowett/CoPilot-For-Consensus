# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import uuid4


@dataclass
class ArchiveIngestedEvent:
    """ArchiveIngested event payload."""
    event_type: str = "ArchiveIngested"
    event_id: str = None  # UUID
    timestamp: str = None  # ISO 8601 datetime
    version: str = "1.0"
    data: Dict[str, Any] = None  # Archive data

    def __post_init__(self):
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.data is None:
            self.data = {}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


@dataclass
class ArchiveIngestionFailedEvent:
    """ArchiveIngestionFailed event payload."""
    event_type: str = "ArchiveIngestionFailed"
    event_id: str = None  # UUID
    timestamp: str = None  # ISO 8601 datetime
    version: str = "1.0"
    data: Dict[str, Any] = None  # Failure data

    def __post_init__(self):
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat() + "Z"
        if self.data is None:
            self.data = {}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


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
