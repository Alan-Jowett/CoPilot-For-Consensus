# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for RabbitMQ publisher and subscriber against a real RabbitMQ instance."""

import logging
import os
import time
import threading
import pytest
import uuid

try:
    import pika
except ImportError:
    pika = None  # type: ignore

from copilot_events import (
    RabbitMQPublisher,
    RabbitMQSubscriber,
)

    # Test timing constants
SUBSCRIBER_STARTUP_WAIT = 1  # seconds to wait for subscriber to start
TEST_TIMEOUT_SECONDS = 10  # seconds to wait for test completion

# Add logger for test debugging
logger = logging.getLogger(__name__)


def get_rabbitmq_config():
    """Get RabbitMQ configuration from environment variables."""
    return {
        "host": os.getenv("RABBITMQ_HOST", "localhost"),
        "port": int(os.getenv("RABBITMQ_PORT", "5672")),
        "username": os.getenv("RABBITMQ_USERNAME", "guest"),
        "password": os.getenv("RABBITMQ_PASSWORD", "guest"),
        "exchange": os.getenv("RABBITMQ_EXCHANGE", "copilot.events.test"),
    }


@pytest.fixture(scope="module")
def rabbitmq_publisher():
    """Create and connect to a RabbitMQ publisher for integration tests."""
    config = get_rabbitmq_config()
    # Directly instantiate RabbitMQPublisher to use test exchange
    publisher = RabbitMQPublisher(
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        exchange=config["exchange"],
    )
    
    # Attempt to connect with retries
    max_retries = 5
    for i in range(max_retries):
        if publisher.connect():
            break
        if i < max_retries - 1:
            time.sleep(2)
    else:
        pytest.skip("Could not connect to RabbitMQ - skipping integration tests")
    
    yield publisher
    
    # Cleanup
    publisher.disconnect()


@pytest.fixture
def rabbitmq_subscriber():
    """Create a RabbitMQ subscriber for integration tests."""
    config = get_rabbitmq_config()
    # Directly instantiate RabbitMQSubscriber to use test exchange
    subscriber = RabbitMQSubscriber(
        host=config["host"],
        port=config["port"],
        username=config["username"],
        password=config["password"],
        exchange_name=config["exchange"],
        queue_name=None,  # Let RabbitMQ generate a unique queue name
    )
    
    # Attempt to connect with retries
    max_retries = 5
    for i in range(max_retries):
        try:
            subscriber.connect()
            break
        except (ConnectionError, OSError, TimeoutError):
            # Network/connection errors - retry
            if i < max_retries - 1:
                time.sleep(2)
            else:
                pytest.skip("Could not connect to RabbitMQ - skipping integration tests")
    
    yield subscriber
    
    # Cleanup
    subscriber.disconnect()


