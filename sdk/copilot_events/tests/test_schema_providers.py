# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema provider implementations."""

import json
import sys
import types
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Provide a stub pymongo module so patching works even if pymongo is not installed.
sys.modules.setdefault("pymongo", types.SimpleNamespace(MongoClient=MagicMock()))

from copilot_events.schema_provider import SchemaProvider
from copilot_events.file_schema_provider import FileSchemaProvider
from copilot_events.mongo_schema_provider import MongoSchemaProvider


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


class TestMongoSchemaProvider:
    """Tests for MongoSchemaProvider."""

    def test_initialization(self):
        """Test MongoSchemaProvider initialization."""
        provider = MongoSchemaProvider(
            mongo_uri="mongodb://localhost:27017",
            database_name="test_db",
            collection_name="test_schemas"
        )

        assert provider.mongo_uri == "mongodb://localhost:27017"
        assert provider.database_name == "test_db"
        assert provider.collection_name == "test_schemas"
        assert provider._schema_cache == {}

    @patch('pymongo.MongoClient')
    def test_ensure_connected(self, mock_mongo_client):
        """Test MongoDB connection establishment."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        result = provider._ensure_connected()

        assert result is True
        assert provider._client is not None
        assert provider._collection is not None
        mock_mongo_client.assert_called_once_with("mongodb://localhost:27017")

    @patch('pymongo.MongoClient')
    def test_get_schema_success(self, mock_mongo_client):
        """Test successfully retrieving a schema from MongoDB."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        test_schema = {"type": "object", "properties": {}}
        mock_collection.find_one.return_value = {
            "name": "TestEvent",
            "schema": test_schema
        }

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        schema = provider.get_schema("TestEvent")

        assert schema is not None
        assert schema == test_schema
        mock_collection.find_one.assert_called_once_with({"name": "TestEvent"})

    @patch('pymongo.MongoClient')
    def test_get_schema_caching(self, mock_mongo_client):
        """Test that schemas are cached after first retrieval."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        test_schema = {"type": "object"}
        mock_collection.find_one.return_value = {
            "name": "TestEvent",
            "schema": test_schema
        }

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        
        # Retrieve schema twice
        schema1 = provider.get_schema("TestEvent")
        schema2 = provider.get_schema("TestEvent")

        # Should only call MongoDB once (second time uses cache)
        assert mock_collection.find_one.call_count == 1
        assert schema1 is schema2

    @patch('pymongo.MongoClient')
    def test_get_schema_not_found(self, mock_mongo_client):
        """Test retrieving a non-existent schema."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_collection.find_one.return_value = None

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        schema = provider.get_schema("NonExistentEvent")

        assert schema is None

    @patch('pymongo.MongoClient')
    def test_list_event_types(self, mock_mongo_client):
        """Test listing all event types from MongoDB."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_cursor = [
            {"name": "EventA"},
            {"name": "EventB"},
            {"name": "EventC"}
        ]
        mock_collection.find.return_value = mock_cursor

        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        event_types = provider.list_event_types()

        assert len(event_types) == 3
        assert "EventA" in event_types
        assert "EventB" in event_types
        assert "EventC" in event_types
        assert event_types == sorted(event_types)  # Should be sorted
        mock_collection.find.assert_called_once_with({}, {"name": 1, "_id": 0})

    @patch('pymongo.MongoClient')
    def test_context_manager(self, mock_mongo_client):
        """Test using MongoSchemaProvider as a context manager."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        with MongoSchemaProvider("mongodb://localhost:27017") as provider:
            assert provider._collection is not None

        mock_client.close.assert_called_once()

    @patch('pymongo.MongoClient')
    def test_close(self, mock_mongo_client):
        """Test closing MongoDB connection."""
        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_mongo_client.return_value = mock_client
        mock_client.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection

        provider = MongoSchemaProvider("mongodb://localhost:27017")
        provider._ensure_connected()
        
        provider.close()
        
        mock_client.close.assert_called_once()
        assert provider._client is None
        assert provider._collection is None

    def test_pymongo_not_available(self):
        """Test behavior when pymongo is not installed."""
        with patch.dict('sys.modules', {'pymongo': None}):
            provider = MongoSchemaProvider("mongodb://localhost:27017")
            # Should fail gracefully
            assert provider._ensure_connected() is False
