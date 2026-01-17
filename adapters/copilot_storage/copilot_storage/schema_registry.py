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

# Default schema directory
# Try to find repository root via environment variable or relative path
_REPO_ROOT = Path(os.environ.get("REPO_ROOT", Path(__file__).parent.parent.parent.parent))
_DEFAULT_SCHEMA_DIR = _REPO_ROOT / "docs" / "schemas" / "documents"

# Global registry: collection name -> set of allowed field names
_COLLECTION_SCHEMAS: dict[str, set[str]] = {}


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
                logger.debug(
                    f"Removing unknown field '{key}' from collection '{collection}' "
                    f"(not in schema)"
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
