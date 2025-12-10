# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema provider abstraction for event validation.

Provides abstract base class and implementations for loading event schemas
from different sources (files, MongoDB).
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional

class SchemaProvider(ABC):
    """Abstract base class for schema providers."""

    @abstractmethod
    def get_schema(self, event_type: str) -> Optional[Dict]:
        """Retrieve the JSON schema for a given event type.

        Args:
            event_type: The event type name (e.g., 'ArchiveIngested')

        Returns:
            The JSON schema as a dictionary, or None if not found
        """
        pass

    @abstractmethod
    def list_event_types(self) -> list[str]:
        """List all available event types.

        Returns:
            List of event type names
        """
        pass
