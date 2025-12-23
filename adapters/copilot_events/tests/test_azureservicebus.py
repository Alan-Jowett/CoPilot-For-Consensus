# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus publishers and subscribers."""

import pytest

from copilot_events import (
    create_publisher,
    create_subscriber,
    AzureServiceBusPublisher,
    AzureServiceBusSubscriber,
    EventPublisher,
    EventSubscriber,
)


class TestAzureServiceBusPublisherFactory:
    """Tests for creating Azure Service Bus publishers via factory."""

    def test_create_azureservicebus_publisher_with_connection_string(self):
        """Test creating Azure Service Bus publisher with connection string."""
        publisher = create_publisher(
            message_bus_type="azureservicebus",
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        assert isinstance(publisher, AzureServiceBusPublisher)
        assert isinstance(publisher, EventPublisher)
        assert publisher.connection_string is not None
        assert publisher.queue_name == "test-queue"

    def test_create_azureservicebus_publisher_with_managed_identity(self):
        """Test creating Azure Service Bus publisher with managed identity."""
        publisher = create_publisher(
            message_bus_type="azureservicebus",
            fully_qualified_namespace="test.servicebus.windows.net",
            topic_name="test-topic",
            use_managed_identity=True,
        )

        assert isinstance(publisher, AzureServiceBusPublisher)
        assert publisher.fully_qualified_namespace == "test.servicebus.windows.net"
        assert publisher.topic_name == "test-topic"
        assert publisher.use_managed_identity is True

    def test_create_azureservicebus_publisher_missing_credentials(self):
        """Test error when creating publisher without credentials."""
        with pytest.raises(ValueError, match="Either connection_string or fully_qualified_namespace"):
            create_publisher(message_bus_type="azureservicebus")

    def test_create_azureservicebus_publisher_managed_identity_without_namespace(self):
        """Test error when using managed identity without namespace."""
        with pytest.raises(ValueError, match="Either connection_string or fully_qualified_namespace"):
            create_publisher(
                message_bus_type="azureservicebus",
                use_managed_identity=True,
            )


class TestAzureServiceBusSubscriberFactory:
    """Tests for creating Azure Service Bus subscribers via factory."""

    def test_create_azureservicebus_subscriber_with_queue(self):
        """Test creating Azure Service Bus subscriber for queue."""
        subscriber = create_subscriber(
            message_bus_type="azureservicebus",
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        assert isinstance(subscriber, AzureServiceBusSubscriber)
        assert isinstance(subscriber, EventSubscriber)
        assert subscriber.queue_name == "test-queue"

    def test_create_azureservicebus_subscriber_with_topic_subscription(self):
        """Test creating Azure Service Bus subscriber for topic/subscription."""
        subscriber = create_subscriber(
            message_bus_type="azureservicebus",
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            topic_name="test-topic",
            subscription_name="test-subscription",
        )

        assert isinstance(subscriber, AzureServiceBusSubscriber)
        assert subscriber.topic_name == "test-topic"
        assert subscriber.subscription_name == "test-subscription"

    def test_create_azureservicebus_subscriber_topic_without_subscription(self):
        """Test error when creating subscriber with topic but no subscription."""
        with pytest.raises(ValueError, match="subscription_name is required"):
            create_subscriber(
                message_bus_type="azureservicebus",
                connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                topic_name="test-topic",
            )

    def test_create_azureservicebus_subscriber_without_queue_or_topic(self):
        """Test error when creating subscriber without queue or topic."""
        with pytest.raises(ValueError, match="Either queue_name or topic_name"):
            create_subscriber(
                message_bus_type="azureservicebus",
                connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            )


class TestAzureServiceBusPublisher:
    """Tests for AzureServiceBusPublisher."""

    def test_initialization_with_connection_string(self):
        """Test publisher initialization with connection string."""
        publisher = AzureServiceBusPublisher(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        assert publisher.connection_string is not None
        assert publisher.queue_name == "test-queue"
        assert publisher.use_managed_identity is False

    def test_initialization_with_managed_identity(self):
        """Test publisher initialization with managed identity."""
        publisher = AzureServiceBusPublisher(
            fully_qualified_namespace="test.servicebus.windows.net",
            topic_name="test-topic",
            use_managed_identity=True,
        )

        assert publisher.fully_qualified_namespace == "test.servicebus.windows.net"
        assert publisher.topic_name == "test-topic"
        assert publisher.use_managed_identity is True

    def test_initialization_missing_credentials(self):
        """Test error when initializing without credentials."""
        with pytest.raises(ValueError, match="Either connection_string or fully_qualified_namespace"):
            AzureServiceBusPublisher()

    def test_publish_without_connection(self):
        """Test error when publishing without connection."""
        publisher = AzureServiceBusPublisher(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        with pytest.raises(ConnectionError, match="Not connected"):
            publisher.publish("exchange", "routing.key", {"event_type": "Test"})


class TestAzureServiceBusSubscriber:
    """Tests for AzureServiceBusSubscriber."""

    def test_initialization_with_queue(self):
        """Test subscriber initialization with queue."""
        subscriber = AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        assert subscriber.queue_name == "test-queue"
        assert subscriber.topic_name is None
        assert subscriber.subscription_name is None

    def test_initialization_with_topic_subscription(self):
        """Test subscriber initialization with topic/subscription."""
        subscriber = AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            topic_name="test-topic",
            subscription_name="test-subscription",
        )

        assert subscriber.topic_name == "test-topic"
        assert subscriber.subscription_name == "test-subscription"
        assert subscriber.queue_name is None

    def test_initialization_topic_without_subscription(self):
        """Test error when initializing with topic but no subscription."""
        with pytest.raises(ValueError, match="subscription_name is required"):
            AzureServiceBusSubscriber(
                connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                topic_name="test-topic",
            )

    def test_initialization_without_queue_or_topic(self):
        """Test error when initializing without queue or topic."""
        with pytest.raises(ValueError, match="Either queue_name or topic_name"):
            AzureServiceBusSubscriber(
                connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            )

    def test_subscribe_without_connection(self):
        """Test error when subscribing without connection."""
        subscriber = AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        with pytest.raises(RuntimeError, match="Not connected"):
            subscriber.subscribe("TestEvent", lambda e: None)

    def test_start_consuming_without_connection(self):
        """Test error when starting consumption without connection."""
        subscriber = AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
        )

        with pytest.raises(RuntimeError, match="Not connected"):
            subscriber.start_consuming()


# Note: Integration tests would require an actual Azure Service Bus instance
# and would be similar to test_integration_rabbitmq.py but adapted for Azure
