# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema registry for mapping collections to their allowed fields.

This module provides a central registry that maps collection names to their
schema-defined fields, enabling the storage layer to return clean documents
without backend-specific or unknown fields.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _find_repo_root() -> Path:
    """Determine the repository root in a robust way.

    Resolution order:
      1. Use REPO_ROOT environment variable if set.
      2. Walk up from this file looking for a marker (e.g., .git, pyproject.toml).
      3. Fall back to the historical parent.parent.parent.parent behavior.
    """
    env_root = os.environ.get("REPO_ROOT")
    if env_root:
        try:
            return Path(env_root).resolve()
        except OSError:
            logger.warning("Invalid REPO_ROOT value %r; falling back to automatic detection.", env_root)

    current = Path(__file__).resolve()
    markers = (".git", "pyproject.toml")

    for candidate in (current, *current.parents):
        for marker in markers:
            if (candidate / marker).exists():
                return candidate

    # Fallback to previous fixed-depth behavior to avoid breaking existing setups
    return current.parent.parent.parent.parent


# Default schema directory
_REPO_ROOT = _find_repo_root()
_DEFAULT_SCHEMA_DIR = _REPO_ROOT / "docs" / "schemas" / "documents"

# Global registry: collection name -> set of allowed field names
_COLLECTION_SCHEMAS: dict[str, set[str]] = {}

# Track which unknown fields have been logged (to avoid log spam)
# Uses tuple (collection, field) as key to avoid delimiter issues
_UNKNOWN_FIELDS_LOGGED: set[tuple[str, str]] = set()


def _load_schema_fields(schema_path: Path) -> set[str]:
    """Load field names from a JSON schema file.

    Args:
        schema_path: Path to the JSON schema file

    Returns:
        Set of field names defined in the schema's properties

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema file is invalid JSON
    """
    with open(schema_path, "r", encoding="utf-8") as f:
        schema = json.load(f)

    properties = schema.get("properties", {})
    return set(properties.keys())


def _initialize_registry(schema_dir: Path | None = None) -> None:
    """Initialize the schema registry by loading all schema files.

    Args:
        schema_dir: Directory containing schema files (defaults to docs/schemas/documents)
    """
    global _COLLECTION_SCHEMAS

    if schema_dir is None:
        schema_dir = _DEFAULT_SCHEMA_DIR

    if not schema_dir.exists():
        logger.warning(
            f"Schema directory not found: {schema_dir}. "
            "Document sanitization will only remove system fields."
        )
        return

    # Load schemas for known collections
    schema_files = {
        "sources": "sources.schema.json",
        "archives": "archives.schema.json",
        "messages": "messages.schema.json",
        "chunks": "chunks.schema.json",
        "threads": "threads.schema.json",
        "summaries": "summaries.schema.json",
    }

    for collection_name, filename in schema_files.items():
        schema_path = schema_dir / filename
        if schema_path.exists():
            try:
                fields = _load_schema_fields(schema_path)
                _COLLECTION_SCHEMAS[collection_name] = fields
                logger.debug(
                    f"Loaded schema for collection '{collection_name}': {len(fields)} fields"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to load schema for collection '{collection_name}' from {schema_path}: {e}"
                )
        else:
            logger.debug(f"Schema file not found for collection '{collection_name}': {schema_path}")


def reset_registry() -> None:
    """Reset the schema registry to its initial state.
    
    This function is primarily intended for testing purposes to ensure
    tests start with a clean state. It clears all loaded schemas so they
    will be reloaded on next access.
    """
    global _COLLECTION_SCHEMAS, _UNKNOWN_FIELDS_LOGGED
    _COLLECTION_SCHEMAS.clear()
    _UNKNOWN_FIELDS_LOGGED.clear()
    logger.debug("Schema registry has been reset")


def get_collection_fields(collection: str) -> set[str] | None:
    """Get the set of allowed fields for a collection.

    Args:
        collection: Name of the collection

    Returns:
        Set of allowed field names, or None if no schema is registered
    """
    global _COLLECTION_SCHEMAS

    # Lazy initialization
    if not _COLLECTION_SCHEMAS:
        _initialize_registry()

    return _COLLECTION_SCHEMAS.get(collection)


def sanitize_document(doc: dict[str, Any], collection: str, preserve_extra: bool = False) -> dict[str, Any]:
    """Remove system and unknown fields from a document.

    This function removes:
    1. Backend system fields (Cosmos: _etag, _rid, _ts, _self, _attachments)
    2. Document store metadata fields (id, collection)
    3. Unknown fields (if schema is available for the collection and preserve_extra is False)

    Args:
        doc: Document dictionary to sanitize
        collection: Name of the collection (used to determine schema)
        preserve_extra: If True, preserve fields not in schema (useful for aggregations)

    Returns:
        Sanitized document with only schema-defined fields (plus extra if preserve_extra=True)
    """
    if not doc:
        return doc

    # System fields to always remove
    system_fields = {
        "_etag",      # Cosmos DB ETag
        "_rid",       # Cosmos DB resource ID
        "_ts",        # Cosmos DB timestamp
        "_self",      # Cosmos DB self-link
        "_attachments",  # Cosmos DB attachments
        "id",         # Document store metadata (Cosmos uses this for _id)
        "collection", # Document store partition key
    }

    # Get schema fields for this collection
    allowed_fields = get_collection_fields(collection)

    sanitized: dict[str, Any] = {}
    for key, value in doc.items():
        # Always remove system fields
        if key in system_fields:
            continue

        # If schema is available and preserve_extra is False, keep only schema-defined fields
        if allowed_fields is not None and not preserve_extra:
            if key not in allowed_fields:
                # Log at warning level for first occurrence of this field in this collection
                # Use tuple for cache key to avoid delimiter collision issues
                cache_key = (collection, key)
                if cache_key not in _UNKNOWN_FIELDS_LOGGED:
                    _UNKNOWN_FIELDS_LOGGED.add(cache_key)
                    logger.warning(
                        f"Removing unknown field '{key}' from collection '{collection}' "
                        f"(not in schema). This warning will only appear once per field."
                    )
                continue

        sanitized[key] = value

    return sanitized


def sanitize_documents(docs: list[dict[str, Any]], collection: str, preserve_extra: bool = False) -> list[dict[str, Any]]:
    """Sanitize a list of documents.

    Args:
        docs: List of documents to sanitize
        collection: Name of the collection
        preserve_extra: If True, preserve fields not in schema (useful for aggregations)

    Returns:
        List of sanitized documents
    """
    return [sanitize_document(doc, collection, preserve_extra) for doc in docs]
