# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for event subscribers."""

import pytest

from copilot_events import (
    create_subscriber,
    RabbitMQSubscriber,
    NoopSubscriber,
)


class TestSubscriberFactory:
    """Tests for create_subscriber factory function."""

    def test_create_rabbitmq_subscriber(self):
        """Test creating RabbitMQ subscriber."""
        subscriber = create_subscriber(
            "rabbitmq",
            host="localhost",
            port=5672,
            username="test",
            password="pass"
        )
        
        assert isinstance(subscriber, RabbitMQSubscriber)
        assert subscriber.host == "localhost"
        assert subscriber.port == 5672
        assert subscriber.username == "test"
        assert subscriber.password == "pass"

    def test_create_rabbitmq_subscriber_defaults(self):
        """Test RabbitMQ subscriber with default values."""
        subscriber = create_subscriber("rabbitmq", host="localhost")
        
        assert isinstance(subscriber, RabbitMQSubscriber)
        assert subscriber.port == 5672
        assert subscriber.username == "guest"
        assert subscriber.password == "guest"

    def test_create_noop_subscriber(self):
        """Test creating Noop subscriber."""
        subscriber = create_subscriber("noop")
        
        assert isinstance(subscriber, NoopSubscriber)

    def test_create_unknown_subscriber_type(self):
        """Test error when creating unknown subscriber type."""
        with pytest.raises(ValueError, match="Unknown message bus type"):
            create_subscriber("unknown")

    def test_rabbitmq_requires_host(self):
        """Test that RabbitMQ subscriber requires host."""
        with pytest.raises(ValueError, match="host is required"):
            create_subscriber("rabbitmq")


class TestNoopSubscriber:
    """Tests for NoopSubscriber."""

    def test_connect(self):
        """Test connecting to noop subscriber."""
        subscriber = NoopSubscriber()
        
        assert not subscriber.connected
        subscriber.connect()
        assert subscriber.connected

    def test_disconnect(self):
        """Test disconnecting from noop subscriber."""
        subscriber = NoopSubscriber()
        subscriber.connect()
        
        subscriber.disconnect()
        assert not subscriber.connected

    def test_subscribe(self):
        """Test subscribing to an event type."""
        subscriber = NoopSubscriber()
        callback_called = []
        
        def callback(event):
            callback_called.append(event)
        
        subscriber.subscribe("TestEvent", callback)
        
        assert "TestEvent" in subscriber.get_subscriptions()

    def test_inject_event(self):
        """Test manually injecting an event."""
        subscriber = NoopSubscriber()
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        subscriber.subscribe("TestEvent", callback)
        
        test_event = {
            "event_type": "TestEvent",
            "event_id": "123",
            "data": {"test": "value"}
        }
        
        subscriber.inject_event(test_event)
        
        assert len(received_events) == 1
        assert received_events[0] == test_event

    def test_inject_event_no_callback(self):
        """Test injecting event with no registered callback."""
        subscriber = NoopSubscriber()
        
        # When no callback is registered, inject_event should complete without error
        # and not modify subscriber state
        initial_callbacks = dict(subscriber.callbacks)
        
        subscriber.inject_event({
            "event_type": "UnknownEvent",
            "event_id": "123"
        })
        
        # Verify no callbacks were added and state unchanged
        assert subscriber.callbacks == initial_callbacks

    def test_inject_event_no_type(self):
        """Test injecting event without event_type field."""
        subscriber = NoopSubscriber()
        
        with pytest.raises(ValueError, match="Event must have 'event_type' field"):
            subscriber.inject_event({"event_id": "123"})

    def test_start_consuming(self):
        """Test starting consumption (now blocks, so run in thread)."""
        import threading
        import time
        
        subscriber = NoopSubscriber()
        subscriber.connect()
        
        # Start consuming in a separate thread since it now blocks
        consume_thread = threading.Thread(target=subscriber.start_consuming, daemon=True)
        consume_thread.start()
        
        # Give it time to start
        time.sleep(0.1)
        assert subscriber.consuming
        
        # Clean up
        subscriber.stop_consuming()
        consume_thread.join(timeout=1.0)

    def test_start_consuming_not_connected(self):
        """Test error when starting consumption without connection."""
        subscriber = NoopSubscriber()
        
        with pytest.raises(RuntimeError, match="Not connected"):
            subscriber.start_consuming()

    def test_stop_consuming(self):
        """Test stopping consumption."""
        import threading
        import time
        
        subscriber = NoopSubscriber()
        subscriber.connect()
        
        # Start consuming in a separate thread since it now blocks
        consume_thread = threading.Thread(target=subscriber.start_consuming, daemon=True)
        consume_thread.start()
        
        # Give it time to start
        time.sleep(0.1)
        assert subscriber.consuming
        
        subscriber.stop_consuming()
        
        # Wait for thread to finish
        consume_thread.join(timeout=1.0)
        assert not subscriber.consuming
        assert not consume_thread.is_alive()

    def test_get_subscriptions(self):
        """Test getting list of subscriptions."""
        subscriber = NoopSubscriber()
        
        subscriber.subscribe("Event1", lambda e: None)
        subscriber.subscribe("Event2", lambda e: None)
        
        subscriptions = subscriber.get_subscriptions()
        assert len(subscriptions) == 2
        assert "Event1" in subscriptions
        assert "Event2" in subscriptions

    def test_clear_subscriptions(self):
        """Test clearing all subscriptions."""
        subscriber = NoopSubscriber()
        
        subscriber.subscribe("Event1", lambda e: None)
        subscriber.subscribe("Event2", lambda e: None)
        
        subscriber.clear_subscriptions()
        assert len(subscriber.get_subscriptions()) == 0

    def test_multiple_event_injections(self):
        """Test injecting multiple events."""
        subscriber = NoopSubscriber()
        received = []
        
        subscriber.subscribe("TestEvent", lambda e: received.append(e))
        
        for i in range(5):
            subscriber.inject_event({
                "event_type": "TestEvent",
                "event_id": str(i)
            })
        
        assert len(received) == 5


class TestRabbitMQSubscriber:
    """Tests for RabbitMQSubscriber."""

    def test_initialization(self):
        """Test RabbitMQ subscriber initialization."""
        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="test",
            password="pass"
        )
        
        assert subscriber.host == "localhost"
        assert subscriber.port == 5672
        assert subscriber.username == "test"
        assert subscriber.password == "pass"
        assert subscriber.exchange_name == "copilot.events"
        assert subscriber.exchange_type == "topic"

    def test_custom_exchange(self):
        """Test subscriber with custom exchange."""
        subscriber = RabbitMQSubscriber(
            host="localhost",
            exchange_name="custom.exchange",
            exchange_type="fanout"
        )
        
        assert subscriber.exchange_name == "custom.exchange"
        assert subscriber.exchange_type == "fanout"

    def test_event_type_to_routing_key(self):
        """Test conversion of event type to routing key."""
        subscriber = RabbitMQSubscriber(host="localhost")
        
        assert subscriber._event_type_to_routing_key("ArchiveIngested") == "archive.ingested"
        assert subscriber._event_type_to_routing_key("JSONParsed") == "json.parsed"
        assert subscriber._event_type_to_routing_key("ParsingFailed") == "parsing.failed"
        assert subscriber._event_type_to_routing_key("TestEvent") == "test.event"
