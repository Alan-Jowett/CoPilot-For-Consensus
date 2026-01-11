# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus publishers and subscribers."""

from unittest.mock import Mock

import pytest
from copilot_config import load_driver_config
from copilot_message_bus import EventPublisher, EventSubscriber, create_publisher, create_subscriber
from copilot_message_bus.azureservicebuspublisher import AzureServiceBusPublisher
from copilot_message_bus.azureservicebussubscriber import AzureServiceBusSubscriber


class TestAzureServiceBusPublisherFactory:
    """Tests for creating Azure Service Bus publishers via factory."""

    def test_create_azureservicebus_publisher_with_connection_string(self):
        """Test creating Azure Service Bus publisher with connection string."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                "queue_name": "test-queue",
            },
        )
        publisher = create_publisher(
            driver_name="azureservicebus",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(publisher, AzureServiceBusPublisher)
        assert isinstance(publisher, EventPublisher)
        assert publisher.connection_string is not None
        assert publisher.queue_name == "test-queue"

    def test_create_azureservicebus_publisher_with_managed_identity(self):
        """Test creating Azure Service Bus publisher with managed identity."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "servicebus_fully_qualified_namespace": "test.servicebus.windows.net",
                "topic_name": "test-topic",
                "servicebus_use_managed_identity": True,
            },
        )
        publisher = create_publisher(
            driver_name="azureservicebus",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(publisher, AzureServiceBusPublisher)
        assert publisher.fully_qualified_namespace == "test.servicebus.windows.net"
        assert publisher.topic_name == "test-topic"
        assert publisher.use_managed_identity is True

    def test_create_azureservicebus_publisher_missing_credentials(self):
        """Test error when creating publisher without credentials."""
        driver_config = load_driver_config(None, "message_bus", "azureservicebus", fields={})
        with pytest.raises(ValueError, match="Either connection_string or fully_qualified_namespace"):
            create_publisher(
                driver_name="azureservicebus",
                driver_config=driver_config,
            )

    def test_create_azureservicebus_publisher_managed_identity_without_namespace(self):
        """Test error when using managed identity without namespace."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={"servicebus_use_managed_identity": True},
        )
        with pytest.raises(ValueError, match="Either connection_string or fully_qualified_namespace"):
            create_publisher(
                driver_name="azureservicebus",
                driver_config=driver_config,
            )


class TestAzureServiceBusSubscriberFactory:
    """Tests for creating Azure Service Bus subscribers via factory."""

    def test_create_azureservicebus_subscriber_with_queue(self):
        """Test creating Azure Service Bus subscriber for queue."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                "queue_name": "test-queue",
            },
        )
        subscriber = create_subscriber(
            driver_name="azureservicebus",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(subscriber, AzureServiceBusSubscriber)
        assert isinstance(subscriber, EventSubscriber)
        assert subscriber.queue_name == "test-queue"

    def test_create_azureservicebus_subscriber_with_topic_subscription(self):
        """Test creating Azure Service Bus subscriber for topic/subscription."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                "topic_name": "test-topic",
                "subscription_name": "test-subscription",
            },
        )
        subscriber = create_subscriber(
            driver_name="azureservicebus",
            driver_config=driver_config,
            enable_validation=False,
        )

        assert isinstance(subscriber, AzureServiceBusSubscriber)
        assert subscriber.topic_name == "test-topic"
        assert subscriber.subscription_name == "test-subscription"

    def test_create_azureservicebus_subscriber_topic_without_subscription(self):
        """Test error when creating subscriber with topic but no subscription."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                "topic_name": "test-topic",
            },
        )
        with pytest.raises(ValueError, match="subscription_name is required"):
            create_subscriber(
                driver_name="azureservicebus",
                driver_config=driver_config,
            )

    def test_create_azureservicebus_subscriber_without_queue_or_topic(self):
        """Test error when creating subscriber without queue or topic."""
        driver_config = load_driver_config(
            None,
            "message_bus",
            "azureservicebus",
            fields={
                "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            },
        )
        with pytest.raises(ValueError, match="Either queue_name or topic_name"):
            create_subscriber(
                driver_name="azureservicebus",
                driver_config=driver_config,
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


def _build_subscriber(auto_complete: bool = False) -> AzureServiceBusSubscriber:
    """Helper to construct a subscriber suitable for unit tests."""
    return AzureServiceBusSubscriber(
        connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
        queue_name="test-queue",
        auto_complete=auto_complete,
    )


class TestAzureServiceBusSubscriberProcessMessage:
    """Unit tests for _process_message decoding and error handling."""

    def test_process_message_decodes_body_sections(self):
        subscriber = _build_subscriber(auto_complete=False)
        mock_msg = Mock()
        mock_msg.body = [b'{"event_type":"Test","value":', b'"abc"}']
        mock_receiver = Mock()
        callback = Mock()
        subscriber.callbacks["Test"] = callback

        subscriber._process_message(mock_msg, mock_receiver)

        callback.assert_called_once()
        mock_receiver.complete_message.assert_called_once_with(mock_msg)

    def test_process_message_handles_invalid_utf8(self):
        subscriber = _build_subscriber(auto_complete=False)
        mock_msg = Mock()
        mock_msg.body = [b"\xff\xff\xff"]
        mock_receiver = Mock()
        callback = Mock()
        subscriber.callbacks["Test"] = callback

        subscriber._process_message(mock_msg, mock_receiver)

        mock_receiver.complete_message.assert_called_once_with(mock_msg)
        callback.assert_not_called()

    def test_process_message_handles_invalid_json(self):
        subscriber = _build_subscriber(auto_complete=False)
        mock_msg = Mock()
        mock_msg.body = [b"not-json"]
        mock_receiver = Mock()
        callback = Mock()
        subscriber.callbacks["Test"] = callback

        subscriber._process_message(mock_msg, mock_receiver)

        mock_receiver.complete_message.assert_called_once_with(mock_msg)
        callback.assert_not_called()

    def test_process_message_auto_complete_true_disables_manual_completion(self):
        """Test that auto_complete=True prevents complete_message from being called."""
        subscriber = _build_subscriber(auto_complete=True)
        mock_msg = Mock()
        mock_msg.body = [b'{"event_type":"Test","value":"abc"}']
        mock_receiver = Mock()
        callback = Mock()
        subscriber.callbacks["Test"] = callback

        subscriber._process_message(mock_msg, mock_receiver)

        callback.assert_called_once()
        mock_receiver.complete_message.assert_not_called()

    def test_process_message_auto_complete_true_no_completion_on_utf8_error(self):
        """Test that auto_complete=True skips complete_message on UTF-8 error."""
        subscriber = _build_subscriber(auto_complete=True)
        mock_msg = Mock()
        mock_msg.body = [b"\xff\xff\xff"]
        mock_receiver = Mock()

        subscriber._process_message(mock_msg, mock_receiver)

        mock_receiver.complete_message.assert_not_called()

    def test_process_message_auto_complete_true_no_completion_on_json_error(self):
        """Test that auto_complete=True skips complete_message on JSON error."""
        subscriber = _build_subscriber(auto_complete=True)
        mock_msg = Mock()
        mock_msg.body = [b"not-json"]
        mock_receiver = Mock()

        subscriber._process_message(mock_msg, mock_receiver)

        mock_receiver.complete_message.assert_not_called()


# Note: Integration tests would require an actual Azure Service Bus instance
# and would be similar to test_integration_rabbitmq.py but adapted for Azure


