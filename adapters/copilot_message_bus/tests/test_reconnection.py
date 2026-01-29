# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for RabbitMQ reconnection logic."""

from unittest.mock import MagicMock, patch

import pytest

try:
    import pika

    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False

from copilot_message_bus.rabbitmq_publisher import RabbitMQPublisher


@pytest.mark.skipif(not PIKA_AVAILABLE, reason="pika not installed")
class TestRabbitMQReconnection:
    """Tests for RabbitMQ automatic reconnection."""

    def test_reconnect_on_channel_closed(self):
        """Test that publisher reconnects when channel is closed."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            max_reconnect_attempts=2,
            reconnect_delay=0.1,
        )

        # Mock connection and channel
        mock_connection = MagicMock()
        mock_channel = MagicMock()

        # Simulate successful initial connection
        with patch.object(pika, "BlockingConnection", return_value=mock_connection):
            mock_connection.channel.return_value = mock_channel
            mock_channel.is_open = True
            mock_connection.is_closed = False

            publisher.connect()  # Should not raise

        # Simulate channel being closed
        mock_channel.is_open = False

        # Mock successful reconnection that restores the channel
        def mock_reconnect_success():
            publisher.connection = mock_connection
            publisher.channel = mock_channel
            mock_channel.is_open = True
            mock_connection.is_closed = False

        # Attempt to publish should detect closed channel and reconnect
        event = {
            "event_type": "TestEvent",
            "event_id": "123",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {},
        }

        with patch.object(publisher, "connect", side_effect=mock_reconnect_success):
            # Should successfully publish after reconnection
            publisher.publish("test.exchange", "test.key", event)

            # Verify channel.basic_publish was called
            assert mock_channel.basic_publish.called

    def test_is_connected_checks_channel_state(self):
        """Test _is_connected properly checks connection and channel state."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

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
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=1.0,  # 1 second delay
        )

        # Mock failed connection
        with patch.object(publisher, "connect", side_effect=Exception("Connection failed")):
            # First reconnect attempt
            result1 = publisher._reconnect()
            assert result1 is False

            # Immediate second attempt should be throttled
            result2 = publisher._reconnect()
            assert result2 is False

            # Verify connect was only called once (throttled on second)
            assert publisher.connect.call_count == 1

    def test_circuit_breaker_time_based_throttling(self):
        """Test circuit breaker respects time delay and allows reconnect after backoff."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=2.0,
        )

        # Mock time and connection
        with patch("copilot_message_bus.rabbitmq_publisher.time.time") as mock_time:
            with patch.object(publisher, "connect", side_effect=Exception("Connection failed")):
                # Start at t=10 (well past the initial _last_reconnect_time of 0)
                mock_time.return_value = 10.0

                # First reconnect attempt at t=10
                result1 = publisher._reconnect()
                assert result1 is False
                assert publisher.connect.call_count == 1

                # Immediate second attempt at t=10 should be throttled
                # Backoff is 2.0 * (2^(0+1)) = 4.0s (count was reset to 1 after first failure)
                # Actually after first attempt, count is 1, so next backoff is 2.0 * (2^(1+1)) = 8.0s
                result2 = publisher._reconnect()
                assert result2 is False
                assert publisher.connect.call_count == 1  # Still only one call

                # Advance time by 7 seconds (still < 8s backoff)
                mock_time.return_value = 17.0
                result3 = publisher._reconnect()
                assert result3 is False
                assert publisher.connect.call_count == 1  # Still throttled

                # Advance time by 9 seconds (> 8s backoff)
                mock_time.return_value = 19.0
                result4 = publisher._reconnect()
                assert result4 is False
                assert publisher.connect.call_count == 2  # Allowed after backoff

    def test_reconnect_limit_enforced(self):
        """Test maximum reconnection attempts are enforced."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            max_reconnect_attempts=2,
            reconnect_delay=0.0,  # No delay for testing
        )

        # Mock failed connection
        with patch.object(publisher, "connect", side_effect=Exception("Connection failed")):
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
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            max_reconnect_attempts=3,
            reconnect_delay=0.0,
        )

        # Simulate failed then successful reconnection
        def mock_connect_sequence():
            """Mock that fails first time, succeeds second time."""
            if publisher._reconnect_count < 2:
                raise Exception("First attempt fails")
            # Second attempt succeeds (returns None)

        with patch.object(publisher, "connect", side_effect=mock_connect_sequence) as mock_connect:
            # First attempt fails
            result1 = publisher._reconnect()
            assert result1 is False
            assert mock_connect.call_count == 1
            assert publisher._reconnect_count == 1

            # Second attempt succeeds
            result2 = publisher._reconnect()
            assert result2 is True
            assert mock_connect.call_count == 2
            assert publisher._reconnect_count == 0  # Reset on success

    def test_reconnect_redeclares_queues(self):
        """Test that reconnection re-declares previously declared queues."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=0.0,
        )

        # Simulate queues being declared
        publisher._declared_queues.add("queue1")
        publisher._declared_queues.add("queue2")

        # Mock successful reconnection
        with patch.object(publisher, "connect"):
            with patch.object(publisher, "declare_queue") as mock_declare:
                result = publisher._reconnect()

                assert result is True
                # Verify queues were re-declared
                assert mock_declare.call_count == 2
                assert any(call[0][0] == "queue1" for call in mock_declare.call_args_list)
                assert any(call[0][0] == "queue2" for call in mock_declare.call_args_list)

    def test_publish_retries_after_reconnection(self):
        """Test that publish retries once after successful reconnection."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
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
            "data": {},
        }

        # First publish fails with channel error, second succeeds
        mock_channel.basic_publish.side_effect = [
            pika.exceptions.ChannelWrongStateError(),
            None,  # Success on retry
        ]

        # Mock successful reconnection
        with patch.object(publisher, "_reconnect", return_value=True):
            # Should not raise exception - retry succeeds
            publisher.publish("test.exchange", "test.key", event)

            # Verify publish was attempted twice
            assert mock_channel.basic_publish.call_count == 2
            # Verify reconnect was called
            assert publisher._reconnect.call_count == 1

    def test_publish_connection_error_and_reconnect_failure(self):
        """Test that publish raises ConnectionError when reconnection fails after a connection error."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
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
            "data": {},
        }

        # Initial publish raises a connection/channel error
        mock_channel.basic_publish.side_effect = pika.exceptions.ChannelWrongStateError()

        # Reconnection attempt fails
        with patch.object(publisher, "_reconnect", return_value=False) as mock_reconnect:
            with pytest.raises(ConnectionError, match="Failed to publish after connection error"):
                publisher.publish("test.exchange", "test.key", event)

            # Verify only one publish attempt (no retry) and reconnect attempted once
            assert mock_channel.basic_publish.call_count == 1
            assert mock_reconnect.call_count == 1

    def test_publish_retry_failure_propagates_exception(self):
        """Test that when reconnection succeeds but retry publish fails, the exception is propagated."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
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
            "data": {},
        }

        # First publish raises connection/channel error, retry raises UnroutableError
        mock_channel.basic_publish.side_effect = [
            pika.exceptions.ChannelWrongStateError(),
            pika.exceptions.UnroutableError([]),
        ]

        # Mock successful reconnection
        with patch.object(publisher, "_reconnect", return_value=True) as mock_reconnect:
            # The retry failure should be propagated to caller
            with pytest.raises(pika.exceptions.UnroutableError):
                publisher.publish("test.exchange", "test.key", event)

            # Verify publish was attempted twice and reconnect occurred once
            assert mock_channel.basic_publish.call_count == 2
            assert mock_reconnect.call_count == 1


