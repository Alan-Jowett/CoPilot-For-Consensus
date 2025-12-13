#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for manage_failed_queues.py

Tests the FailedQueueManager class functionality.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(__file__))

from manage_failed_queues import FailedQueueManager


@pytest.fixture
def mock_connection():
    """Create a mock RabbitMQ connection."""
    connection = MagicMock()
    channel = MagicMock()
    connection.channel.return_value = channel
    connection.is_closed = False
    return connection, channel


@pytest.fixture
def manager(mock_connection):
    """Create a FailedQueueManager instance with mocked connection."""
    connection, channel = mock_connection
    
    manager = FailedQueueManager(
        host="localhost",
        port=5672,
        username="guest",
        password="guest",
    )
    
    # Replace connection with mock
    with patch('pika.BlockingConnection', return_value=connection):
        manager.connect()
    
    return manager


class TestFailedQueueManager:
    """Tests for FailedQueueManager class."""
    
    def test_initialization(self):
        """Test manager initialization with default values."""
        manager = FailedQueueManager()
        
        assert manager.host == "localhost"
        assert manager.port == 5672
        assert manager.username == "guest"
        assert manager.password == "guest"
        assert manager.vhost == "/"
    
    def test_initialization_with_custom_values(self):
        """Test manager initialization with custom values."""
        manager = FailedQueueManager(
            host="rabbitmq",
            port=5673,
            username="admin",
            password="secret",
            vhost="/custom",
        )
        
        assert manager.host == "rabbitmq"
        assert manager.port == 5673
        assert manager.username == "admin"
        assert manager.password == "secret"
        assert manager.vhost == "/custom"
    
    def test_connect(self, mock_connection):
        """Test RabbitMQ connection establishment."""
        connection, channel = mock_connection
        
        manager = FailedQueueManager()
        
        with patch('pika.BlockingConnection', return_value=connection) as mock_block:
            manager.connect()
            
            assert manager.connection is not None
            assert manager.channel is not None
            mock_block.assert_called_once()
    
    def test_disconnect(self, manager):
        """Test disconnection from RabbitMQ."""
        manager.disconnect()
        
        manager.connection.close.assert_called_once()
    
    def test_list_failed_queues(self, manager):
        """Test listing failed queues."""
        # Mock queue_declare responses
        queue_info_mock = MagicMock()
        queue_info_mock.method.message_count = 42
        manager.channel.queue_declare.return_value = queue_info_mock
        
        queues = manager.list_failed_queues()
        
        # Should have all defined failed queues
        assert len(queues) == len(FailedQueueManager.QUEUE_MAPPINGS)
        
        # Check first queue
        assert queues[0]["queue"] in FailedQueueManager.QUEUE_MAPPINGS
        assert queues[0]["message_count"] == 42
    
    def test_inspect_messages(self, manager):
        """Test inspecting messages from a queue."""
        # Mock basic_get to return 2 messages
        message_data = {"event_type": "ParsingFailed", "data": {"error": "test"}}
        message_body = json.dumps(message_data).encode('utf-8')
        
        method_mock = MagicMock()
        method_mock.delivery_tag = 1
        method_mock.exchange = "copilot.events"
        method_mock.routing_key = "parsing.failed"
        method_mock.redelivered = False
        
        properties_mock = MagicMock()
        properties_mock.content_type = "application/json"
        properties_mock.delivery_mode = 2
        properties_mock.timestamp = 1234567890
        
        # Return 2 messages then None
        manager.channel.basic_get.side_effect = [
            (method_mock, properties_mock, message_body),
            (method_mock, properties_mock, message_body),
            (None, None, None),
        ]
        
        messages = manager.inspect_messages("parsing.failed", limit=3, requeue=True)
        
        assert len(messages) == 2
        assert messages[0]["routing_key"] == "parsing.failed"
        assert messages[0]["message"] == message_data
    
    def test_export_messages(self, manager, tmp_path):
        """Test exporting messages to JSON file."""
        # Mock queue info
        queue_info_mock = MagicMock()
        queue_info_mock.method.message_count = 5
        manager.channel.queue_declare.return_value = queue_info_mock
        
        # Mock basic_get to return 2 messages
        message_body = json.dumps({"test": "data"}).encode('utf-8')
        method_mock = MagicMock()
        method_mock.delivery_tag = 1
        method_mock.exchange = "copilot.events"
        method_mock.routing_key = "parsing.failed"
        method_mock.redelivered = False
        
        properties_mock = MagicMock()
        properties_mock.content_type = "application/json"
        properties_mock.delivery_mode = 2
        properties_mock.timestamp = 1234567890
        
        manager.channel.basic_get.side_effect = [
            (method_mock, properties_mock, message_body),
            (method_mock, properties_mock, message_body),
            (None, None, None),
        ]
        
        output_file = tmp_path / "export.json"
        count = manager.export_messages("parsing.failed", str(output_file), limit=3)
        
        assert count == 2
        assert output_file.exists()
        
        # Verify file contents
        with open(output_file) as f:
            data = json.load(f)
        
        assert data["queue"] == "parsing.failed"
        assert data["total_messages_in_queue"] == 5
        assert data["messages_exported"] == 2
        assert len(data["messages"]) == 2
    
    def test_requeue_messages(self, manager):
        """Test requeuing messages to target queue."""
        # Mock queue info
        queue_info_mock = MagicMock()
        queue_info_mock.method.message_count = 3
        manager.channel.queue_declare.return_value = queue_info_mock
        
        # Mock basic_get
        message_body = b'{"test": "data"}'
        method_mock = MagicMock()
        method_mock.delivery_tag = 1
        properties_mock = MagicMock()
        properties_mock.content_type = "application/json"
        
        manager.channel.basic_get.side_effect = [
            (method_mock, properties_mock, message_body),
            (method_mock, properties_mock, message_body),
            (None, None, None),
        ]
        
        count = manager.requeue_messages("parsing.failed", limit=3, dry_run=False)
        
        assert count == 2
        # Verify messages were published
        assert manager.channel.basic_publish.call_count == 2
        # Verify messages were acknowledged
        assert manager.channel.basic_ack.call_count == 2
    
    def test_requeue_messages_dry_run(self, manager):
        """Test requeuing in dry-run mode."""
        # Mock queue info
        queue_info_mock = MagicMock()
        queue_info_mock.method.message_count = 2
        manager.channel.queue_declare.return_value = queue_info_mock
        
        # Mock basic_get
        message_body = b'{"test": "data"}'
        method_mock = MagicMock()
        properties_mock = MagicMock()
        
        manager.channel.basic_get.side_effect = [
            (method_mock, properties_mock, message_body),
            (None, None, None),
        ]
        
        count = manager.requeue_messages("parsing.failed", limit=2, dry_run=True)
        
        assert count == 1
        # Verify no messages were published (dry-run)
        assert manager.channel.basic_publish.call_count == 0
        # Verify messages were nacked (requeued to same queue)
        assert manager.channel.basic_nack.call_count == 1
    
    def test_purge_messages_all(self, manager):
        """Test purging all messages from a queue."""
        # Mock queue_purge
        purge_result = MagicMock()
        purge_result.method.message_count = 100
        manager.channel.queue_purge.return_value = purge_result
        
        count = manager.purge_messages("parsing.failed", limit=None, dry_run=False)
        
        assert count == 100
        manager.channel.queue_purge.assert_called_once_with("parsing.failed")
    
    def test_purge_messages_limited(self, manager):
        """Test purging limited number of messages."""
        # Mock basic_get
        method_mock = MagicMock()
        
        manager.channel.basic_get.side_effect = [
            (method_mock, None, b'data'),
            (method_mock, None, b'data'),
            (None, None, None),
        ]
        
        count = manager.purge_messages("parsing.failed", limit=5, dry_run=False)
        
        assert count == 2
        # Verify basic_get was called (auto_ack=True for purge)
        assert manager.channel.basic_get.call_count == 3
    
    def test_purge_messages_dry_run(self, manager):
        """Test purging in dry-run mode."""
        # Mock queue info for dry-run
        queue_info_mock = MagicMock()
        queue_info_mock.method.message_count = 50
        manager.channel.queue_declare.return_value = queue_info_mock
        
        count = manager.purge_messages("parsing.failed", limit=None, dry_run=True)
        
        assert count == 50
        # Verify queue was not purged
        assert manager.channel.queue_purge.call_count == 0
    
    def test_queue_mappings(self):
        """Test that all expected failed queues are mapped."""
        expected_queues = [
            "archive.ingestion.failed",
            "parsing.failed",
            "chunking.failed",
            "embedding.generation.failed",
            "summarization.failed",
            "orchestration.failed",
            "report.delivery.failed",
        ]
        
        for queue in expected_queues:
            assert queue in FailedQueueManager.QUEUE_MAPPINGS
            assert FailedQueueManager.QUEUE_MAPPINGS[queue] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