@pytest.mark.integration
class TestRabbitMQIntegration:
    """Integration tests for RabbitMQ publisher and subscriber."""

    def test_publisher_connection(self, rabbitmq_publisher):
        """Test that we can connect to RabbitMQ."""
        assert rabbitmq_publisher.connection is not None
        assert rabbitmq_publisher.channel is not None
        assert not rabbitmq_publisher.connection.is_closed

    def test_publish_event(self, rabbitmq_publisher):
        """Test publishing a simple event.
        
        Note: Creates a temporary queue to ensure the message has a route.
        RabbitMQ returns NO_ROUTE if no queue is bound to the exchange.
        """
        # Declare a temporary queue and bind it to receive the message
        result = rabbitmq_publisher.channel.queue_declare(queue='', exclusive=True)
        queue_name = result.method.queue
        rabbitmq_publisher.channel.queue_bind(
            exchange=rabbitmq_publisher.exchange,
            queue=queue_name,
            routing_key="test.event"
        )
        
        event = {
            "event_type": "TestEvent",
            "event_id": str(uuid.uuid4()),
            "data": {"message": "Hello RabbitMQ"},
        }
        
        rabbitmq_publisher.publish(
            exchange=rabbitmq_publisher.exchange,
            routing_key="test.event",
            event=event,
        )
        
        # Clean up the temporary queue
        rabbitmq_publisher.channel.queue_delete(queue=queue_name)

    def test_publish_and_receive_event(self, rabbitmq_publisher, rabbitmq_subscriber):
        """Test publishing and receiving an event."""
        received_events = []
        
        def on_test_event(event):
            """Callback to capture received events."""
            received_events.append(event)
            # Stop consuming after receiving the first event
            rabbitmq_subscriber.stop_consuming()
        
        # Subscribe to test events
        rabbitmq_subscriber.subscribe("TestEvent", on_test_event, routing_key="test.*")
        
        # Start consuming in a background thread
        consume_thread = threading.Thread(
            target=rabbitmq_subscriber.start_consuming
        )
        consume_thread.daemon = True
        consume_thread.start()
        
        try:
            # Give the subscriber time to start
            time.sleep(SUBSCRIBER_STARTUP_WAIT)
            
            # Publish an event
            event = {
                "event_type": "TestEvent",
                "event_id": str(uuid.uuid4()),
                "data": {"message": "Integration test message"},
            }
            
            rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key="test.event",
                event=event,
            )
            
            # Wait for the event to be received
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            # Verify the event was received
            assert len(received_events) == 1
            assert received_events[0]["event_type"] == "TestEvent"
            assert received_events[0]["data"]["message"] == "Integration test message"
        finally:
            # Ensure consuming is stopped
            if consume_thread.is_alive():
                rabbitmq_subscriber.stop_consuming()
                consume_thread.join(timeout=2)

    def test_publish_multiple_events(self, rabbitmq_publisher, rabbitmq_subscriber):
        """Test publishing and receiving multiple events."""
        received_events = []
        num_events = 5
        
        def on_test_event(event):
            """Callback to capture received events."""
            received_events.append(event)
            # Stop consuming after receiving all events
            if len(received_events) >= num_events:
                rabbitmq_subscriber.stop_consuming()
        
        # Subscribe to test events
        rabbitmq_subscriber.subscribe("TestEvent", on_test_event, routing_key="test.*")
        
        # Start consuming in a background thread
        consume_thread = threading.Thread(
            target=rabbitmq_subscriber.start_consuming
        )
        consume_thread.daemon = True
        consume_thread.start()
        
        try:
            # Give the subscriber time to start
            time.sleep(SUBSCRIBER_STARTUP_WAIT)
            
            # Publish multiple events
            for i in range(num_events):
                event = {
                    "event_type": "TestEvent",
                    "event_id": str(uuid.uuid4()),
                    "data": {"index": i, "message": f"Message {i}"},
                }
                
                rabbitmq_publisher.publish(
                    exchange=rabbitmq_publisher.exchange,
                    routing_key="test.event",
                    event=event,
                )
            
            # Wait for events to be received
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            # Verify all events were received
            assert len(received_events) == num_events
            for i in range(num_events):
                assert received_events[i]["data"]["index"] == i
        finally:
            # Ensure consuming is stopped
            if consume_thread.is_alive():
                rabbitmq_subscriber.stop_consuming()
                consume_thread.join(timeout=2)

    def test_routing_key_pattern_matching(self, rabbitmq_publisher, rabbitmq_subscriber):
        """Test that routing key patterns work correctly."""
        received_events = []
        
        def on_test_event(event):
            """Callback to capture received events."""
            received_events.append(event)
            # Stop after receiving one event
            rabbitmq_subscriber.stop_consuming()
        
        # Subscribe to specific pattern
        rabbitmq_subscriber.subscribe("TestEvent", on_test_event, routing_key="test.specific.*")
        
        # Start consuming in a background thread
        consume_thread = threading.Thread(
            target=rabbitmq_subscriber.start_consuming
        )
        consume_thread.daemon = True
        consume_thread.start()
        
        try:
            # Give the subscriber time to start
            time.sleep(SUBSCRIBER_STARTUP_WAIT)
            
            # Publish events with different routing keys
            # This should be received
            event1 = {
                "event_type": "TestEvent",
                "event_id": str(uuid.uuid4()),
                "data": {"message": "Should receive this"},
            }
            rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key="test.specific.event",
                event=event1,
            )
            
            # Wait a moment for the first message to be processed
            time.sleep(0.5)
            
            # This should NOT be received (different pattern)
            # Publishing to a routing key with no queue bound will raise an exception
            event2 = {
                "event_type": "TestEvent",
                "event_id": str(uuid.uuid4()),
                "data": {"message": "Should NOT receive this"},
            }
            try:
                rabbitmq_publisher.publish(
                    exchange=rabbitmq_publisher.exchange,
                    routing_key="test.other.event",
                    event=event2,
                )
                # If no exception is raised, that's also acceptable for this test
            except Exception:
                # Expected: publishing to unbound routing key raises exception
                pass
            
            # Wait for events
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            # Verify only matching event was received
            assert len(received_events) == 1
            assert received_events[0]["data"]["message"] == "Should receive this"
        finally:
            # Ensure consuming is stopped
            if consume_thread.is_alive():
                rabbitmq_subscriber.stop_consuming()
                consume_thread.join(timeout=2)

    def test_complex_event_data(self, rabbitmq_publisher, rabbitmq_subscriber):
        """Test publishing and receiving events with complex nested data."""
        received_events = []
        
        def on_test_event(event):
            """Callback to capture received events."""
            received_events.append(event)
            rabbitmq_subscriber.stop_consuming()
        
        rabbitmq_subscriber.subscribe("ComplexEvent", on_test_event, routing_key="test.*")
        
        consume_thread = threading.Thread(
            target=rabbitmq_subscriber.start_consuming
        )
        consume_thread.daemon = True
        consume_thread.start()
        
        try:
            time.sleep(SUBSCRIBER_STARTUP_WAIT)
            
            # Create a complex event
            complex_event = {
                "event_type": "ComplexEvent",
                "event_id": str(uuid.uuid4()),
                "data": {
                    "nested": {
                        "array": [1, 2, 3, 4, 5],
                        "object": {
                            "key1": "value1",
                            "key2": "value2",
                        },
                    },
                    "metadata": {
                        "tags": ["integration", "test", "rabbitmq"],
                        "count": 42,
                    },
                },
            }
            
            rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key="test.complex",
                event=complex_event,
            )
            
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            assert len(received_events) == 1
            received = received_events[0]
            assert received["data"]["nested"]["array"] == [1, 2, 3, 4, 5]
            assert received["data"]["nested"]["object"]["key1"] == "value1"
            assert received["data"]["metadata"]["count"] == 42
        finally:
            # Ensure consuming is stopped
            if consume_thread.is_alive():
                rabbitmq_subscriber.stop_consuming()
                consume_thread.join(timeout=2)

    def test_subscriber_connection(self, rabbitmq_subscriber):
        """Test that subscriber can connect to RabbitMQ."""
        assert rabbitmq_subscriber.connection is not None
        assert rabbitmq_subscriber.channel is not None
        assert not rabbitmq_subscriber.connection.is_closed
        assert rabbitmq_subscriber.queue_name is not None  # Should have generated queue name


