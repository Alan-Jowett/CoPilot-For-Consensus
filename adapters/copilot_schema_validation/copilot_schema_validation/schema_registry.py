# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Centralized schema registry for resolving versioned event and document schemas.

This module provides a centralized mapping of (type, version) pairs to their
corresponding JSON Schema file paths. This enables dynamic validation, schema
evolution, and clearer contributor documentation.

Example:
    >>> from copilot_schema_validation.schema_registry import get_schema_path, load_schema
    >>> path = get_schema_path("ArchiveIngested", "v1")
    >>> schema = load_schema("Archive", "v1")
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Module-level cache for loaded schemas
_schema_cache: Dict[str, dict] = {}

# Schema registry mapping (type, version) pairs to relative schema file paths
# All paths are relative to the repository's documents/schemas/ directory
SCHEMA_REGISTRY: Dict[str, str] = {
    # Event schemas (v1)
    "v1.ArchiveIngested": "events/ArchiveIngested.schema.json",
    "v1.ArchiveIngestionFailed": "events/ArchiveIngestionFailed.schema.json",
    "v1.JSONParsed": "events/JSONParsed.schema.json",
    "v1.ParsingFailed": "events/ParsingFailed.schema.json",
    "v1.ChunksPrepared": "events/ChunksPrepared.schema.json",
    "v1.ChunkingFailed": "events/ChunkingFailed.schema.json",
    "v1.EmbeddingsGenerated": "events/EmbeddingsGenerated.schema.json",
    "v1.EmbeddingGenerationFailed": "events/EmbeddingGenerationFailed.schema.json",
    "v1.SummarizationRequested": "events/SummarizationRequested.schema.json",
    "v1.OrchestrationFailed": "events/OrchestrationFailed.schema.json",
    "v1.SummaryComplete": "events/SummaryComplete.schema.json",
    "v1.SummarizationFailed": "events/SummarizationFailed.schema.json",
    "v1.ReportPublished": "events/ReportPublished.schema.json",
    "v1.ReportDeliveryFailed": "events/ReportDeliveryFailed.schema.json",
    "v1.EventEnvelope": "events/event-envelope.schema.json",

    # Document schemas (v1)
    "v1.Archive": "documents/archives.schema.json",
    "v1.Message": "documents/messages.schema.json",
    "v1.Thread": "documents/threads.schema.json",
    "v1.Chunk": "documents/chunks.schema.json",
    "v1.Summary": "documents/summaries.schema.json",

    # Role store schemas (v1)
    "v1.UserRoles": "role_store/user_roles.schema.json",
}


@lru_cache(maxsize=1)
def _get_schema_base_dir() -> Path:
    """Get the base directory for schema files.

    This function is cached to avoid repeated directory tree walking.

    Returns:
        Path to the documents/schemas directory in the repository.

    Raises:
        FileNotFoundError: If the schema directory cannot be found.
    """
    # Start from the current file and walk up to find the repo root
    # Look for markers like .git, README.md, or pyproject.toml
    current = Path(__file__).resolve().parent

    # Walk up the directory tree looking for the schema directory
    for _ in range(10):  # Limit search depth to avoid infinite loops
        schema_dir = current / "documents" / "schemas"
        if schema_dir.exists() and schema_dir.is_dir():
            logger.debug(f"Found schema directory at: {schema_dir}")
            return schema_dir

        # Check if we've reached the repo root by looking for common markers
        if (current / ".git").exists() or (current / "pyproject.toml").exists():
            schema_dir = current / "documents" / "schemas"
            if schema_dir.exists() and schema_dir.is_dir():
                return schema_dir

        # Move up one level
        parent = current.parent
        if parent == current:  # Reached filesystem root
            break
        current = parent

    error_msg = (
        f"Schema directory not found. Searched up from {Path(__file__).resolve().parent} "
        f"but could not find documents/schemas directory."
    )
    logger.error(error_msg)
    raise FileNotFoundError(error_msg)


def get_schema_path(schema_type: str, version: str) -> str:
    """Get the file path for a schema given its type and version.

    Args:
        schema_type: The schema type name (e.g., 'ArchiveIngested', 'Archive')
        version: The schema version (e.g., 'v1', 'v2')

    Returns:
        Absolute path to the schema file as a string.

    Raises:
        KeyError: If the (type, version) combination is not registered.
        FileNotFoundError: If the schema file does not exist on disk.

    Example:
        >>> path = get_schema_path("ArchiveIngested", "v1")
        >>> path.endswith("events/ArchiveIngested.schema.json")
        True
    """
    registry_key = f"{version}.{schema_type}"

    if registry_key not in SCHEMA_REGISTRY:
        available = ", ".join(sorted(SCHEMA_REGISTRY.keys()))
        raise KeyError(
            f"Schema not registered: {registry_key}. "
            f"Available schemas: {available}"
        )

    relative_path = SCHEMA_REGISTRY[registry_key]
    schema_base_dir = _get_schema_base_dir()
    full_path = schema_base_dir / relative_path

    if not full_path.exists():
        raise FileNotFoundError(
            f"Schema file not found: {full_path}. "
            f"Registry points to: {relative_path}"
        )

    return str(full_path)


