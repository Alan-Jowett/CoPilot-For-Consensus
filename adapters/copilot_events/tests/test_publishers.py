# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event publishers."""

import pytest

from copilot_events import create_publisher, EventPublisher, RabbitMQPublisher, NoopPublisher


class TestPublisherFactory:
    """Tests for create_publisher factory function."""

    def test_create_rabbitmq_publisher(self):
        """Test creating a RabbitMQ publisher."""
        publisher = create_publisher(
            message_bus_type="rabbitmq",
            host="localhost",
            port=5672,
        )

        assert isinstance(publisher, RabbitMQPublisher)
        assert isinstance(publisher, EventPublisher)
        assert publisher.host == "localhost"
        assert publisher.port == 5672

    def test_create_noop_publisher(self):
        """Test creating a no-op publisher."""
        publisher = create_publisher(message_bus_type="noop")

        assert isinstance(publisher, NoopPublisher)
        assert isinstance(publisher, EventPublisher)

    def test_create_unknown_publisher_type(self):
        """Test that unknown publisher type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown message_bus_type"):
            create_publisher(message_bus_type="invalid")


class TestNoopPublisher:
    """Tests for NoopPublisher."""

    def test_connect(self):
        """Test connecting to no-op publisher."""
        publisher = NoopPublisher()

        publisher.connect()  # Should not raise

        assert publisher.connected is True

    def test_disconnect(self):
        """Test disconnecting from no-op publisher."""
        publisher = NoopPublisher()
        publisher.connect()

        publisher.disconnect()

        assert publisher.connected is False

    def test_publish_event(self):
        """Test publishing an event."""
        publisher = NoopPublisher()
        publisher.connect()

        event = {"event_type": "TestEvent", "data": {"foo": "bar"}}
        publisher.publish("test.exchange", "test.key", event)

        assert len(publisher.published_events) == 1
        assert publisher.published_events[0]["exchange"] == "test.exchange"
        assert publisher.published_events[0]["routing_key"] == "test.key"
        assert publisher.published_events[0]["event"] == event

    def test_publish_multiple_events(self):
        """Test publishing multiple events."""
        publisher = NoopPublisher()
        publisher.connect()

        publisher.publish("ex1", "key1", {"type": "Event1"})
        publisher.publish("ex2", "key2", {"type": "Event2"})
        publisher.publish("ex3", "key3", {"type": "Event3"})

        assert len(publisher.published_events) == 3

    def test_clear_events(self):
        """Test clearing stored events."""
        publisher = NoopPublisher()
        publisher.connect()

        publisher.publish("ex", "key", {"type": "Event"})
        assert len(publisher.published_events) == 1

        publisher.clear_events()
        assert len(publisher.published_events) == 0

    def test_get_events_all(self):
        """Test getting all events."""
        publisher = NoopPublisher()
        publisher.connect()

        publisher.publish("ex", "key1", {"event_type": "Type1"})
        publisher.publish("ex", "key2", {"event_type": "Type2"})

        events = publisher.get_events()
        assert len(events) == 2

    def test_get_events_filtered(self):
        """Test getting filtered events by type."""
        publisher = NoopPublisher()
        publisher.connect()

        publisher.publish("ex", "key1", {"event_type": "TypeA"})
        publisher.publish("ex", "key2", {"event_type": "TypeB"})
        publisher.publish("ex", "key3", {"event_type": "TypeA"})

        events = publisher.get_events(event_type="TypeA")
        assert len(events) == 2
        assert all(e["event"]["event_type"] == "TypeA" for e in events)


class TestRabbitMQPublisher:
    """Tests for RabbitMQPublisher."""

    def test_initialization(self):
        """Test RabbitMQ publisher initialization."""
        publisher = RabbitMQPublisher(
            host="testhost",
            port=5673,
            username="testuser",
            password="testpass",
            exchange="test.exchange",
        )

        assert publisher.host == "testhost"
        assert publisher.port == 5673
        assert publisher.username == "testuser"
        assert publisher.password == "testpass"
        assert publisher.exchange == "test.exchange"

    def test_default_values(self):
        """Test default initialization values."""
        publisher = RabbitMQPublisher()

        assert publisher.host == "localhost"
        assert publisher.port == 5672
        assert publisher.username == "guest"
        assert publisher.password == "guest"
        assert publisher.exchange == "copilot.events"
        assert publisher.exchange_type == "topic"
        assert publisher.enable_publisher_confirms is True

    def test_publisher_confirms_disabled(self):
        """Test initialization with publisher confirms disabled."""
        publisher = RabbitMQPublisher(enable_publisher_confirms=False)

        assert publisher.enable_publisher_confirms is False

    def test_declared_queues_tracking(self):
        """Test that declared queues are tracked."""
        publisher = RabbitMQPublisher()

        # Initially no queues declared
        assert len(publisher._declared_queues) == 0

    # Note: Actual connection tests would require a running RabbitMQ instance
    # or mocking the pika library, which is beyond the scope of basic unit tests
