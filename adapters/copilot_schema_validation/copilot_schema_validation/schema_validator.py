# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Utilities for validating JSON documents against JSON Schemas."""

import copy
import json
import logging
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

logger = logging.getLogger(__name__)


def _build_registry() -> Registry:
    """Build a referencing Registry with preloaded schemas.

    The event envelope schema is loaded from the filesystem only, not from
    arbitrary schema providers. This prevents inappropriate lookups when
    validating documents (which don't use event envelopes).

    Returns:
        Registry with preloaded schemas for $ref resolution
    """
    resources = {}
    envelope_schema = None

    # Load event envelope from filesystem
    candidate_bases = [
        Path(__file__).resolve().parents[2],  # when running from repo package folder
        Path(__file__).resolve().parents[3],  # repo root (common during editable installs)
    ]

    for base in candidate_bases:
        envelope_path = base / "docs" / "schemas" / "events" / "event-envelope.schema.json"
        try:
            if envelope_path.exists():
                envelope_schema = json.loads(envelope_path.read_text(encoding="utf-8"))
                logger.debug(f"Loaded event-envelope schema from filesystem: {envelope_path}")
                break
        except Exception as exc:
            logger.debug(f"Could not load envelope schema from {envelope_path} (will try next candidate): {exc}")

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


def _strip_allof_additional_properties(schema: dict[str, Any]) -> dict[str, Any]:
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


def validate_json(document: dict[str, Any], schema: dict[str, Any], schema_provider=None) -> tuple[bool, list[str]]:
    """Validate a JSON document against a JSON schema.

    Args:
        document: The JSON document to validate.
        schema: The JSON schema to validate against.
        schema_provider: Deprecated parameter (ignored). Event envelope is always loaded
                        from filesystem. This parameter will be removed in a future version.
                        Callers should remove this argument from their validate_json() calls.

    Returns:
        Tuple of (is_valid, errors). is_valid is True when the document conforms
        to the schema. errors is a list of human-readable validation errors (empty if valid).
    """
    del schema_provider
    try:
        normalized_schema = _strip_allof_additional_properties(schema)
        registry = _build_registry()
        validator = Draft202012Validator(normalized_schema, registry=registry)
        errors = sorted(validator.iter_errors(document), key=lambda e: e.path)
        if not errors:
            return True, []

        messages: list[str] = []
        for err in errors:
            path = ".".join([str(p) for p in err.absolute_path])
            location = f" at '{path}'" if path else ""
            messages.append(f"{err.message}{location}")
        return False, messages
    except Exception as exc:  # Fallback for malformed schemas or unexpected issues
        logger.error(f"Schema validation failed due to an internal error: {exc}")
        return False, [str(exc)]
