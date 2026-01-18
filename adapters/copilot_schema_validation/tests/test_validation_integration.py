# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for validation integration."""

import json
from unittest.mock import Mock

from copilot_schema_validation import create_schema_provider, validate_json


class TestValidationIntegration:
    """Integration tests for schema validation with providers."""

    def test_validate_with_file_schema_provider(self, tmp_path):
        """Test validation with file schema provider."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        # Create a schema
        schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"id": {"type": "string"}, "name": {"type": "string"}},
            "required": ["id", "name"],
        }

        (schema_dir / "TestEvent.schema.json").write_text(json.dumps(schema))

        provider = create_schema_provider(schema_dir=schema_dir)
        loaded_schema = provider.get_schema("TestEvent")

        # Valid document
        valid_doc = {"id": "123", "name": "Test"}
        is_valid, errors = validate_json(valid_doc, loaded_schema, schema_provider=provider)
        assert is_valid

        # Invalid document
        invalid_doc = {"id": "123"}
        is_valid, errors = validate_json(invalid_doc, loaded_schema, schema_provider=provider)
        assert not is_valid

    def test_event_envelope_not_requested_from_schema_provider(self):
        """Test that event-envelope is not requested from arbitrary schema providers.

        This verifies the fix for the issue where document schema providers
        (pointing to docs/schemas/documents/) were being asked for
        event-envelope.schema.json, which only exists in docs/schemas/events/.

        The event envelope should only be loaded from the filesystem, not from
        the schema_provider parameter passed to validate_json().
        """
        # Create a mock schema provider that tracks get_schema calls
        mock_provider = Mock()
        mock_provider.get_schema = Mock(return_value=None)

        # Create a simple document schema (not using event envelope)
        doc_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {"archive_id": {"type": "string"}, "status": {"type": "string"}},
            "required": ["archive_id", "status"],
        }

        # Validate a document
        doc = {"archive_id": "test123", "status": "pending"}
        is_valid, errors = validate_json(doc, doc_schema, schema_provider=mock_provider)

        # Validation should succeed
        assert is_valid
        assert errors == []

        # The schema provider should NOT have been called at all
        # (event-envelope should only be loaded from filesystem)
        mock_provider.get_schema.assert_not_called()
