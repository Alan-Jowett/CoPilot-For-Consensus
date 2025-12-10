# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""File-based schema provider for loading schemas from the filesystem.

Used primarily in test environments where schema files are available locally.
"""

from pathlib import Path
from typing import Dict, Optional
import json
import logging

from .schema_provider import SchemaProvider

logger = logging.getLogger(__name__)


class FileSchemaProvider(SchemaProvider):
    """Schema provider that loads schemas from JSON files on disk."""

    def __init__(self, schema_dir: Optional[Path] = None):
        """Initialize the file-based schema provider.

        Args:
            schema_dir: Directory containing schema files. If None, defaults to
                       the documents/schemas/events directory in the repository.
        """
        if schema_dir is None:
            # Default to repository schema location
            sdk_dir = Path(__file__).parent.parent
            repo_root = sdk_dir.parent
            schema_dir = repo_root / "documents" / "schemas" / "events"

        self.schema_dir = Path(schema_dir)
        if not self.schema_dir.exists():
            logger.warning(f"Schema directory does not exist: {self.schema_dir}")
            self.schema_dir = None
        else:
            logger.info(f"Loading schemas from: {self.schema_dir}")

        self._schema_cache: Dict[str, Dict] = {}

    def get_schema(self, event_type: str) -> Optional[Dict]:
        """Retrieve the JSON schema for a given event type from disk.

        Args:
            event_type: The event type name (e.g., 'ArchiveIngested')

        Returns:
            The JSON schema as a dictionary, or None if not found
        """
        if self.schema_dir is None:
            logger.error("Schema directory is not available")
            return None

        # Check cache first
        if event_type in self._schema_cache:
            return self._schema_cache[event_type]

        # Try to load from file
        schema_file = self.schema_dir / f"{event_type}.schema.json"
        if not schema_file.exists():
            logger.warning(f"Schema file not found: {schema_file}")
            return None

        try:
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema = json.load(f)
            self._schema_cache[event_type] = schema
            logger.debug(f"Loaded schema for event type: {event_type}")
            return schema
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in schema file {schema_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading schema file {schema_file}: {e}")
            return None

    def list_event_types(self) -> list[str]:
        """List all available event types by scanning schema files.

        Returns:
            List of event type names
        """
        if self.schema_dir is None:
            return []

        event_types = []
        try:
            for schema_file in self.schema_dir.glob("*.schema.json"):
                # Extract event type from filename (e.g., ArchiveIngested.schema.json -> ArchiveIngested)
                event_type = schema_file.stem.replace(".schema", "")
                event_types.append(event_type)
        except Exception as e:
            logger.error(f"Error listing schema files: {e}")

        return sorted(event_types)
