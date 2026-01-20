# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for RabbitMQ heartbeat configuration."""

import unittest.mock as mock

import pytest
from copilot_config.generated.adapters.message_bus import DriverConfig_MessageBus_Rabbitmq
from copilot_message_bus.rabbitmq_publisher import RabbitMQPublisher
from copilot_message_bus.rabbitmq_subscriber import RabbitMQSubscriber


class TestRabbitMQPublisherHeartbeat:
    """Tests for RabbitMQ publisher heartbeat configuration."""

    def test_default_heartbeat_values(self):
        """Test that default heartbeat values are set correctly."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        assert publisher.heartbeat == 300
        assert publisher.blocked_connection_timeout == 600

    def test_custom_heartbeat_values(self):
        """Test that custom heartbeat values are accepted."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            heartbeat=600,
            blocked_connection_timeout=1200,
        )

        assert publisher.heartbeat == 600
        assert publisher.blocked_connection_timeout == 1200

    def test_heartbeat_disabled(self):
        """Test that heartbeat can be disabled by setting to 0."""
        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            heartbeat=0,
            blocked_connection_timeout=0,
        )

        assert publisher.heartbeat == 0
        assert publisher.blocked_connection_timeout == 0

    def test_from_config_with_heartbeat(self):
        """Test that from_config correctly passes heartbeat parameters."""
        config = DriverConfig_MessageBus_Rabbitmq(
            rabbitmq_host="testhost",
            rabbitmq_port=5672,
            rabbitmq_username="testuser",
            rabbitmq_password="testpass",
            heartbeat=450,
            blocked_connection_timeout=900,
        )

        publisher = RabbitMQPublisher.from_config(config)

        assert publisher.host == "testhost"
        assert publisher.heartbeat == 450
        assert publisher.blocked_connection_timeout == 900

    def test_from_config_uses_defaults(self):
        """Test that from_config uses default heartbeat values from config dataclass."""
        config = DriverConfig_MessageBus_Rabbitmq(
            rabbitmq_host="testhost",
            rabbitmq_port=5672,
            rabbitmq_username="testuser",
            rabbitmq_password="testpass",
        )

        publisher = RabbitMQPublisher.from_config(config)

        # Should use the defaults from the DriverConfig dataclass
        assert publisher.heartbeat == 300
        assert publisher.blocked_connection_timeout == 600

    @mock.patch("copilot_message_bus.rabbitmq_publisher.pika")
    def test_connect_with_heartbeat_parameters(self, mock_pika):
        """Test that connect() passes heartbeat parameters to pika.ConnectionParameters."""
        mock_connection = mock.Mock()
        mock_channel = mock.Mock()
        mock_connection.channel.return_value = mock_channel
        mock_pika.BlockingConnection.return_value = mock_connection

        publisher = RabbitMQPublisher(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            heartbeat=450,
            blocked_connection_timeout=900,
        )

        publisher.connect()

        # Verify ConnectionParameters was called with heartbeat parameters
        mock_pika.ConnectionParameters.assert_called_once()
        call_kwargs = mock_pika.ConnectionParameters.call_args.kwargs
        assert call_kwargs["heartbeat"] == 450
        assert call_kwargs["blocked_connection_timeout"] == 900


class TestRabbitMQSubscriberHeartbeat:
    """Tests for RabbitMQ subscriber heartbeat configuration."""

    def test_default_heartbeat_values(self):
        """Test that default heartbeat values are set correctly."""
        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
        )

        assert subscriber.heartbeat == 300
        assert subscriber.blocked_connection_timeout == 600

    def test_custom_heartbeat_values(self):
        """Test that custom heartbeat values are accepted."""
        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            heartbeat=600,
            blocked_connection_timeout=1200,
        )

        assert subscriber.heartbeat == 600
        assert subscriber.blocked_connection_timeout == 1200

    def test_heartbeat_disabled(self):
        """Test that heartbeat can be disabled by setting to 0."""
        subscriber = RabbitMQSubscriber(
            host="localhost",
            port=5672,
            username="guest",
            password="guest",
            heartbeat=0,
            blocked_connection_timeout=0,
        )

        assert subscriber.heartbeat == 0
        assert subscriber.blocked_connection_timeout == 0

    def test_from_config_with_heartbeat(self):
        """Test that from_config correctly passes heartbeat parameters."""
        config = DriverConfig_MessageBus_Rabbitmq(
            rabbitmq_host="testhost",
            rabbitmq_port=5672,
            rabbitmq_username="testuser",
            rabbitmq_password="testpass",
            heartbeat=450,
            blocked_connection_timeout=900,
        )

        subscriber = RabbitMQSubscriber.from_config(config)

        assert subscriber.host == "testhost"
        assert subscriber.heartbeat == 450
        assert subscriber.blocked_connection_timeout == 900

    def test_from_config_uses_defaults(self):
        """Test that from_config uses default heartbeat values from config dataclass."""
        config = DriverConfig_MessageBus_Rabbitmq(
            rabbitmq_host="testhost",
            rabbitmq_port=5672,
            rabbitmq_username="testuser",
            rabbitmq_password="testpass",
        )

        subscriber = RabbitMQSubscriber.from_config(config)

        # Should use the defaults from the DriverConfig dataclass
        assert subscriber.heartbeat == 300
        assert subscriber.blocked_connection_timeout == 600

    def test_connect_with_heartbeat_parameters(self):
        """Test that connect() passes heartbeat parameters to pika.ConnectionParameters."""
        # Import pika within the test since it's imported inside the connect method
        with mock.patch("pika.BlockingConnection") as mock_blocking_connection, mock.patch(
            "pika.ConnectionParameters"
        ) as mock_connection_params, mock.patch("pika.PlainCredentials") as mock_credentials:
            mock_connection = mock.Mock()
            mock_channel = mock.Mock()
            mock_connection.channel.return_value = mock_channel
            mock_connection.is_closed = False
            mock_blocking_connection.return_value = mock_connection

            # Mock queue_declare to return a method with queue attribute
            mock_result = mock.Mock()
            mock_result.method.queue = "test-queue"
            mock_channel.queue_declare.return_value = mock_result

            subscriber = RabbitMQSubscriber(
                host="localhost",
                port=5672,
                username="guest",
                password="guest",
                heartbeat=450,
                blocked_connection_timeout=900,
            )

            subscriber.connect()

            # Verify ConnectionParameters was called with heartbeat parameters
            mock_connection_params.assert_called_once()
            call_kwargs = mock_connection_params.call_args.kwargs
            assert call_kwargs["heartbeat"] == 450
            assert call_kwargs["blocked_connection_timeout"] == 900
