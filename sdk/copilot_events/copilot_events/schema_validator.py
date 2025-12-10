# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Utilities for validating JSON documents against JSON Schemas."""

from typing import Any, Dict, List, Tuple
import copy
import json
import logging
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

logger = logging.getLogger(__name__)


# Small helper to preload shared schemas (e.g., event envelope) so $ref resolution
# works even when schemas are stored outside the local filesystem (like MongoDB).
# Falls back silently if the supporting schema file is not present.
def _build_registry(schema_provider=None) -> Registry:
    """Build a referencing Registry with preloaded schemas.
    
    Args:
        schema_provider: Optional SchemaProvider to use for loading envelope schema
        
    Returns:
        Registry with preloaded schemas for $ref resolution
    """
    resources = {}
    envelope_schema = None
    
    # Try to load from schema provider first (e.g., MongoDB)
    if schema_provider is not None:
        try:
            envelope_schema = schema_provider.get_schema("event-envelope")
            if envelope_schema:
                logger.debug("Loaded event-envelope schema from schema provider")
        except Exception as exc:
            logger.debug(f"Could not load envelope from schema provider: {exc}")
    
    # Fallback to filesystem if not found in provider
    if envelope_schema is None:
        try:
            envelope_path = Path(__file__).resolve().parents[2] / "documents" / "schemas" / "event-envelope.schema.json"
            if envelope_path.exists():
                envelope_schema = json.loads(envelope_path.read_text(encoding="utf-8"))
                logger.debug("Loaded event-envelope schema from filesystem")
        except Exception as exc:
            logger.debug(f"Unable to preload envelope schema from filesystem: {exc}")
    
    # Register the envelope schema if found
    if envelope_schema:
        resource = Resource.from_contents(envelope_schema)
        
        # Register by $id if present
        schema_id = envelope_schema.get("$id")
        if schema_id:
            resources[schema_id] = resource
        
        # Also register under the relative path used in references
        resources["../event-envelope.schema.json"] = resource
        resources["event-envelope.schema.json"] = resource
    
    # Build the registry with all preloaded resources
    return Registry().with_resources(resources.items())


def _strip_allof_additional_properties(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Relax additionalProperties inside allOf blocks to avoid double-rejection.

    Event schemas extend a shared envelope via allOf. Without removing
    additionalProperties in the extended subschemas, envelope fields (e.g.,
    event_id) are incorrectly treated as unexpected. We prune those keys only
    within the top-level allOf entries to preserve most validation behavior
    while keeping the envelope extension usable.
    """
    if not isinstance(schema, dict) or "allOf" not in schema:
        return schema

    normalized = copy.deepcopy(schema)
    all_of = normalized.get("allOf")
    if isinstance(all_of, list):
        stripped = []
        for subschema in all_of:
            if isinstance(subschema, dict):
                cleaned = copy.deepcopy(subschema)
                cleaned.pop("additionalProperties", None)
                stripped.append(cleaned)
            else:
                stripped.append(subschema)
        normalized["allOf"] = stripped
    return normalized


def validate_json(document: Dict[str, Any], schema: Dict[str, Any], schema_provider=None) -> Tuple[bool, List[str]]:
    """Validate a JSON document against a JSON schema.

    Args:
        document: The JSON document to validate.
        schema: The JSON schema to validate against.
        schema_provider: Optional SchemaProvider for resolving schema references (e.g., event-envelope)

    Returns:
        Tuple of (is_valid, errors). is_valid is True when the document conforms
        to the schema. errors is a list of human-readable validation errors (empty if valid).
    """
    try:
        normalized_schema = _strip_allof_additional_properties(schema)
        registry = _build_registry(schema_provider)
        validator = Draft202012Validator(normalized_schema, registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda e: e.path)
        if not errors:
            return True, []

        messages: List[str] = []
        for err in errors:
            path = ".".join([str(p) for p in err.absolute_path])
            location = f" at '{path}'" if path else ""
            messages.append(f"{err.message}{location}")
        return False, messages
    except Exception as exc:  # Fallback for malformed schemas or unexpected issues
        logger.error(f"Schema validation failed due to an internal error: {exc}")
        return False, [str(exc)]
