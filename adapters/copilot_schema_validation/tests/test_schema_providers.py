# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema provider implementations."""

import json
import logging
import pytest

from copilot_schema_validation.file_schema_provider import FileSchemaProvider


class TestFileSchemaProvider:
    """Tests for FileSchemaProvider."""

    def test_default_schema_dir(self):
        """Test that default schema directory is set correctly."""
        provider = FileSchemaProvider()
        # Should default to documents/schemas/events relative to repo root
        assert provider.schema_dir is not None
        assert "events" in str(provider.schema_dir)

    def test_custom_schema_dir(self, tmp_path):
        """Test initialization with custom schema directory."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        provider = FileSchemaProvider(schema_dir)
        assert provider.schema_dir == schema_dir

    def test_nonexistent_schema_dir(self, tmp_path):
        """Test initialization with nonexistent directory."""
        schema_dir = tmp_path / "nonexistent"
        provider = FileSchemaProvider(schema_dir)
        assert provider.schema_dir is None

    def test_get_schema_success(self, tmp_path):
        """Test successfully loading a schema."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        # Create a test schema file
        test_schema = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "event_type": {"const": "TestEvent"}
            }
        }
        schema_file = schema_dir / "TestEvent.schema.json"
        schema_file.write_text(json.dumps(test_schema), encoding="utf-8")

        provider = FileSchemaProvider(schema_dir)
        schema = provider.get_schema("TestEvent")

        assert schema is not None
        assert schema["type"] == "object"
        assert schema["properties"]["event_type"]["const"] == "TestEvent"

    def test_get_schema_caching(self, tmp_path):
        """Test that schemas are cached after first load."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        test_schema = {"type": "object"}
        schema_file = schema_dir / "TestEvent.schema.json"
        schema_file.write_text(json.dumps(test_schema), encoding="utf-8")

        provider = FileSchemaProvider(schema_dir)
        
        # Load schema twice
        schema1 = provider.get_schema("TestEvent")
        schema2 = provider.get_schema("TestEvent")

        # Should return the same cached instance
        assert schema1 is schema2
        assert "TestEvent" in provider._schema_cache

    def test_get_schema_not_found(self, tmp_path):
        """Test retrieving a non-existent schema."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        provider = FileSchemaProvider(schema_dir)
        schema = provider.get_schema("NonExistentEvent")

        assert schema is None

    def test_get_schema_invalid_json(self, tmp_path):
        """Test loading a schema with invalid JSON."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        schema_file = schema_dir / "InvalidEvent.schema.json"
        schema_file.write_text("{ invalid json }", encoding="utf-8")

        provider = FileSchemaProvider(schema_dir)
        schema = provider.get_schema("InvalidEvent")

        assert schema is None

    def test_list_event_types(self, tmp_path):
        """Test listing all available event types."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        # Create multiple schema files
        (schema_dir / "EventA.schema.json").write_text("{}", encoding="utf-8")
        (schema_dir / "EventB.schema.json").write_text("{}", encoding="utf-8")
        (schema_dir / "EventC.schema.json").write_text("{}", encoding="utf-8")

        provider = FileSchemaProvider(schema_dir)
        event_types = provider.list_event_types()

        assert len(event_types) == 3
        assert "EventA" in event_types
        assert "EventB" in event_types
        assert "EventC" in event_types
        assert event_types == sorted(event_types)  # Should be sorted

    def test_list_event_types_empty_dir(self, tmp_path):
        """Test listing event types from empty directory."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        provider = FileSchemaProvider(schema_dir)
        event_types = provider.list_event_types()

        assert event_types == []

    def test_list_event_types_no_schema_dir(self, tmp_path):
        """Test listing event types when schema directory doesn't exist."""
        schema_dir = tmp_path / "nonexistent"
        provider = FileSchemaProvider(schema_dir)
        event_types = provider.list_event_types()

        assert event_types == []


class TestDocumentStoreSchemaProvider:
    """Tests for DocumentStoreSchemaProvider - REMOVED.
    
    DocumentStoreSchemaProvider and its dependency on copilot_storage have been removed
    to break the circular dependency between copilot_schema_validation and copilot_storage.
    The application now uses only FileSchemaProvider to load schemas from the file system.
    """
    pass

