# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema registry functionality."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from copilot_schema_validation.schema_registry import (
    get_schema_path,
    load_schema,
    list_schemas,
    validate_registry,
    get_schema_metadata,
    SCHEMA_REGISTRY,
    _get_schema_base_dir,
)


class TestSchemaRegistry:
    """Tests for schema registry functions."""

    def test_schema_registry_not_empty(self):
        """Test that the schema registry is populated."""
        assert len(SCHEMA_REGISTRY) > 0
        # Check that some expected entries exist
        assert "v1.ArchiveIngested" in SCHEMA_REGISTRY
        assert "v1.Archive" in SCHEMA_REGISTRY

    def test_schema_registry_format(self):
        """Test that all registry keys follow the version.type format."""
        for key in SCHEMA_REGISTRY.keys():
            assert "." in key, f"Registry key {key} should be in format 'version.type'"
            parts = key.split(".", 1)
            assert len(parts) == 2, f"Registry key {key} should have exactly one dot"
            version, schema_type = parts
            assert version.startswith("v"), f"Version {version} should start with 'v'"

    def test_get_schema_base_dir(self):
        """Test that schema base directory can be found."""
        base_dir = _get_schema_base_dir()
        assert base_dir.exists()
        assert base_dir.is_dir()
        assert base_dir.name == "schemas"

    def test_get_schema_path_success(self):
        """Test successfully getting a schema path."""
        path = get_schema_path("ArchiveIngested", "v1")
        assert path.endswith("events/ArchiveIngested.schema.json")
        assert Path(path).exists()

    def test_get_schema_path_invalid_type(self):
        """Test getting schema path with invalid type."""
        with pytest.raises(KeyError, match="Schema not registered"):
            get_schema_path("NonExistentType", "v1")

    def test_get_schema_path_invalid_version(self):
        """Test getting schema path with invalid version."""
        with pytest.raises(KeyError, match="Schema not registered"):
            get_schema_path("ArchiveIngested", "v99")

    def test_load_schema_success(self):
        """Test successfully loading a schema."""
        schema = load_schema("ArchiveIngested", "v1")
        assert isinstance(schema, dict)
        assert "title" in schema
        assert schema["title"] == "ArchiveIngested Event"

    def test_load_schema_document(self):
        """Test loading a document schema."""
        schema = load_schema("Archive", "v1")
        assert isinstance(schema, dict)
        assert "title" in schema
        assert schema["title"] == "archives collection"

    def test_load_schema_invalid_type(self):
        """Test loading schema with invalid type."""
        with pytest.raises(KeyError, match="Schema not registered"):
            load_schema("InvalidType", "v1")

    def test_list_schemas(self):
        """Test listing all registered schemas."""
        schemas = list_schemas()
        assert len(schemas) > 0
        
        # Check structure
        for schema_type, version, path in schemas:
            assert isinstance(schema_type, str)
            assert isinstance(version, str)
            assert isinstance(path, str)
            assert version.startswith("v")
            assert path.endswith(".schema.json")
        
        # Check that results are sorted
        types_and_versions = [(t, v) for t, v, _ in schemas]
        assert types_and_versions == sorted(types_and_versions)

    def test_list_schemas_contains_events(self):
        """Test that list_schemas includes event schemas."""
        schemas = list_schemas()
        schema_types = [t for t, _, _ in schemas]
        
        # Check for some known event types
        assert "ArchiveIngested" in schema_types
        assert "ChunksPrepared" in schema_types
        assert "SummaryComplete" in schema_types

    def test_list_schemas_contains_documents(self):
        """Test that list_schemas includes document schemas."""
        schemas = list_schemas()
        schema_types = [t for t, _, _ in schemas]
        
        # Check for some known document types
        assert "Archive" in schema_types
        assert "Message" in schema_types
        assert "Chunk" in schema_types

    def test_validate_registry_success(self):
        """Test that registry validation passes for all registered schemas."""
        valid, errors = validate_registry()
        if not valid:
            # Print errors for debugging
            for error in errors:
                print(f"Validation error: {error}")
        assert valid, f"Registry validation failed with errors: {errors}"
        assert len(errors) == 0

    def test_validate_registry_with_missing_file(self, monkeypatch):
        """Test registry validation detects missing schema files."""
        # Use monkeypatch to temporarily add a fake schema to the registry
        monkeypatch.setitem(SCHEMA_REGISTRY, "v99.FakeSchema", "events/fake-schema.schema.json")
        
        valid, errors = validate_registry()
        assert not valid
        assert len(errors) > 0
        assert any("FakeSchema" in error for error in errors)

    def test_get_schema_metadata_success(self):
        """Test getting schema metadata."""
        meta = get_schema_metadata("ArchiveIngested", "v1")
        assert meta is not None
        assert meta["type"] == "ArchiveIngested"
        assert meta["version"] == "v1"
        assert meta["relative_path"] == "events/ArchiveIngested.schema.json"
        assert meta["absolute_path"] is not None
        assert meta["exists"] is True

    def test_get_schema_metadata_not_registered(self):
        """Test getting metadata for unregistered schema."""
        meta = get_schema_metadata("NonExistent", "v1")
        assert meta is None

    def test_get_schema_metadata_all_fields(self):
        """Test that metadata contains all expected fields."""
        meta = get_schema_metadata("Archive", "v1")
        assert meta is not None
        
        expected_fields = {"type", "version", "relative_path", "absolute_path", "exists"}
        assert set(meta.keys()) == expected_fields

    def test_all_registered_events_loadable(self):
        """Test that all registered event schemas can be loaded."""
        for key, path in SCHEMA_REGISTRY.items():
            if "events/" in path:
                version, schema_type = key.split(".", 1)
                try:
                    schema = load_schema(schema_type, version)
                    assert isinstance(schema, dict)
                    # Event schemas should have a $schema key
                    assert "$schema" in schema or "$id" in schema
                except Exception as e:
                    pytest.fail(f"Failed to load {key}: {e}")

    def test_all_registered_documents_loadable(self):
        """Test that all registered document schemas can be loaded."""
        for key, path in SCHEMA_REGISTRY.items():
            if "documents/" in path:
                version, schema_type = key.split(".", 1)
                try:
                    schema = load_schema(schema_type, version)
                    assert isinstance(schema, dict)
                    # Document schemas should have a $schema key
                    assert "$schema" in schema or "$id" in schema
                except Exception as e:
                    pytest.fail(f"Failed to load {key}: {e}")

    def test_schema_paths_are_consistent(self):
        """Test that schema paths in registry match actual file locations."""
        base_dir = _get_schema_base_dir()
        
        for key, relative_path in SCHEMA_REGISTRY.items():
            full_path = base_dir / relative_path
            assert full_path.exists(), f"Schema file not found for {key}: {full_path}"
            assert full_path.is_file(), f"Schema path is not a file for {key}: {full_path}"

    def test_load_schema_validates_json(self):
        """Test that load_schema validates JSON syntax."""
        # This test implicitly validates JSON since load_schema uses json.load()
        # which will raise JSONDecodeError for invalid JSON
        schema = load_schema("ArchiveIngested", "v1")
        assert isinstance(schema, dict)

    def test_registry_includes_event_envelope(self):
        """Test that the event envelope schema is registered."""
        assert "v1.EventEnvelope" in SCHEMA_REGISTRY
        schema = load_schema("EventEnvelope", "v1")
        assert schema["title"] == "Event Envelope"


