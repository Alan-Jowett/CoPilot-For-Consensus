# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for Azure Service Bus publisher and subscriber.

These tests require an actual Azure Service Bus namespace and will be skipped
if the required environment variables are not set.

Required environment variables:
    - AZURE_SERVICEBUS_CONNECTION_STRING: Connection string for Azure Service Bus
    - AZURE_SERVICEBUS_QUEUE_NAME: Name of test queue
    OR
    - AZURE_SERVICEBUS_NAMESPACE: Fully qualified namespace (for managed identity)
    - AZURE_SERVICEBUS_QUEUE_NAME: Name of test queue

Optional environment variables:
    - AZURE_SERVICEBUS_TOPIC_NAME: Name of test topic
    - AZURE_SERVICEBUS_SUBSCRIPTION_NAME: Name of test subscription
"""

import os
import time
import threading
import pytest
import uuid

from copilot_events import (
    AzureServiceBusPublisher,
    AzureServiceBusSubscriber,
)

# Test timing constants
SUBSCRIBER_STARTUP_WAIT = 2  # seconds to wait for subscriber to start
TEST_TIMEOUT_SECONDS = 30  # seconds to wait for test completion


def get_azureservicebus_config():
    """Get Azure Service Bus configuration from environment variables."""
    connection_string = os.getenv("AZURE_SERVICEBUS_CONNECTION_STRING")
    namespace = os.getenv("AZURE_SERVICEBUS_NAMESPACE")
    
    if not connection_string and not namespace:
        return None
    
    return {
        "connection_string": connection_string,
        "fully_qualified_namespace": namespace,
        "queue_name": os.getenv("AZURE_SERVICEBUS_QUEUE_NAME", "copilot-events-test"),
        "topic_name": os.getenv("AZURE_SERVICEBUS_TOPIC_NAME"),
        "subscription_name": os.getenv("AZURE_SERVICEBUS_SUBSCRIPTION_NAME"),
        "use_managed_identity": bool(namespace and not connection_string),
    }


@pytest.fixture(scope="module")
def azureservicebus_config():
    """Get Azure Service Bus configuration or skip tests."""
    config = get_azureservicebus_config()
    if not config:
        pytest.skip(
            "Azure Service Bus credentials not configured - "
            "set AZURE_SERVICEBUS_CONNECTION_STRING or AZURE_SERVICEBUS_NAMESPACE"
        )
    return config


@pytest.fixture(scope="module")
def azureservicebus_publisher(azureservicebus_config):
    """Create and connect to an Azure Service Bus publisher for integration tests."""
    config = azureservicebus_config
    
    publisher = AzureServiceBusPublisher(
        connection_string=config.get("connection_string"),
        fully_qualified_namespace=config.get("fully_qualified_namespace"),
        queue_name=config.get("queue_name"),
        topic_name=config.get("topic_name"),
        use_managed_identity=config.get("use_managed_identity", False),
    )
    
    # Attempt to connect with retries
    max_retries = 3
    for i in range(max_retries):
        try:
            publisher.connect()
            break
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                pytest.skip(f"Could not connect to Azure Service Bus: {e}")
    
    yield publisher
    
    # Cleanup
    publisher.disconnect()


@pytest.fixture
def azureservicebus_subscriber(azureservicebus_config):
    """Create an Azure Service Bus subscriber for integration tests."""
    config = azureservicebus_config
    
    # Use topic/subscription if configured, otherwise use queue
    if config.get("topic_name") and config.get("subscription_name"):
        subscriber = AzureServiceBusSubscriber(
            connection_string=config.get("connection_string"),
            fully_qualified_namespace=config.get("fully_qualified_namespace"),
            topic_name=config["topic_name"],
            subscription_name=config["subscription_name"],
            use_managed_identity=config.get("use_managed_identity", False),
            max_wait_time=3,
        )
    else:
        subscriber = AzureServiceBusSubscriber(
            connection_string=config.get("connection_string"),
            fully_qualified_namespace=config.get("fully_qualified_namespace"),
            queue_name=config["queue_name"],
            use_managed_identity=config.get("use_managed_identity", False),
            max_wait_time=3,
        )
    
    # Attempt to connect with retries
    max_retries = 3
    for i in range(max_retries):
        try:
            subscriber.connect()
            break
        except Exception as e:
            if i < max_retries - 1:
                time.sleep(2)
            else:
                pytest.skip(f"Could not connect to Azure Service Bus: {e}")
    
    yield subscriber
    
    # Cleanup
    subscriber.disconnect()


@pytest.mark.integration
class TestAzureServiceBusIntegration:
    """Integration tests for Azure Service Bus publisher and subscriber."""

    def test_publisher_connection(self, azureservicebus_publisher):
        """Test that publisher can connect successfully."""
        assert azureservicebus_publisher.client is not None

    def test_subscriber_connection(self, azureservicebus_subscriber):
        """Test that subscriber can connect successfully."""
        assert azureservicebus_subscriber.client is not None

    def test_publish_and_receive_event(
        self, azureservicebus_publisher, azureservicebus_subscriber
    ):
        """Test publishing an event and receiving it."""
        # Track received events
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        # Subscribe to test event
        azureservicebus_subscriber.subscribe("TestEvent", callback)
        
        # Start subscriber in a thread
        subscriber_thread = threading.Thread(
            target=azureservicebus_subscriber.start_consuming,
            daemon=True,
        )
        subscriber_thread.start()
        
        # Give subscriber time to start
        time.sleep(SUBSCRIBER_STARTUP_WAIT)
        
        # Publish test event
        test_event = {
            "event_type": "TestEvent",
            "event_id": str(uuid.uuid4()),
            "timestamp": "2025-12-21T00:00:00Z",
            "version": "1.0",
            "data": {"test_key": "test_value"},
        }
        
        azureservicebus_publisher.publish(
            exchange="copilot.events",
            routing_key="test.event",
            event=test_event,
        )
        
        # Wait for event to be received
        timeout_at = time.time() + TEST_TIMEOUT_SECONDS
        while len(received_events) == 0 and time.time() < timeout_at:
            time.sleep(0.5)
        
        # Stop subscriber
        azureservicebus_subscriber.stop_consuming()
        subscriber_thread.join(timeout=5)
        
        # Verify event was received
        assert len(received_events) == 1
        received_event = received_events[0]
        assert received_event["event_type"] == "TestEvent"
        assert received_event["event_id"] == test_event["event_id"]
        assert received_event["data"]["test_key"] == "test_value"

    def test_publish_multiple_events(
        self, azureservicebus_publisher, azureservicebus_subscriber
    ):
        """Test publishing multiple events."""
        # Track received events
        received_events = []
        
        def callback(event):
            received_events.append(event)
        
        # Subscribe to test event
        azureservicebus_subscriber.subscribe("MultiTestEvent", callback)
        
        # Start subscriber in a thread
        subscriber_thread = threading.Thread(
            target=azureservicebus_subscriber.start_consuming,
            daemon=True,
        )
        subscriber_thread.start()
        
        # Give subscriber time to start
        time.sleep(SUBSCRIBER_STARTUP_WAIT)
        
        # Publish multiple test events
        num_events = 5
        for i in range(num_events):
            test_event = {
                "event_type": "MultiTestEvent",
                "event_id": str(uuid.uuid4()),
                "timestamp": "2025-12-21T00:00:00Z",
                "version": "1.0",
                "data": {"sequence": i},
            }
            
            azureservicebus_publisher.publish(
                exchange="copilot.events",
                routing_key="test.multi",
                event=test_event,
            )
        
        # Wait for events to be received
        timeout_at = time.time() + TEST_TIMEOUT_SECONDS
        while len(received_events) < num_events and time.time() < timeout_at:
            time.sleep(0.5)
        
        # Stop subscriber
        azureservicebus_subscriber.stop_consuming()
        subscriber_thread.join(timeout=5)
        
        # Verify events were received
        assert len(received_events) == num_events
        sequences = [e["data"]["sequence"] for e in received_events]
        assert sorted(sequences) == list(range(num_events))
