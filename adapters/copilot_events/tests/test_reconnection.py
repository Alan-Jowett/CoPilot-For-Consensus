# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for RabbitMQ reconnection logic."""

import pytest
from unittest.mock import Mock, MagicMock, patch

try:
    import pika
    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False

from copilot_events import RabbitMQPublisher


@pytest.mark.skipif(not PIKA_AVAILABLE, reason="pika not installed")
class TestRabbitMQReconnection:
    """Tests for RabbitMQ automatic reconnection."""

    def test_reconnect_on_channel_closed(self):
        """Test that publisher reconnects when channel is closed."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            max_reconnect_attempts=2,
            reconnect_delay=0.1,
        )
        
        # Mock connection and channel
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        
        # Simulate successful initial connection
        with patch.object(pika, 'BlockingConnection', return_value=mock_connection):
            mock_connection.channel.return_value = mock_channel
            mock_channel.is_open = True
            mock_connection.is_closed = False
            
            result = publisher.connect()
            assert result is True
        
        # Simulate channel being closed
        mock_channel.is_open = False
        
        # Mock reconnection
        with patch.object(publisher, 'connect', return_value=True) as mock_connect:
            # Attempt to publish should detect closed channel and reconnect
            event = {
                "event_type": "TestEvent",
                "event_id": "123",
                "timestamp": "2025-01-01T00:00:00Z",
                "version": "1.0",
                "data": {}
            }
            
            # First publish attempt will fail, trigger reconnect
            with patch.object(mock_channel, 'basic_publish') as mock_publish:
                mock_publish.side_effect = pika.exceptions.ChannelWrongStateError()
                
                # After reconnect, second attempt should succeed
                with pytest.raises(ConnectionError):
                    publisher.publish("test.exchange", "test.key", event)
                
                # Verify reconnect was attempted
                assert mock_connect.call_count >= 1

    def test_is_connected_checks_channel_state(self):
        """Test _is_connected properly checks connection and channel state."""
        publisher = RabbitMQPublisher()
        
        # No connection
        assert publisher._is_connected() is False
        
        # Connection but no channel
        publisher.connection = MagicMock()
        publisher.connection.is_closed = False
        assert publisher._is_connected() is False
        
        # Connection and channel but channel closed
        publisher.channel = MagicMock()
        publisher.channel.is_open = False
        assert publisher._is_connected() is False
        
        # Both open
        publisher.channel.is_open = True
        assert publisher._is_connected() is True
        
        # Connection closed
        publisher.connection.is_closed = True
        assert publisher._is_connected() is False

    def test_circuit_breaker_prevents_rapid_reconnects(self):
        """Test circuit breaker throttles reconnection attempts."""
        publisher = RabbitMQPublisher(
            reconnect_delay=1.0,  # 1 second delay
        )
        
        # Mock failed connection
        with patch.object(publisher, 'connect', return_value=False):
            # First reconnect attempt
            result1 = publisher._reconnect()
            assert result1 is False
            
            # Immediate second attempt should be throttled
            result2 = publisher._reconnect()
            assert result2 is False
            
            # Verify connect was only called once (throttled on second)
            assert publisher.connect.call_count == 1

    def test_reconnect_limit_enforced(self):
        """Test maximum reconnection attempts are enforced."""
        publisher = RabbitMQPublisher(
            max_reconnect_attempts=2,
            reconnect_delay=0.0,  # No delay for testing
        )
        
        # Mock failed connection
        with patch.object(publisher, 'connect', return_value=False):
            # Exhaust reconnection attempts
            publisher._reconnect()
            publisher._reconnect()
            
            # Third attempt should fail due to limit
            result = publisher._reconnect()
            assert result is False
            assert publisher._reconnect_count >= publisher.max_reconnect_attempts

    def test_reconnect_resets_count_on_success(self):
        """Test reconnection count resets after successful reconnect."""
        publisher = RabbitMQPublisher(
            max_reconnect_attempts=3,
            reconnect_delay=0.0,
        )
        
        # Simulate failed then successful reconnection
        with patch.object(publisher, 'connect', side_effect=[False, True]):
            # First attempt fails
            result1 = publisher._reconnect()
            assert result1 is False
            assert publisher._reconnect_count == 1
            
            # Second attempt succeeds
            result2 = publisher._reconnect()
            assert result2 is True
            assert publisher._reconnect_count == 0  # Reset on success

    def test_reconnect_redeclares_queues(self):
        """Test that reconnection re-declares previously declared queues."""
        publisher = RabbitMQPublisher(
            reconnect_delay=0.0,
        )
        
        # Simulate queues being declared
        publisher._declared_queues.add("queue1")
        publisher._declared_queues.add("queue2")
        
        # Mock successful reconnection
        with patch.object(publisher, 'connect', return_value=True):
            with patch.object(publisher, 'declare_queue', return_value=True) as mock_declare:
                result = publisher._reconnect()
                
                assert result is True
                # Verify queues were re-declared
                assert mock_declare.call_count == 2
                assert any(call[0][0] == "queue1" for call in mock_declare.call_args_list)
                assert any(call[0][0] == "queue2" for call in mock_declare.call_args_list)

    def test_publish_retries_after_reconnection(self):
        """Test that publish retries once after successful reconnection."""
        publisher = RabbitMQPublisher(
            reconnect_delay=0.0,
        )
        
        # Mock connection and channel
        mock_connection = MagicMock()
        mock_channel = MagicMock()
        publisher.connection = mock_connection
        publisher.channel = mock_channel
        mock_connection.is_closed = False
        mock_channel.is_open = True
        
        event = {
            "event_type": "TestEvent",
            "event_id": "123",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {}
        }
        
        # First publish fails with channel error, second succeeds
        mock_channel.basic_publish.side_effect = [
            pika.exceptions.ChannelWrongStateError(),
            None,  # Success on retry
        ]
        
        # Mock successful reconnection
        with patch.object(publisher, '_reconnect', return_value=True):
            # Should not raise exception - retry succeeds
            publisher.publish("test.exchange", "test.key", event)
            
            # Verify publish was attempted twice
            assert mock_channel.basic_publish.call_count == 2
            # Verify reconnect was called
            assert publisher._reconnect.call_count == 1
