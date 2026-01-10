# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event publishers."""

import pytest
from copilot_config import load_driver_config
from copilot_message_bus import EventPublisher, create_publisher
from copilot_message_bus.noop_publisher import NoopPublisher
from copilot_message_bus.rabbitmq_publisher import RabbitMQPublisher


class TestPublisherFactory:
    """Tests for create_publisher factory function."""

    def test_create_rabbitmq_publisher(self):
        """Test creating a RabbitMQ publisher."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "rabbitmq",
            fields={
                "rabbitmq_host": "localhost",
                "rabbitmq_port": 5672,
                "rabbitmq_username": "guest",
                "rabbitmq_password": "guest",
            },
        )
        publisher = create_publisher(
            driver_name="rabbitmq",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(publisher, RabbitMQPublisher)
        assert isinstance(publisher, EventPublisher)
        assert publisher.host == "localhost"
        assert publisher.port == 5672

    def test_create_noop_publisher(self):
        """Test creating a no-op publisher."""
        driver_config = load_driver_config(None, "message_bus", "noop")
        publisher = create_publisher(
            driver_name="noop",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(publisher, NoopPublisher)
        assert isinstance(publisher, EventPublisher)

    def test_create_unknown_publisher_type(self):
        """Test that unknown publisher type raises ValueError."""
        with pytest.raises(ValueError, match="does not support driver"):
            load_driver_config(None, "message_bus", "invalid")

    def test_validation_enabled_by_default(self):
        """Test that publishers are wrapped in ValidatingEventPublisher by default."""
        from copilot_message_bus.validating_publisher import ValidatingEventPublisher

        driver_config = load_driver_config(None, "message_bus", "noop")
        publisher = create_publisher(driver_name="noop", driver_config=driver_config)

        assert isinstance(publisher, ValidatingEventPublisher)
        # The underlying publisher should be NoopPublisher
        assert isinstance(publisher._publisher, NoopPublisher)


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

    def test_missing_required_parameters(self):
        """Test initialization requires explicit connection parameters."""
        import pytest
        with pytest.raises(ValueError):
            RabbitMQPublisher()

    def test_publisher_confirms_disabled(self):
        """Test initialization with publisher confirms disabled."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            enable_publisher_confirms=False,
        )

        assert publisher.enable_publisher_confirms is False

    def test_declared_queues_tracking(self):
        """Test that declared queues are tracked."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        # Initially no queues declared
        assert len(publisher._declared_queues) == 0

    # Note: Actual connection tests would require a running RabbitMQ instance
    # or mocking the pika library, which is beyond the scope of basic unit tests


