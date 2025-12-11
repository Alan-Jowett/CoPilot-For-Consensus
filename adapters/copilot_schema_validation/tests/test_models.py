# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event models."""

import json

from copilot_schema_validation import (
    ArchiveIngestedEvent,
    ArchiveIngestionFailedEvent,
    JSONParsedEvent,
    ParsingFailedEvent,
)


class TestArchiveIngestedEvent:
    """Tests for ArchiveIngestedEvent model."""

    def test_event_defaults(self):
        """Test event with default values."""
        event = ArchiveIngestedEvent()
        
        assert event.event_type == "ArchiveIngested"
        assert event.version == "1.0"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.data == {}

    def test_event_with_data(self):
        """Test event with custom data."""
        data = {
            "archive_id": "test-123",
            "source_name": "test-source",
            "file_path": "/test/path.mbox",
        }
        event = ArchiveIngestedEvent(data=data)
        
        assert event.data == data
        assert event.event_type == "ArchiveIngested"

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        data = {"archive_id": "abc-123"}
        event = ArchiveIngestedEvent(data=data)
        
        result = event.to_dict()
        
        assert result["event_type"] == "ArchiveIngested"
        assert result["version"] == "1.0"
        assert "event_id" in result
        assert "timestamp" in result
        assert result["data"] == data

    def test_event_json_serializable(self):
        """Test that event can be JSON serialized."""
        event = ArchiveIngestedEvent(data={"test": "value"})
        
        # Should not raise exception
        json_str = json.dumps(event.to_dict())
        
        # Should be able to deserialize
        result = json.loads(json_str)
        assert result["event_type"] == "ArchiveIngested"

    def test_unique_event_ids(self):
        """Test that each event gets a unique ID."""
        event1 = ArchiveIngestedEvent()
        event2 = ArchiveIngestedEvent()
        
        assert event1.event_id != event2.event_id


class TestArchiveIngestionFailedEvent:
    """Tests for ArchiveIngestionFailedEvent model."""

    def test_event_defaults(self):
        """Test event with default values."""
        event = ArchiveIngestionFailedEvent()
        
        assert event.event_type == "ArchiveIngestionFailed"
        assert event.version == "1.0"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.data == {}

    def test_event_with_error_data(self):
        """Test event with error information."""
        data = {
            "source_name": "test-source",
            "error_message": "Connection failed",
            "error_type": "ConnectionError",
            "retry_count": 3,
        }
        event = ArchiveIngestionFailedEvent(data=data)
        
        assert event.data == data
        assert event.data["error_message"] == "Connection failed"

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        event = ArchiveIngestionFailedEvent(data={"error": "test"})
        
        result = event.to_dict()
        
        assert result["event_type"] == "ArchiveIngestionFailed"
        assert result["version"] == "1.0"
        assert "event_id" in result
        assert "timestamp" in result


class TestJSONParsedEvent:
    """Tests for JSONParsedEvent model."""

    def test_event_defaults(self):
        """Test event with default values."""
        event = JSONParsedEvent()
        
        assert event.event_type == "JSONParsed"
        assert event.version == "1.0"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.data == {}

    def test_event_with_data(self):
        """Test event with parsing results."""
        data = {
            "archive_id": "test-123",
            "message_count": 150,
            "parsed_message_ids": ["msg1", "msg2", "msg3"],
            "thread_count": 45,
            "thread_ids": ["thread1", "thread2"],
            "parsing_duration_seconds": 12.5,
        }
        event = JSONParsedEvent(data=data)
        
        assert event.data == data
        assert event.data["message_count"] == 150
        assert event.data["thread_count"] == 45

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        data = {"archive_id": "abc-123", "message_count": 100}
        event = JSONParsedEvent(data=data)
        
        result = event.to_dict()
        
        assert result["event_type"] == "JSONParsed"
        assert result["version"] == "1.0"
        assert "event_id" in result
        assert "timestamp" in result
        assert result["data"] == data

    def test_event_json_serializable(self):
        """Test that event can be JSON serialized."""
        event = JSONParsedEvent(data={"message_count": 50})
        
        # Should not raise exception
        json_str = json.dumps(event.to_dict())
        
        # Should be able to deserialize
        result = json.loads(json_str)
        assert result["event_type"] == "JSONParsed"


class TestParsingFailedEvent:
    """Tests for ParsingFailedEvent model."""

    def test_event_defaults(self):
        """Test event with default values."""
        event = ParsingFailedEvent()
        
        assert event.event_type == "ParsingFailed"
        assert event.version == "1.0"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.data == {}

    def test_event_with_error_data(self):
        """Test event with error information."""
        data = {
            "archive_id": "test-123",
            "file_path": "/test/archive.mbox",
            "error_message": "Invalid mbox format",
            "error_type": "MboxParseError",
            "messages_parsed_before_failure": 75,
            "retry_count": 3,
        }
        event = ParsingFailedEvent(data=data)
        
        assert event.data == data
        assert event.data["error_message"] == "Invalid mbox format"
        assert event.data["messages_parsed_before_failure"] == 75

    def test_event_to_dict(self):
        """Test event serialization to dict."""
        event = ParsingFailedEvent(data={"error": "test"})
        
        result = event.to_dict()
        
        assert result["event_type"] == "ParsingFailed"
        assert result["version"] == "1.0"
        assert "event_id" in result
        assert "timestamp" in result