def load_schema(schema_type: str, version: str) -> dict:
    """Load a JSON schema given its type and version.

    Schemas are cached after first load to avoid repeated file I/O.

    Args:
        schema_type: The schema type name (e.g., 'ArchiveIngested', 'Archive')
        version: The schema version (e.g., 'v1', 'v2')

    Returns:
        The loaded JSON schema as a dictionary.

    Raises:
        KeyError: If the (type, version) combination is not registered.
        FileNotFoundError: If the schema file does not exist on disk.
        json.JSONDecodeError: If the schema file contains invalid JSON.

    Example:
        >>> schema = load_schema("ArchiveIngested", "v1")
        >>> schema["title"]
        'ArchiveIngested Event'
    """
    # Check cache first
    cache_key = f"{version}.{schema_type}"
    if cache_key in _schema_cache:
        logger.debug(f"Returning cached schema: {schema_type} {version}")
        return _schema_cache[cache_key]

    schema_path = get_schema_path(schema_type, version)

    try:
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)

        # Cache the loaded schema
        _schema_cache[cache_key] = schema
        logger.debug(f"Loaded schema: {schema_type} {version} from {schema_path}")
        return schema
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in schema file {schema_path}: {e}")
        raise
    except Exception as e:
        logger.error(f"Error loading schema file {schema_path}: {e}")
        raise


def list_schemas() -> List[Tuple[str, str, str]]:
    """List all registered schemas.

    Returns:
        List of tuples containing (type, version, relative_path) for each
        registered schema, sorted by type then version.

    Example:
        >>> schemas = list_schemas()
        >>> len(schemas) > 0
        True
        >>> schemas[0]  # doctest: +SKIP
        ('Archive', 'v1', 'documents/archives.schema.json')
    """
    result = []
    for key, path in SCHEMA_REGISTRY.items():
        # Split the key into version and type
        version, schema_type = key.split(".", 1)
        result.append((schema_type, version, path))

    # Sort by type, then version
    return sorted(result, key=lambda x: (x[0], x[1]))


def validate_registry() -> Tuple[bool, List[str]]:
    """Validate that all registered schemas exist on disk.

    Returns:
        Tuple of (all_valid, errors) where all_valid is True if all schemas
        exist, and errors is a list of error messages for missing schemas.

    Example:
        >>> valid, errors = validate_registry()
        >>> valid
        True
        >>> errors
        []
    """
    errors = []
    schema_base_dir = _get_schema_base_dir()

    for registry_key, relative_path in SCHEMA_REGISTRY.items():
        full_path = schema_base_dir / relative_path
        if not full_path.exists():
            errors.append(
                f"Missing schema file for {registry_key}: {relative_path} "
                f"(expected at {full_path})"
            )
        elif not full_path.is_file():
            errors.append(
                f"Schema path is not a file for {registry_key}: {full_path}"
            )
        else:
            # Try to load and validate JSON
            try:
                with open(full_path, 'r', encoding='utf-8') as f:
                    json.load(f)
            except json.JSONDecodeError as e:
                errors.append(
                    f"Invalid JSON in schema file for {registry_key}: {full_path} - {e}"
                )
            except Exception as e:
                errors.append(
                    f"Error reading schema file for {registry_key}: {full_path} - {e}"
                )

    return len(errors) == 0, errors


def get_schema_metadata(schema_type: str, version: str) -> Optional[Dict[str, str]]:
    """Get metadata about a registered schema without loading the full content.

    Args:
        schema_type: The schema type name
        version: The schema version

    Returns:
        Dictionary with metadata (path, exists, type, version) or None if not registered.

    Example:
        >>> meta = get_schema_metadata("ArchiveIngested", "v1")
        >>> meta['type']
        'ArchiveIngested'
        >>> meta['version']
        'v1'
    """
    registry_key = f"{version}.{schema_type}"

    if registry_key not in SCHEMA_REGISTRY:
        return None

    relative_path = SCHEMA_REGISTRY[registry_key]

    try:
        schema_base_dir = _get_schema_base_dir()
        full_path = schema_base_dir / relative_path
        exists = full_path.exists()
    except FileNotFoundError:
        exists = False
        full_path = None

    return {
        "type": schema_type,
        "version": version,
        "relative_path": relative_path,
        "absolute_path": str(full_path) if full_path else None,
        "exists": exists,
    }
