#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Unit tests for verify_rabbitmq_persistence.py script.

Can be run standalone or via pytest:
    python scripts/test_verify_rabbitmq_persistence.py
    pytest scripts/test_verify_rabbitmq_persistence.py
"""

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

import verify_rabbitmq_persistence


class TestVerifyRabbitMQPersistence(unittest.TestCase):
    """Test cases for RabbitMQ persistence verification script."""

    def test_load_definitions_valid_json(self):
        """Test loading valid definitions JSON."""
        mock_json = json.dumps({
            "queues": [
                {"name": "test.queue", "durable": True, "auto_delete": False}
            ],
            "exchanges": [
                {"name": "test.exchange", "durable": True, "auto_delete": False}
            ]
        })
        
        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = verify_rabbitmq_persistence.load_definitions(Path('/fake/path'))
        
        self.assertEqual(len(result['queues']), 1)
        self.assertEqual(result['queues'][0]['name'], 'test.queue')
        self.assertEqual(len(result['exchanges']), 1)
        self.assertEqual(result['exchanges'][0]['name'], 'test.exchange')

    def test_verify_definitions_file_all_durable(self):
        """Test that verification passes when all queues/exchanges are durable."""
        definitions = {
            "queues": [
                {"name": "queue1", "durable": True, "auto_delete": False},
                {"name": "queue2", "durable": True, "auto_delete": False}
            ],
            "exchanges": [
                {"name": "exchange1", "durable": True, "auto_delete": False}
            ]
        }
        
        mock_json = json.dumps(definitions)
        
        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = verify_rabbitmq_persistence.verify_definitions_file(Path('/fake/path'))
        
        self.assertTrue(result)

    def test_verify_definitions_file_non_durable_queue(self):
        """Test that verification fails when a queue is not durable."""
        definitions = {
            "queues": [
                {"name": "queue1", "durable": False, "auto_delete": False}
            ],
            "exchanges": []
        }
        
        mock_json = json.dumps(definitions)
        
        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = verify_rabbitmq_persistence.verify_definitions_file(Path('/fake/path'))
        
        self.assertFalse(result)

    def test_verify_definitions_file_auto_delete_queue(self):
        """Test that verification fails when a queue has auto_delete=true."""
        definitions = {
            "queues": [
                {"name": "queue1", "durable": True, "auto_delete": True}
            ],
            "exchanges": []
        }
        
        mock_json = json.dumps(definitions)
        
        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = verify_rabbitmq_persistence.verify_definitions_file(Path('/fake/path'))
        
        self.assertFalse(result)

    def test_verify_definitions_file_non_durable_exchange(self):
        """Test that verification fails when an exchange is not durable."""
        definitions = {
            "queues": [],
            "exchanges": [
                {"name": "exchange1", "durable": False, "auto_delete": False}
            ]
        }
        
        mock_json = json.dumps(definitions)
        
        with patch('builtins.open', mock_open(read_data=mock_json)):
            result = verify_rabbitmq_persistence.verify_definitions_file(Path('/fake/path'))
        
        self.assertFalse(result)

    def test_verify_queue_durability_success(self):
        """Test successful queue durability verification."""
        mock_channel = MagicMock()
        mock_result = MagicMock()
        mock_channel.queue_declare.return_value = mock_result
        
        result = verify_rabbitmq_persistence.verify_queue_durability(
            mock_channel, "test.queue"
        )
        
        self.assertTrue(result)
        mock_channel.queue_declare.assert_called_once_with(
            queue="test.queue", passive=True
        )

    def test_verify_queue_durability_not_exist(self):
        """Test queue durability verification when queue does not exist."""
        try:
            import pika
        except ImportError:
            self.skipTest("pika library not available")
            
        mock_channel = MagicMock()
        mock_channel.queue_declare.side_effect = pika.exceptions.ChannelClosedByBroker(
            404, "NOT_FOUND - no queue 'test.queue'"
        )
        
        result = verify_rabbitmq_persistence.verify_queue_durability(
            mock_channel, "test.queue"
        )
        
        self.assertFalse(result)

    def test_verify_exchange_durability_success(self):
        """Test successful exchange durability verification."""
        mock_channel = MagicMock()
        
        result = verify_rabbitmq_persistence.verify_exchange_durability(
            mock_channel, "test.exchange", "topic"
        )
        
        self.assertTrue(result)
        mock_channel.exchange_declare.assert_called_once_with(
            exchange="test.exchange",
            exchange_type="topic",
            passive=True
        )


class TestRealDefinitionsFile(unittest.TestCase):
    """Test the actual definitions.json file in the repository."""

    def test_real_definitions_file_is_valid(self):
        """Test that the actual definitions.json file passes validation."""
        # Find the definitions.json file
        script_dir = Path(__file__).parent
        repo_root = script_dir.parent
        definitions_path = repo_root / 'infra' / 'rabbitmq' / 'definitions.json'
        
        if not definitions_path.exists():
            self.skipTest(f"definitions.json not found at {definitions_path}")
        
        # Verify it
        result = verify_rabbitmq_persistence.verify_definitions_file(definitions_path)
        
        self.assertTrue(
            result,
            "definitions.json should have all queues and exchanges marked as durable"
        )


if __name__ == '__main__':
    unittest.main()
