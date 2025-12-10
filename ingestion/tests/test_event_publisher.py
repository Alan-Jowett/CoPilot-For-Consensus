# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for event publishing module."""

import json
import pytest

from copilot_events import (
    NoopPublisher,
    RabbitMQPublisher,
    create_publisher,
    ArchiveIngestedEvent,
)


class TestNoopPublisher:
    """Tests for NoopPublisher."""

    def test_noop_publisher_connect(self):
        """Test connecting to noop publisher."""
        publisher = NoopPublisher()
        assert publisher.connect() is True

    def test_noop_publisher_disconnect(self):
        """Test disconnecting from noop publisher."""
        publisher = NoopPublisher()
        publisher.connect()
        publisher.disconnect()  # Should not raise

    def test_noop_publisher_publish(self):
        """Test publishing to noop publisher."""
        publisher = NoopPublisher()
        publisher.connect()

        event = {"event_type": "test", "event_id": "123"}
        result = publisher.publish("exchange", "routing.key", event)

        assert result is True
        assert len(publisher.published_events) == 1
        assert publisher.published_events[0]["exchange"] == "exchange"
        assert publisher.published_events[0]["routing_key"] == "routing.key"

    def test_noop_publisher_multiple_publishes(self):
        """Test multiple publishes to noop publisher."""
        publisher = NoopPublisher()
        publisher.connect()

        for i in range(3):
            event = {"event_type": f"test{i}", "event_id": str(i)}
            publisher.publish("exchange", "routing.key", event)

        assert len(publisher.published_events) == 3


class TestCreatePublisher:
    """Tests for create_publisher factory."""

    def test_create_noop_publisher(self):
        """Test creating noop publisher."""
        publisher = create_publisher(message_bus_type="noop")
        assert isinstance(publisher, NoopPublisher)

    def test_create_publisher_invalid_type(self):
        """Test creating publisher with invalid type."""
        with pytest.raises(ValueError):
            create_publisher(message_bus_type="invalid")

    def test_create_rabbitmq_publisher(self):
        """Test creating RabbitMQ publisher."""
        publisher = create_publisher(
            message_bus_type="rabbitmq",
            host="localhost",
            port=5672,
        )
        assert isinstance(publisher, RabbitMQPublisher)
        assert publisher.host == "localhost"
        assert publisher.port == 5672


class TestArchiveIngestedEvent:
    """Tests for ArchiveIngestedEvent."""

    def test_archive_ingested_event_defaults(self):
        """Test ArchiveIngestedEvent with defaults."""
        event = ArchiveIngestedEvent()

        assert event.event_type == "ArchiveIngested"
        assert event.event_id is not None
        assert event.timestamp is not None
        assert event.version == "1.0"

    def test_archive_ingested_event_to_dict(self):
        """Test converting ArchiveIngestedEvent to dictionary."""
        event_data = {
            "archive_id": "test-id",
            "source_name": "test-source",
            "file_path": "/path/to/file",
        }

        event = ArchiveIngestedEvent(data=event_data)
        event_dict = event.to_dict()

        assert event_dict["event_type"] == "ArchiveIngested"
        assert event_dict["event_id"] == event.event_id
        assert event_dict["timestamp"] == event.timestamp
        assert event_dict["version"] == "1.0"
        assert event_dict["data"]["archive_id"] == "test-id"

    def test_archive_ingested_event_json_serializable(self):
        """Test that ArchiveIngestedEvent is JSON serializable."""
        event_data = {
            "archive_id": "test-id",
            "source_name": "test-source",
        }

        event = ArchiveIngestedEvent(data=event_data)
        event_dict = event.to_dict()

        # Should not raise
        json_str = json.dumps(event_dict)
        assert json_str is not None
