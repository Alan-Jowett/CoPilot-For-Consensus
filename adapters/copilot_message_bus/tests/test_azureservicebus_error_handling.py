# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus error handling, especially AttributeError scenarios."""

import json
import threading
import time
from unittest.mock import Mock, patch

import pytest
from copilot_message_bus.azureservicebussubscriber import AzureServiceBusSubscriber


class TestAzureServiceBusAttributeErrorHandling:
    """Test error handling for AttributeError scenarios in Azure Service Bus.

    These tests cover the known azure-servicebus SDK bug where internal handlers
    can become None during message processing (GitHub issues #35618, #36334).
    """

    @pytest.fixture
    def subscriber(self):
        """Create a test subscriber instance."""
        return AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
            auto_complete=False,
        )

    @pytest.fixture
    def mock_receiver(self):
        """Create a mock receiver."""
        receiver = Mock()
        receiver.complete_message = Mock()
        receiver.abandon_message = Mock()
        return receiver

    @pytest.fixture
    def mock_message(self):
        """Create a mock Service Bus message."""
        msg = Mock()
        msg.body = [json.dumps({"event_type": "test.event", "event_id": "123"}).encode("utf-8")]
        return msg

    def test_process_message_handles_complete_attributeerror(self, subscriber, mock_receiver, mock_message):
        """Test that AttributeError on complete_message is logged and handled gracefully."""
        # Setup: receiver.complete_message raises AttributeError
        mock_receiver.complete_message.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")

        # Register a callback
        callback = Mock()
        subscriber.callbacks["test.event"] = callback

        # Process message should not raise - AttributeError is caught and logged
        with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
            subscriber._process_message(mock_message, mock_receiver)

            # Verify callback was called
            callback.assert_called_once()

            # Verify error was logged
            assert mock_logger.error.called
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "receiver AttributeError" in str(call)]
            assert len(error_calls) > 0

            # Verify warning about redelivery was logged
            assert mock_logger.warning.called
            warning_calls = [call for call in mock_logger.warning.call_args_list
                           if "will be redelivered" in str(call)]
            assert len(warning_calls) > 0

    def test_process_message_handles_abandon_attributeerror(self, subscriber, mock_receiver, mock_message):
        """Test that AttributeError on abandon_message is logged and doesn't crash."""
        # Setup: callback raises exception, abandon raises AttributeError
        callback = Mock(side_effect=ValueError("Processing failed"))
        subscriber.callbacks["test.event"] = callback
        mock_receiver.abandon_message.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")

        # Process message should not crash despite AttributeError on abandon
        with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
            with pytest.raises(ValueError):  # Original exception is re-raised
                subscriber._process_message(mock_message, mock_receiver)

            # Verify error was logged
            assert mock_logger.error.called
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "Cannot abandon message" in str(call)]
            assert len(error_calls) > 0

    def test_process_message_handles_complete_attributeerror_no_callback(self, subscriber, mock_receiver, mock_message):
        """Test AttributeError handling when no callback is registered."""
        # Setup: no callback registered, complete raises AttributeError
        mock_receiver.complete_message.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")

        # Process message should log but not crash
        with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
            subscriber._process_message(mock_message, mock_receiver)

            # Verify error was logged
            assert mock_logger.error.called
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "receiver AttributeError" in str(call)]
            assert len(error_calls) > 0

    def test_process_message_handles_complete_attributeerror_no_event_type(self, subscriber, mock_receiver):
        """Test AttributeError handling for messages without event_type."""
        # Setup: message without event_type, complete raises AttributeError
        msg = Mock()
        msg.body = [json.dumps({"data": "test"}).encode("utf-8")]
        mock_receiver.complete_message.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")

        # Process message should log but not crash
        with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
            subscriber._process_message(msg, mock_receiver)

            # Verify error was logged
            assert mock_logger.error.called
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "receiver AttributeError" in str(call)]
            assert len(error_calls) > 0

    def test_process_message_in_auto_complete_mode_doesnt_call_complete(self, mock_message):
        """Test that in auto_complete mode, complete_message is not called."""
        # Create subscriber with auto_complete enabled
        subscriber = AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
            auto_complete=True,
        )

        receiver = Mock()
        callback = Mock()
        subscriber.callbacks["test.event"] = callback

        # Process message
        subscriber._process_message(mock_message, receiver)

        # Verify complete_message was not called (auto_complete mode)
        receiver.complete_message.assert_not_called()
        receiver.abandon_message.assert_not_called()

    def test_start_consuming_handles_receive_attributeerror(self, subscriber):
        """Test that AttributeError during receive_messages is logged and handled."""
        # Mock the client and receiver
        mock_client = Mock()
        subscriber.client = mock_client

        mock_receiver = Mock()
        mock_receiver.__enter__ = Mock(return_value=mock_receiver)
        mock_receiver.__exit__ = Mock(return_value=False)
        mock_receiver.receive_messages.side_effect = [
            AttributeError("'NoneType' object has no attribute 'flow'"),
            [],  # Empty list to allow graceful exit
        ]
        mock_client.get_queue_receiver.return_value = mock_receiver

        # Start consuming should handle the error and continue
        with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
            with patch("copilot_message_bus.azureservicebussubscriber.ServiceBusReceiveMode", Mock()):
                # Stop after first error to avoid infinite loop
                def stop_after_delay():
                    time.sleep(0.1)
                    subscriber.stop_consuming()
                thread = threading.Thread(target=stop_after_delay)
                thread.start()

                subscriber.start_consuming()
                thread.join()

            # Verify error was logged
            error_calls = [call for call in mock_logger.error.call_args_list
                          if "AttributeError" in str(call)]
            assert len(error_calls) > 0