@pytest.mark.integration
class TestRabbitMQErrorHandling:
    """Test edge cases and error handling."""

    def test_publish_without_connection(self):
        """Test that publishing fails gracefully without connection."""
        config = get_rabbitmq_config()
        publisher = RabbitMQPublisher(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
        )
        # Don't connect
        
        event = {"event_type": "Test", "data": {}}
        
        # Should raise ConnectionError
        with pytest.raises(ConnectionError):
            publisher.publish(
                exchange=publisher.exchange,
                routing_key="test",
                event=event
            )

    def test_reconnect_publisher(self):
        """Test reconnecting a publisher."""
        config = get_rabbitmq_config()
        publisher = RabbitMQPublisher(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            exchange=config["exchange"],
        )
        
        # Connect
        success = publisher.connect()
        if not success:
            pytest.skip("Could not connect to RabbitMQ")
        
        # Disconnect
        publisher.disconnect()
        
        # Reconnect
        success = publisher.connect()
        assert success is True
        
        # Cleanup
        publisher.disconnect()

    def test_empty_event_data(self, rabbitmq_publisher, rabbitmq_subscriber):
        """Test publishing an event with empty data."""
        received_events = []
        
        def on_test_event(event):
            received_events.append(event)
            rabbitmq_subscriber.stop_consuming()
        
        rabbitmq_subscriber.subscribe("EmptyEvent", on_test_event, routing_key="test.*")
        
        consume_thread = threading.Thread(
            target=rabbitmq_subscriber.start_consuming
        )
        consume_thread.daemon = True
        consume_thread.start()
        
        try:
            time.sleep(SUBSCRIBER_STARTUP_WAIT)
            
            # Publish event with empty data
            event = {
                "event_type": "EmptyEvent",
                "event_id": str(uuid.uuid4()),
                "data": {},
            }
            
            rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key="test.empty",
                event=event,
            )
            
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            assert len(received_events) == 1
            assert received_events[0]["data"] == {}
        finally:
            # Ensure consuming is stopped
            if consume_thread.is_alive():
                rabbitmq_subscriber.stop_consuming()
                consume_thread.join(timeout=2)


