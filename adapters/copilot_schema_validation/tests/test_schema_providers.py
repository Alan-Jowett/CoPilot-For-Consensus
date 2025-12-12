# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema provider implementations."""

import json
import logging
import pytest

from copilot_schema_validation.file_schema_provider import FileSchemaProvider
from copilot_schema_validation.document_store_schema_provider import DocumentStoreSchemaProvider
from copilot_storage import InMemoryDocumentStore


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
    """Tests for DocumentStoreSchemaProvider."""

    def test_initialization(self):
        """Test DocumentStoreSchemaProvider initialization."""
        store = InMemoryDocumentStore()
        provider = DocumentStoreSchemaProvider(
            document_store=store,
            database_name="test_db",
            collection_name="test_schemas",
        )

        assert provider.mongo_uri is None
        assert provider.database_name == "test_db"
        assert provider.collection_name == "test_schemas"
        assert provider._schema_cache == {}
        assert provider._store is store

    def test_ensure_connected_with_store(self):
        store = InMemoryDocumentStore()
        provider = DocumentStoreSchemaProvider(document_store=store)

        assert provider._ensure_connected() is True
        assert store.connected is True

    def test_get_schema_success(self):
        store = InMemoryDocumentStore()
        store.connect()
        test_schema = {"type": "object", "properties": {}}
        store.insert_document("event_schemas", {"name": "TestEvent", "schema": test_schema})

        provider = DocumentStoreSchemaProvider(document_store=store)
        schema = provider.get_schema("TestEvent")

        assert schema is not None
        assert schema == test_schema

    def test_get_schema_caching(self):
        store = InMemoryDocumentStore()
        store.connect()
        test_schema = {"type": "object"}
        store.insert_document("event_schemas", {"name": "TestEvent", "schema": test_schema})

        provider = DocumentStoreSchemaProvider(document_store=store)

        schema1 = provider.get_schema("TestEvent")
        schema2 = provider.get_schema("TestEvent")

        assert schema1 is schema2
        assert provider._schema_cache["TestEvent"] == test_schema

    def test_get_schema_not_found(self):
        store = InMemoryDocumentStore()
        store.connect()
        provider = DocumentStoreSchemaProvider(document_store=store)

        schema = provider.get_schema("NonExistentEvent")

        assert schema is None

    def test_list_event_types(self):
        store = InMemoryDocumentStore()
        store.connect()
        store.insert_document("event_schemas", {"name": "EventA", "schema": {}})
        store.insert_document("event_schemas", {"name": "EventB", "schema": {}})
        store.insert_document("event_schemas", {"name": "EventC", "schema": {}})

        provider = DocumentStoreSchemaProvider(document_store=store)
        event_types = provider.list_event_types()

        assert len(event_types) == 3
        assert event_types == sorted(event_types)

    def test_context_manager(self):
        store = InMemoryDocumentStore()
        provider = DocumentStoreSchemaProvider(document_store=store)

        with provider as p:
            assert p._store is store
            assert store.connected is True

    def test_close_does_not_disconnect_external_store(self):
        class TrackStore(InMemoryDocumentStore):
            def __init__(self):
                super().__init__()
                self.disconnect_called = False

            def disconnect(self) -> None:
                self.disconnect_called = True
                super().disconnect()

        store = TrackStore()
        store.connect()
        provider = DocumentStoreSchemaProvider(document_store=store)

        provider.close()
        assert store.disconnect_called is False

    def test_error_when_no_store_or_uri(self, caplog):
        caplog.set_level(logging.ERROR)
        provider = DocumentStoreSchemaProvider()

        assert provider.get_schema("Anything") is None
        assert any("Either document_store must be provided" in msg for msg in caplog.messages)

    def test_connect_error_is_logged(self, caplog):
        class FailingStore(InMemoryDocumentStore):
            def connect(self) -> bool:
                raise RuntimeError("boom")

        caplog.set_level(logging.ERROR)
        provider = DocumentStoreSchemaProvider(document_store=FailingStore())

        assert provider._ensure_connected() is False
        assert any("Failed to connect document store" in msg for msg in caplog.messages)

    def test_close_disconnects_owned_store(self, monkeypatch):
        disconnect_calls = []

        class DummyStore(InMemoryDocumentStore):
            def disconnect(self) -> None:
                disconnect_calls.append(True)
                super().disconnect()

        def fake_create_document_store(**kwargs):
            return DummyStore()

        monkeypatch.setattr(
            "copilot_schema_validation.document_store_schema_provider.create_document_store",
            fake_create_document_store,
        )

        provider = DocumentStoreSchemaProvider(mongo_uri="mongodb://host:27017")
        assert provider._ensure_connected() is True

        provider.close()
        assert disconnect_calls, "Owned store should be disconnected on close"

    def test_list_event_types_warns_on_truncation(self, caplog):
        store = InMemoryDocumentStore()
        store.connect()
        for i in range(3):
            store.insert_document("event_schemas", {"name": f"Event{i}", "schema": {}})

        caplog.set_level(logging.WARNING)
        provider = DocumentStoreSchemaProvider(document_store=store, list_limit=2)
        event_types = provider.list_event_types()

        assert len(event_types) == 2
        assert any("truncated" in msg for msg in caplog.messages)

    def test_uri_does_not_pass_port(self, monkeypatch):
         captured_kwargs = {}
 
         def fake_create_document_store(**kwargs):
             captured_kwargs.update(kwargs)
             return InMemoryDocumentStore()
 
         monkeypatch.setattr(
             "copilot_schema_validation.document_store_schema_provider.create_document_store",
             fake_create_document_store,
         )
 
         provider = DocumentStoreSchemaProvider(
             mongo_uri="mongodb://admin:password@localhost:27017/cooldb",
             port=27017,
         )
         provider._ensure_connected()
 
         assert "port" not in captured_kwargs
         assert captured_kwargs.get("host").startswith("mongodb://admin:password@localhost:27017")

    def test_mongo_uri_initialization_creates_store(self, monkeypatch):
        captured_kwargs = {}

        class DummyStore(InMemoryDocumentStore):
            def connect(self) -> bool:
                self.connected = True
                return True

        def fake_create_document_store(**kwargs):
            captured_kwargs.update(kwargs)
            return DummyStore()

        monkeypatch.setattr(
            "copilot_schema_validation.document_store_schema_provider.create_document_store",
            fake_create_document_store,
        )

        provider = DocumentStoreSchemaProvider(
            mongo_uri="mongodb://localhost:27017",
            database_name="mydb",
            collection_name="event_schemas",
        )

        assert provider._ensure_connected() is True
        assert isinstance(provider._store, InMemoryDocumentStore)
        assert captured_kwargs.get("host") == "mongodb://localhost:27017"
        assert captured_kwargs.get("database") == "mydb"

    def test_connect_error_with_mongo_uri_logs(self, caplog, monkeypatch):
        class FailingStore(InMemoryDocumentStore):
            def connect(self) -> bool:
                raise RuntimeError("cannot connect")

        def fake_create_document_store(**kwargs):
            return FailingStore()

        monkeypatch.setattr(
            "copilot_schema_validation.document_store_schema_provider.create_document_store",
            fake_create_document_store,
        )

        caplog.set_level(logging.ERROR)
        provider = DocumentStoreSchemaProvider(mongo_uri="mongodb://bad-uri")

        assert provider._ensure_connected() is False
        assert any("Failed to connect document store" in msg for msg in caplog.messages)

