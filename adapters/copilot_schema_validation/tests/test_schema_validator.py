# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema validation utility."""

from copilot_schema_validation.schema_validator import validate_json


def test_validate_json_success():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0},
        },
        "required": ["name", "age"],
        "additionalProperties": False,
    }

    doc = {"name": "Alice", "age": 30}
    valid, errors = validate_json(doc, schema)

    assert valid is True
    assert errors == []


def test_validate_json_failure():
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0},
        },
        "required": ["name", "age"],
        "additionalProperties": False,
    }

    doc = {"name": 123, "age": -5, "extra": True}
    valid, errors = validate_json(doc, schema)

    assert valid is False
    # Ensure we surface multiple violations
    assert any("name" in err for err in errors)
    assert any("age" in err for err in errors)
    assert any("additional properties" in err.lower() for err in errors)


def test_validate_json_malformed_schema():
    # Malformed schema should not raise, but return False with an error message
    schema = {"type": "object", "properties": {"name": {"type": "unknown-type"}}}
    doc = {"name": "Bob"}
    valid, errors = validate_json(doc, schema)

    assert valid is False
    assert len(errors) > 0