@pytest.mark.skipif(not PIKA_AVAILABLE, reason="pika not installed")
class TestRabbitMQSubscriberReconnection:
    """Tests for RabbitMQ subscriber automatic reconnection."""

    def test_subscriber_is_connected_checks_state(self):
        """Test _is_connected properly checks connection and channel state."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        # No connection
        assert subscriber._is_connected() is False

        # Connection but no channel
        subscriber.connection = MagicMock()
        subscriber.connection.is_closed = False
        assert subscriber._is_connected() is False

        # Connection and channel but channel closed
        subscriber.channel = MagicMock()
        subscriber.channel.is_open = False
        assert subscriber._is_connected() is False

        # Both open
        subscriber.channel.is_open = True
        assert subscriber._is_connected() is True

        # Connection closed
        subscriber.connection.is_closed = True
        assert subscriber._is_connected() is False

    def test_subscriber_reconnect_success(self):
        """Test successful subscriber reconnection."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=0.0,
        )

        # Mock successful reconnection
        with patch.object(subscriber, "connect") as mock_connect:
            result = subscriber._reconnect()

            assert result is True
            assert mock_connect.call_count == 1
            assert subscriber._reconnect_count == 0  # Reset on success

    def test_subscriber_reconnect_reestablishes_subscriptions(self):
        """Test that reconnection re-establishes subscriptions."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=0.0,
        )

        # Simulate existing subscriptions
        subscriber._subscriptions = [
            ("EventType1", "event.type1", "test.exchange"),
            ("EventType2", "event.type2", "test.exchange"),
        ]

        # Mock successful connection
        mock_channel = MagicMock()
        subscriber.queue_name = "test-queue"

        def mock_connect():
            subscriber.channel = mock_channel

        with patch.object(subscriber, "connect", side_effect=mock_connect):
            result = subscriber._reconnect()

            assert result is True
            # Verify queue_bind was called for each subscription
            assert mock_channel.queue_bind.call_count == 2

    def test_subscriber_reconnect_with_backoff(self):
        """Test subscriber circuit breaker respects time delay and exponential backoff."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            reconnect_delay=2.0,
        )

        with patch("copilot_message_bus.rabbitmq_subscriber.time.time") as mock_time:
            with patch.object(subscriber, "connect", side_effect=Exception("Connection failed")):
                # Start at t=10
                mock_time.return_value = 10.0

                # First reconnect attempt at t=10
                result1 = subscriber._reconnect()
                assert result1 is False
                assert subscriber.connect.call_count == 1
                assert subscriber._reconnect_count == 1

                # Immediate second attempt at t=10 should be throttled
                result2 = subscriber._reconnect()
                assert result2 is False
                assert subscriber.connect.call_count == 1  # Still only one call

                # Advance time by 5 seconds (past first backoff delay of ~4s with jitter)
                mock_time.return_value = 15.0
                result3 = subscriber._reconnect()
                assert result3 is False
                assert subscriber.connect.call_count == 2  # Second attempt now allowed
                assert subscriber._reconnect_count == 2

                # Advance time by 10 seconds (past second backoff delay of ~8s with jitter)
                mock_time.return_value = 25.0
                result4 = subscriber._reconnect()
                assert result4 is False
                assert subscriber.connect.call_count == 3  # Third attempt now allowed
                assert subscriber._reconnect_count == 3

    def test_subscriber_safe_ack_handles_channel_closure(self):
        """Test _safe_ack catches channel closure exceptions."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        mock_channel = MagicMock()
        mock_channel.basic_ack.side_effect = pika.exceptions.ChannelClosedByBroker(
            reply_code=406, reply_text="PRECONDITION_FAILED"
        )

        # Should not raise exception
        subscriber._safe_ack(mock_channel, 123)
        assert mock_channel.basic_ack.call_count == 1

    def test_subscriber_safe_nack_handles_channel_closure(self):
        """Test _safe_nack catches channel closure exceptions."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        mock_channel = MagicMock()
        mock_channel.basic_nack.side_effect = pika.exceptions.ChannelWrongStateError()

        # Should not raise exception
        subscriber._safe_nack(mock_channel, 123, requeue=True)
        assert mock_channel.basic_nack.call_count == 1

    def test_subscriber_tracks_subscriptions(self):
        """Test that subscribe() tracks subscriptions for reconnection."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        # Mock connection
        mock_channel = MagicMock()
        subscriber.channel = mock_channel
        subscriber.queue_name = "test-queue"

        # Subscribe to multiple events
        subscriber.subscribe("EventType1", lambda e: None, routing_key="event.type1")
        subscriber.subscribe("EventType2", lambda e: None, routing_key="event.type2")

        # Verify subscriptions were tracked
        assert len(subscriber._subscriptions) == 2
        assert ("EventType1", "event.type1", "copilot.events") in subscriber._subscriptions
        assert ("EventType2", "event.type2", "copilot.events") in subscriber._subscriptions

    def test_subscriber_reconnect_limit_enforced(self):
        """Test maximum reconnection attempts are enforced."""
        from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber

        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            max_reconnect_attempts=2,
            reconnect_delay=0.0,
        )

        # Mock failed connection
        with patch.object(subscriber, "connect", side_effect=Exception("Connection failed")):
            # Exhaust reconnection attempts
            subscriber._reconnect()
            subscriber._reconnect()

            # Third attempt should fail due to limit
            result = subscriber._reconnect()
            assert result is False
            # Count should be reset to allow future attempts
            assert subscriber._reconnect_count == 0