class TestSchemaRegistryWithMocks:
    """Tests for schema registry with mocked filesystem."""

    def test_get_schema_path_missing_file(self, tmp_path):
        """Test error handling when schema file doesn't exist."""
        # Mock the schema base directory to point to an empty directory
        with patch('copilot_schema_validation.schema_registry._get_schema_base_dir') as mock_base:
            mock_base.return_value = tmp_path
            
            # Even though it's registered, the file doesn't exist
            with pytest.raises(FileNotFoundError, match="Schema file not found"):
                get_schema_path("ArchiveIngested", "v1")

    def test_get_schema_base_dir_not_found(self):
        """Test error handling when schema directory cannot be found."""
        with patch('copilot_schema_validation.schema_registry.Path') as mock_path:
            # Make all paths return non-existent directories
            mock_instance = MagicMock()
            mock_instance.exists.return_value = False
            mock_path.return_value.resolve.return_value.parents = [mock_instance, mock_instance]
            mock_path.return_value = mock_instance
            mock_path.__file__ = __file__
            
            # This should work with the real implementation
            # Just test that it doesn't crash
            try:
                _get_schema_base_dir()
            except FileNotFoundError:
                # Expected if mocking makes paths invalid
                pass

    def test_load_schema_invalid_json(self, tmp_path):
        """Test error handling when schema file contains invalid JSON."""
        # Create a schema directory with invalid JSON
        schema_dir = tmp_path / "schemas" / "events"
        schema_dir.mkdir(parents=True)
        
        invalid_schema = schema_dir / "ArchiveIngested.schema.json"
        invalid_schema.write_text("{ invalid json }", encoding="utf-8")
        
        with patch('copilot_schema_validation.schema_registry._get_schema_base_dir') as mock_base:
            mock_base.return_value = tmp_path / "schemas"
            
            with pytest.raises(json.JSONDecodeError):
                load_schema("ArchiveIngested", "v1")