@pytest.mark.integration
class TestRabbitMQPersistence:
    """Test message persistence when consumers are down."""

    def test_message_persistence_with_consumer_down(self, rabbitmq_publisher):
        """Test that messages persist when consumer is offline and are delivered when it comes back.
        
        This test verifies:
        1. Messages published to a durable queue with persistent delivery mode survive
        2. Messages are delivered after consumer restart
        3. Queue and messages survive consumer downtime
        """
        config = get_rabbitmq_config()
        
        # Use a unique queue name for this test to avoid interference
        test_queue_name = f"test.persistence.{uuid.uuid4().hex[:8]}"
        routing_key = f"test.persistence.{uuid.uuid4().hex[:8]}"
        
        # Step 1: Declare a durable queue through publisher
        success = rabbitmq_publisher.declare_queue(
            queue_name=test_queue_name,
            routing_key=routing_key,
        )
        assert success is True
        
        # Step 2: Publish messages BEFORE starting any consumer
        test_event_ids = []
        num_messages = 3
        
        for i in range(num_messages):
            event_id = str(uuid.uuid4())
            test_event_ids.append(event_id)
            event = {
                "event_type": "PersistenceTest",
                "event_id": event_id,
                "data": {"index": i, "message": f"Persistence test {i}"},
            }
            
            success = rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key=routing_key,
                event=event,
            )
            assert success is True
        
        # Step 3: Wait a moment to ensure messages are persisted
        time.sleep(1)
        
        # Step 4: NOW start a consumer and verify it receives all messages
        subscriber = RabbitMQSubscriber(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            exchange_name=config["exchange"],
            queue_name=test_queue_name,
            queue_durable=True,
            auto_ack=False,  # Manual ack to ensure proper message handling
        )
        
        try:
            # Connect subscriber
            connected = subscriber.connect()
            assert connected is True
            
            received_events = []
            
            def on_persistence_event(event):
                """Callback to capture received events."""
                received_events.append(event)
                # Stop after receiving all messages
                if len(received_events) >= num_messages:
                    subscriber.stop_consuming()
            
            # Subscribe to persistence test events
            subscriber.subscribe("PersistenceTest", on_persistence_event, routing_key=routing_key)
            
            # Start consuming in a background thread
            consume_thread = threading.Thread(
                target=subscriber.start_consuming
            )
            consume_thread.daemon = True
            consume_thread.start()
            
            # Wait for messages to be received
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            # Verify all messages were received
            assert len(received_events) == num_messages, \
                f"Expected {num_messages} messages, got {len(received_events)}"
            
            # Verify all event IDs were received
            received_ids = [e["event_id"] for e in received_events]
            for expected_id in test_event_ids:
                assert expected_id in received_ids, \
                    f"Expected event ID {expected_id} not found in received messages"
            
            # Verify messages are in order
            for i in range(num_messages):
                assert received_events[i]["data"]["index"] == i, \
                    f"Message {i} has wrong index: {received_events[i]['data']['index']}"
                
        finally:
            # Cleanup
            if consume_thread.is_alive():
                subscriber.stop_consuming()
                consume_thread.join(timeout=2)
            subscriber.disconnect()
            
            # Clean up the test queue
            try:
                rabbitmq_publisher.channel.queue_delete(queue=test_queue_name)
            except (pika.exceptions.ChannelError, pika.exceptions.ConnectionError) as e:
                # Best effort cleanup - queue may not exist or connection may be closed
                logger.warning(f"Failed to delete test queue during cleanup: {e}")

    def test_queue_durability_survives_disconnect(self, rabbitmq_publisher):
        """Test that durable queues persist across subscriber disconnects."""
        config = get_rabbitmq_config()
        
        # Use a unique queue name for this test
        test_queue_name = f"test.durable.{uuid.uuid4().hex[:8]}"
        routing_key = f"test.durable.{uuid.uuid4().hex[:8]}"
        
        # Step 1: Create first subscriber and declare queue
        subscriber1 = RabbitMQSubscriber(
            host=config["host"],
            port=config["port"],
            username=config["username"],
            password=config["password"],
            exchange_name=config["exchange"],
            queue_name=test_queue_name,
            queue_durable=True,
        )
        
        try:
            connected = subscriber1.connect()
            assert connected is True
            
            # Bind the queue
            subscriber1.channel.queue_bind(
                exchange=config["exchange"],
                queue=test_queue_name,
                routing_key=routing_key,
            )
            
            # Step 2: Disconnect first subscriber
            subscriber1.disconnect()
            
            # Step 3: Publish a message to the queue
            event_id = str(uuid.uuid4())
            event = {
                "event_type": "DurabilityTest",
                "event_id": event_id,
                "data": {"message": "Queue should persist"},
            }
            
            success = rabbitmq_publisher.publish(
                exchange=rabbitmq_publisher.exchange,
                routing_key=routing_key,
                event=event,
            )
            assert success is True
            
            # Step 4: Create a new subscriber with the same queue name
            subscriber2 = RabbitMQSubscriber(
                host=config["host"],
                port=config["port"],
                username=config["username"],
                password=config["password"],
                exchange_name=config["exchange"],
                queue_name=test_queue_name,
                queue_durable=True,
                auto_ack=False,
            )
            
            connected = subscriber2.connect()
            assert connected is True
            
            received_events = []
            
            def on_durability_event(event):
                """Callback to capture received events."""
                received_events.append(event)
                subscriber2.stop_consuming()
            
            # Subscribe and consume
            subscriber2.subscribe("DurabilityTest", on_durability_event, routing_key=routing_key)
            
            consume_thread = threading.Thread(
                target=subscriber2.start_consuming
            )
            consume_thread.daemon = True
            consume_thread.start()
            
            # Wait for message
            consume_thread.join(timeout=TEST_TIMEOUT_SECONDS)
            
            # Verify the message was received
            assert len(received_events) == 1
            assert received_events[0]["event_id"] == event_id
            
        finally:
            # Cleanup
            if consume_thread.is_alive():
                subscriber2.stop_consuming()
                consume_thread.join(timeout=2)
            subscriber2.disconnect()
            
            # Clean up the test queue
            try:
                rabbitmq_publisher.channel.queue_delete(queue=test_queue_name)
            except (pika.exceptions.ChannelError, pika.exceptions.ConnectionError) as e:
                # Best effort cleanup - queue may not exist or connection may be closed
                logger.warning(f"Failed to delete test queue during cleanup: {e}")