class TestAzureServiceBusAutoLockRenewerErrorHandling:
    """Test error handling for AutoLockRenewer AttributeError scenarios."""

    @pytest.fixture
    def subscriber(self):
        """Create a test subscriber instance with auto-lock renewal enabled."""
        return AzureServiceBusSubscriber(
            connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
            queue_name="test-queue",
            auto_complete=False,
            max_auto_lock_renewal_duration=60,  # Enable auto-lock renewal
        )

    def test_renewer_register_handles_attributeerror(self, subscriber):
        """Test that AttributeError on renewer.register is logged and handled."""
        # Mock the client and receiver
        mock_client = Mock()
        subscriber.client = mock_client

        mock_receiver = Mock()
        mock_receiver.__enter__ = Mock(return_value=mock_receiver)
        mock_receiver.__exit__ = Mock(return_value=False)

        mock_message = Mock()
        mock_message.body = [json.dumps({"event_type": "test.event", "event_id": "123"}).encode("utf-8")]

        mock_receiver.receive_messages.return_value = [mock_message]
        mock_client.get_queue_receiver.return_value = mock_receiver

        # Mock AutoLockRenewer
        with patch("copilot_message_bus.azureservicebussubscriber.AutoLockRenewer") as MockRenewer:
            mock_renewer = Mock()
            mock_renewer.register.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")
            mock_renewer.close = Mock()
            MockRenewer.return_value = mock_renewer

            with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
                with patch("copilot_message_bus.azureservicebussubscriber.ServiceBusReceiveMode", Mock()):
                    # Register a callback
                    callback = Mock()
                    subscriber.callbacks["test.event"] = callback

                    # Stop after processing one batch
                    def stop_after_delay():
                        time.sleep(0.1)
                        subscriber.stop_consuming()
                    thread = threading.Thread(target=stop_after_delay)
                    thread.start()

                    subscriber.start_consuming()
                    thread.join()

                # Verify error was logged
                error_calls = [call for call in mock_logger.error.call_args_list
                              if "AutoLockRenewer AttributeError" in str(call)]
                assert len(error_calls) > 0

                # Verify callback was still called
                callback.assert_called()

    def test_renewer_close_handles_attributeerror(self, subscriber):
        """Test that AttributeError on renewer.close is logged and handled."""
        # Mock the client and receiver
        mock_client = Mock()
        subscriber.client = mock_client

        mock_receiver = Mock()
        mock_receiver.__enter__ = Mock(return_value=mock_receiver)
        mock_receiver.__exit__ = Mock(return_value=False)
        mock_receiver.receive_messages.return_value = []  # Empty to exit quickly
        mock_client.get_queue_receiver.return_value = mock_receiver

        # Mock AutoLockRenewer with close raising AttributeError
        with patch("copilot_message_bus.azureservicebussubscriber.AutoLockRenewer") as MockRenewer:
            mock_renewer = Mock()
            mock_renewer.register = Mock()
            mock_renewer.close.side_effect = AttributeError("'NoneType' object has no attribute 'flow'")
            MockRenewer.return_value = mock_renewer

            with patch("copilot_message_bus.azureservicebussubscriber.logger") as mock_logger:
                with patch("copilot_message_bus.azureservicebussubscriber.ServiceBusReceiveMode", Mock()):
                    # Stop immediately
                    def stop_after_delay():
                        time.sleep(0.05)
                        subscriber.stop_consuming()
                    thread = threading.Thread(target=stop_after_delay)
                    thread.start()

                    subscriber.start_consuming()
                    thread.join()

                # Verify error was logged as debug (expected during cleanup)
                debug_calls = [call for call in mock_logger.debug.call_args_list
                              if "AutoLockRenewer AttributeError during close" in str(call)]
                assert len(debug_calls) > 0
