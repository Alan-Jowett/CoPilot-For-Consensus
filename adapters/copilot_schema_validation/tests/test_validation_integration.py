# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for validation integration."""

from pathlib import Path

from copilot_schema_validation import FileSchemaProvider, validate_json


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
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"}
            },
            "required": ["id", "name"]
        }
        
        import json
        (schema_dir / "TestEvent.schema.json").write_text(json.dumps(schema))
        
        provider = FileSchemaProvider(schema_dir=schema_dir)
        loaded_schema = provider.get_schema("TestEvent")
        
        # Valid document
        valid_doc = {"id": "123", "name": "Test"}
        is_valid, errors = validate_json(valid_doc, loaded_schema, schema_provider=provider)
        assert is_valid
        
        # Invalid document
        invalid_doc = {"id": "123"}
        is_valid, errors = validate_json(invalid_doc, loaded_schema, schema_provider=provider)
        assert not is_valid

