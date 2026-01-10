# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""File-based schema provider for loading schemas from the filesystem.

Used primarily in test environments where schema files are available locally.
"""

import json
import logging
from pathlib import Path

from .schema_provider import SchemaProvider

logger = logging.getLogger(__name__)


def create_schema_provider(
    schema_dir: Path | str | None = None,
    schema_type: str = "events"
) -> SchemaProvider:
    """Create a schema provider instance.

    Factory function that returns a SchemaProvider implementation.
    This is the public API for obtaining schema providers.

    Args:
        schema_dir: Directory containing schema files. If None, defaults to
                   docs/schemas/{schema_type} in the repository.
        schema_type: Type of schemas to load ("events", "documents", "configs").
                    Defaults to "events". Ignored if schema_dir is provided.

    Returns:
        A SchemaProvider instance (currently FileSchemaProvider)

    Example:
        >>> provider = create_schema_provider()  # events schemas
        >>> schema = provider.get_schema("ArchiveIngested")
        >>> doc_provider = create_schema_provider(schema_type="documents")
        >>> doc_schema = doc_provider.get_schema("Message")
    """
    return FileSchemaProvider(schema_dir=schema_dir, schema_type=schema_type)


class FileSchemaProvider(SchemaProvider):
    """Schema provider that loads schemas from JSON files on disk."""

    def __init__(
        self,
        schema_dir: Path | str | None = None,
        schema_type: str = "events"
    ):
        """Initialize the file-based schema provider.

        Args:
            schema_dir: Directory containing schema files. If None, defaults to
                       docs/schemas/{schema_type} in the repository.
            schema_type: Type of schemas to load ("events", "documents", "configs").
                        Defaults to "events". Ignored if schema_dir is provided.
        """
        if schema_dir is None:
            # Default to repository schema location
            # Path: adapters/copilot_schema_validation/copilot_schema_validation/file_schema_provider.py
            # Go up 4 levels to reach repo root
            repo_root = Path(__file__).parent.parent.parent.parent
            schema_dir = repo_root / "docs" / "schemas" / schema_type

        self.schema_dir = Path(schema_dir)
        if not self.schema_dir.exists():
            error_msg = f"Schema directory does not exist: {self.schema_dir}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        if not self.schema_dir.is_dir():
            error_msg = f"Schema path is not a directory: {self.schema_dir}"
            logger.error(error_msg)
            raise NotADirectoryError(error_msg)

        logger.info(f"Loading schemas from: {self.schema_dir}")
        self._schema_cache: dict[str, dict] = {}

    def get_schema(self, event_type: str) -> dict | None:
        """Retrieve the JSON schema for a given event type from disk.

        Args:
            event_type: The event type name (e.g., 'ArchiveIngested')

        Returns:
            The JSON schema as a dictionary, or None if not found
        """
        # Check cache first
        if event_type in self._schema_cache:
            return self._schema_cache[event_type]

        # Try to load from file
        schema_file = self.schema_dir / f"{event_type}.schema.json"
        if not schema_file.exists():
            logger.debug(f"Schema file not found: {schema_file}")
            return None

        try:
            with open(schema_file, encoding='utf-8') as f:
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
        event_types = []
        try:
            for schema_file in self.schema_dir.glob("*.schema.json"):
                # Extract event type from filename (e.g., ArchiveIngested.schema.json -> ArchiveIngested)
                event_type = schema_file.stem.replace(".schema", "")
                event_types.append(event_type)
        except Exception as e:
            logger.error(f"Error listing schema files: {e}")

        return sorted(event_types)
