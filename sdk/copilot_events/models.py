# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Common event models for Copilot-for-Consensus services."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from uuid import uuid4


@dataclass
class ArchiveIngestedEvent:
    """Event published when an archive is successfully ingested.
    
    Attributes:
        event_type: Type of event (always "ArchiveIngested")
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp of event creation
        version: Event schema version
        data: Archive metadata and ingestion details
    """
    event_type: str = "ArchiveIngested"
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for event_id and timestamp."""
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


@dataclass
class ArchiveIngestionFailedEvent:
    """Event published when archive ingestion fails.
    
    Attributes:
        event_type: Type of event (always "ArchiveIngestionFailed")
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp of event creation
        version: Event schema version
        data: Failure details and error information
    """
    event_type: str = "ArchiveIngestionFailed"
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for event_id and timestamp."""
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


@dataclass
class JSONParsedEvent:
    """Event published when an archive has been successfully parsed.
    
    Attributes:
        event_type: Type of event (always "JSONParsed")
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp of event creation
        version: Event schema version
        data: Parsing results including message_count, parsed_message_ids, thread_count, etc.
    """
    event_type: str = "JSONParsed"
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for event_id and timestamp."""
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }


@dataclass
class ParsingFailedEvent:
    """Event published when archive parsing fails.
    
    Attributes:
        event_type: Type of event (always "ParsingFailed")
        event_id: Unique event identifier (UUID)
        timestamp: ISO 8601 timestamp of event creation
        version: Event schema version
        data: Failure details including archive_id, file_path, error information
    """
    event_type: str = "ParsingFailed"
    event_id: Optional[str] = None
    timestamp: Optional[str] = None
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Generate default values for event_id and timestamp."""
        if self.event_id is None:
            self.event_id = str(uuid4())
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.
        
        Returns:
            Dictionary representation of the event
        """
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "version": self.version,
            "data": self.data,
        }
