# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for validating event publisher."""

import pytest

from copilot_events import NoopPublisher
from copilot_events.validating_publisher import ValidatingEventPublisher, ValidationError


class MockSchemaProvider:
    """Mock schema provider for testing."""
    
    def __init__(self, schemas=None):
        """Initialize with optional schemas dictionary."""
        self.schemas = schemas or {}
    
    def get_schema(self, event_type: str):
        """Return schema for event type or None if not found."""
        return self.schemas.get(event_type)


class TestValidatingEventPublisher:
    """Tests for ValidatingEventPublisher."""
    
    def test_init(self):
        """Test initializing a validating publisher."""
        base = NoopPublisher()
        provider = MockSchemaProvider()
        
        publisher = ValidatingEventPublisher(
            publisher=base,
            schema_provider=provider,
            strict=True
        )
        
        assert publisher._publisher is base
        assert publisher._schema_provider is provider
        assert publisher._strict is True
    
    def test_publish_valid_event_strict_mode(self):
        """Test publishing a valid event in strict mode."""
        base = NoopPublisher()
        base.connect()
        
        schema = {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "event_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "version": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "archive_id": {"type": "string"}
                    },
                    "required": ["archive_id"]
                }
            },
            "required": ["event_type", "event_id", "timestamp", "version", "data"]
        }
        
        provider = MockSchemaProvider({"TestEvent": schema})
        publisher = ValidatingEventPublisher(base, provider, strict=True)
        
        event = {
            "event_type": "TestEvent",
            "event_id": "123",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {"archive_id": "abc"}
        }
        
        # Should not raise any exception
        publisher.publish("copilot.events", "test.event", event)
    
    def test_publish_invalid_event_strict_mode(self):
        """Test publishing an invalid event in strict mode raises ValidationError."""
        base = NoopPublisher()
        base.connect()
        
        schema = {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "event_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "version": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "archive_id": {"type": "string"}
                    },
                    "required": ["archive_id"]
                }
            },
            "required": ["event_type", "event_id", "timestamp", "version", "data"]
        }
        
        provider = MockSchemaProvider({"TestEvent": schema})
        publisher = ValidatingEventPublisher(base, provider, strict=True)
        
        # Missing required data.archive_id
        event = {
            "event_type": "TestEvent",
            "event_id": "123",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {}
        }
        
        with pytest.raises(ValidationError) as exc_info:
            publisher.publish("copilot.events", "test.event", event)
        
        assert exc_info.value.event_type == "TestEvent"
        assert len(exc_info.value.errors) > 0
        assert any("archive_id" in err for err in exc_info.value.errors)
    
    def test_publish_invalid_event_non_strict_mode(self):
        """Test publishing an invalid event in non-strict mode succeeds with warning."""
        base = NoopPublisher()
        base.connect()
        
        schema = {
            "type": "object",
            "properties": {
                "event_type": {"type": "string"},
                "data": {
                    "type": "object",
                    "properties": {
                        "archive_id": {"type": "string"}
                    },
                    "required": ["archive_id"]
                }
            },
            "required": ["event_type", "data"]
        }
        
        provider = MockSchemaProvider({"TestEvent": schema})
        publisher = ValidatingEventPublisher(base, provider, strict=False)
        
        # Missing required data.archive_id
        event = {
            "event_type": "TestEvent",
            "data": {}
        }
        
        # Should succeed despite validation failure
        publisher.publish("copilot.events", "test.event", event)
    
    def test_publish_without_schema_provider(self):
        """Test publishing without schema provider skips validation."""
        base = NoopPublisher()
        base.connect()
        
        publisher = ValidatingEventPublisher(base, schema_provider=None, strict=True)
        
        # Even invalid event should pass without schema provider
        event = {"anything": "goes"}
        
        publisher.publish("copilot.events", "test.event", event)
    
    def test_publish_event_missing_event_type(self):
        """Test publishing event without event_type field fails."""
        base = NoopPublisher()
        base.connect()
        
        provider = MockSchemaProvider()
        publisher = ValidatingEventPublisher(base, provider, strict=True)
        
        event = {"data": {"some": "data"}}
        
        with pytest.raises(ValidationError) as exc_info:
            publisher.publish("copilot.events", "test.event", event)
        
        assert "event_type" in str(exc_info.value).lower()
    
    def test_publish_schema_not_found_strict_mode(self):
        """Test publishing event with no schema in strict mode fails."""
        base = NoopPublisher()
        base.connect()
        
        provider = MockSchemaProvider({})  # Empty schemas
        publisher = ValidatingEventPublisher(base, provider, strict=True)
        
        event = {"event_type": "UnknownEvent", "data": {}}
        
        with pytest.raises(ValidationError) as exc_info:
            publisher.publish("copilot.events", "test.event", event)
        
        assert "UnknownEvent" in str(exc_info.value)
    
    def test_publish_schema_not_found_non_strict_mode(self):
        """Test publishing event with no schema in non-strict mode succeeds."""
        base = NoopPublisher()
        base.connect()
        
        provider = MockSchemaProvider({})  # Empty schemas
        publisher = ValidatingEventPublisher(base, provider, strict=False)
        
        event = {"event_type": "UnknownEvent", "data": {}}
        
        # Should succeed in non-strict mode
        publisher.publish("copilot.events", "test.event", event)
    
    def test_connect_delegates_to_underlying_publisher(self):
        """Test that connect is delegated to underlying publisher."""
        base = NoopPublisher()
        provider = MockSchemaProvider()
        publisher = ValidatingEventPublisher(base, provider)
        
        publisher.connect()  # Should not raise
        assert base.connected is True
    
    def test_disconnect_delegates_to_underlying_publisher(self):
        """Test that disconnect is delegated to underlying publisher."""
        base = NoopPublisher()
        base.connect()
        
        provider = MockSchemaProvider()
        publisher = ValidatingEventPublisher(base, provider)
        
        publisher.disconnect()
        assert base.connected is False
