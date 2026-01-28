# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus retry logic for SSL EOF and connection errors."""

from unittest.mock import Mock, patch

import pytest
from copilot_message_bus.azureservicebuspublisher import AzureServiceBusPublisher


class TestAzureServiceBusPublisherRetryLogic:
    """Test retry logic for Azure Service Bus publisher."""

    @pytest.fixture
    def publisher(self):
        """Create a test publisher instance with retry configuration."""
        return AzureServiceBusPublisher(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            topic_name="test-topic",
            retry_attempts=3,
            retry_backoff_seconds=0.1,  # Short for testing
        )

    @pytest.fixture
    def mock_servicebus_client(self):
        """Create a mock ServiceBusClient."""
        return Mock()

    def test_connect_retries_on_ssl_eof_error(self, publisher):
        """Test that connect retries on SSL EOF errors."""
        # Mock the ServiceBusClient to raise SSL EOF error twice, then succeed
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusClient") as MockClient:
            mock_client_instance = Mock()
            
            # First two calls raise SSL EOF error, third succeeds
            ssl_error = ConnectionError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
            MockClient.from_connection_string.side_effect = [
                ssl_error,
                ssl_error,
                mock_client_instance,
            ]

            # Connect should succeed after retries
            with patch("copilot_message_bus.azureservicebuspublisher.time.sleep") as mock_sleep:
                publisher.connect()

            # Verify retries occurred
            assert MockClient.from_connection_string.call_count == 3
            # Verify exponential backoff (0.1 * 2^0 = 0.1, 0.1 * 2^1 = 0.2)
            assert mock_sleep.call_count == 2
            mock_sleep.assert_any_call(0.1)
            mock_sleep.assert_any_call(0.2)
            
            # Verify connection succeeded
            assert publisher.client == mock_client_instance

    def test_connect_fails_after_max_retries(self, publisher):
        """Test that connect fails after exhausting all retry attempts."""
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusClient") as MockClient:
            ssl_error = ConnectionError("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
            MockClient.from_connection_string.side_effect = ssl_error

            with patch("copilot_message_bus.azureservicebuspublisher.time.sleep"):
                with pytest.raises(ConnectionError, match="SSL: UNEXPECTED_EOF_WHILE_READING"):
                    publisher.connect()

            # Verify all retry attempts were made (initial + 3 retries = 4 total)
            assert MockClient.from_connection_string.call_count == 4

    def test_connect_does_not_retry_non_transient_errors(self, publisher):
        """Test that connect does not retry non-transient errors like ValueError."""
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusClient") as MockClient:
            value_error = ValueError("Invalid connection string format")
            MockClient.from_connection_string.side_effect = value_error

            with pytest.raises(ValueError, match="Invalid connection string"):
                publisher.connect()

            # Verify only one attempt was made (no retries)
            assert MockClient.from_connection_string.call_count == 1

    def test_publish_retries_on_servicebus_connection_error(self, publisher):
        """Test that publish retries on ServiceBusConnectionError."""
        # Setup connected publisher
        mock_client = Mock()
        publisher.client = mock_client
        
        # Mock sender to raise connection error twice, then succeed
        mock_sender = Mock()
        mock_sender.__enter__ = Mock(return_value=mock_sender)
        mock_sender.__exit__ = Mock(return_value=False)
        
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusConnectionError") as MockConnectionError:
            # Create a mock exception class
            class MockServiceBusConnectionError(Exception):
                pass
            
            MockConnectionError.side_effect = lambda msg: MockServiceBusConnectionError(msg)
            
            # Make isinstance return True for our mock exception
            def mock_isinstance(obj, cls):
                if cls == MockConnectionError:
                    return isinstance(obj, MockServiceBusConnectionError)
                return isinstance(obj, cls)
            
            conn_error = MockServiceBusConnectionError("Connection lost due to SSL EOF")
            
            # First two send_messages calls fail, third succeeds
            mock_sender.send_messages.side_effect = [
                conn_error,
                conn_error,
                None,  # Success
            ]
            
            mock_client.get_topic_sender.return_value = mock_sender

            event = {"event_type": "test.event", "data": {"test": "value"}}

            with patch("copilot_message_bus.azureservicebuspublisher.time.sleep") as mock_sleep:
                with patch("copilot_message_bus.azureservicebuspublisher.isinstance", side_effect=mock_isinstance):
                    publisher.publish("test-exchange", "test.route", event)

            # Verify retries occurred
            assert mock_sender.send_messages.call_count == 3
            assert mock_sleep.call_count == 2

    def test_publish_fails_after_max_retries(self, publisher):
        """Test that publish fails after exhausting all retry attempts."""
        mock_client = Mock()
        publisher.client = mock_client
        
        mock_sender = Mock()
        mock_sender.__enter__ = Mock(return_value=mock_sender)
        mock_sender.__exit__ = Mock(return_value=False)
        
        # Always raise connection error
        conn_error = ConnectionError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
        mock_sender.send_messages.side_effect = conn_error
        mock_client.get_topic_sender.return_value = mock_sender

        event = {"event_type": "test.event", "data": {"test": "value"}}

        with patch("copilot_message_bus.azureservicebuspublisher.time.sleep"):
            with pytest.raises(ConnectionError, match="SSL: UNEXPECTED_EOF_WHILE_READING"):
                publisher.publish("test-exchange", "test.route", event)

        # Verify all retry attempts were made (initial + 3 retries = 4 total)
        assert mock_sender.send_messages.call_count == 4

    def test_publish_does_not_retry_non_transient_errors(self, publisher):
        """Test that publish does not retry non-transient errors."""
        mock_client = Mock()
        publisher.client = mock_client
        
        mock_sender = Mock()
        mock_sender.__enter__ = Mock(return_value=mock_sender)
        mock_sender.__exit__ = Mock(return_value=False)
        
        # ValueError is non-transient
        value_error = ValueError("Invalid message format")
        mock_sender.send_messages.side_effect = value_error
        mock_client.get_topic_sender.return_value = mock_sender

        event = {"event_type": "test.event", "data": {"test": "value"}}

        with pytest.raises(ValueError, match="Invalid message format"):
            publisher.publish("test-exchange", "test.route", event)

        # Verify only one attempt was made (no retries)
        assert mock_sender.send_messages.call_count == 1

    def test_is_transient_error_identifies_ssl_errors(self, publisher):
        """Test that _is_transient_error correctly identifies SSL/connection errors."""
        # SSL EOF error
        assert publisher._is_transient_error(ConnectionError("[SSL: UNEXPECTED_EOF_WHILE_READING]"))
        
        # Connection reset
        assert publisher._is_transient_error(ConnectionError("Connection reset by peer"))
        
        # Socket errors
        assert publisher._is_transient_error(OSError("socket error"))
        
        # Timeout
        assert publisher._is_transient_error(TimeoutError("Connection timeout"))
        
        # Non-transient errors
        assert not publisher._is_transient_error(ValueError("Invalid input"))
        assert not publisher._is_transient_error(KeyError("Missing key"))

    def test_retry_disabled_when_retry_attempts_zero(self):
        """Test that retry is disabled when retry_attempts is set to 0."""
        publisher = AzureServiceBusPublisher(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            topic_name="test-topic",
            retry_attempts=0,  # Disable retry
        )
        
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusClient") as MockClient:
            ssl_error = ConnectionError("[SSL: UNEXPECTED_EOF_WHILE_READING]")
            MockClient.from_connection_string.side_effect = ssl_error

            with pytest.raises(ConnectionError):
                publisher.connect()

            # Verify only one attempt was made (no retries)
            assert MockClient.from_connection_string.call_count == 1

    def test_websockets_transport_type(self):
        """Test that WebSockets transport type is configured correctly."""
        publisher = AzureServiceBusPublisher(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            transport_type="websockets",
        )
        
        assert publisher.transport_type == "websockets"
        
        with patch("copilot_message_bus.azureservicebuspublisher.ServiceBusClient") as MockClient:
            with patch("copilot_message_bus.azureservicebuspublisher.TransportType") as MockTransportType:
                MockTransportType.AmqpOverWebsocket = "websocket_transport"
                mock_client = Mock()
                MockClient.from_connection_string.return_value = mock_client
                
                publisher.connect()
                
                # Verify WebSockets transport was used
                MockClient.from_connection_string.assert_called_once()
                call_kwargs = MockClient.from_connection_string.call_args[1]
                assert "transport_type" in call_kwargs
                assert call_kwargs["transport_type"] == "websocket_transport"


class TestAzureServiceBusPublisherConfig:
    """Test configuration handling for retry settings."""

    def test_from_config_with_retry_settings(self):
        """Test creating publisher from config with retry settings."""
        from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_AzureServiceBus
        
        config = DriverConfig_MessageBus_AzureServiceBus(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            topic_name="test-topic",
            retry_attempts=5,
            retry_backoff_seconds=2.0,
            transport_type="websockets",
        )
        
        publisher = AzureServiceBusPublisher.from_config(config)
        
        assert publisher.retry_attempts == 5
        assert publisher.retry_backoff_seconds == 2.0
        assert publisher.transport_type == "websockets"

    def test_from_config_uses_defaults(self):
        """Test that from_config uses default retry values from schema."""
        from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_AzureServiceBus
        
        config = DriverConfig_MessageBus_AzureServiceBus(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
        )
        
        publisher = AzureServiceBusPublisher.from_config(config)
        
        # Verify defaults from schema
        assert publisher.retry_attempts == 3
        assert publisher.retry_backoff_seconds == 1.0
        assert publisher.transport_type == "amqp"
