#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Tests for retry_stuck_documents.py

These tests verify the retry job logic including:
- Exponential backoff calculation
- Stuck document detection
- Max retry handling
- Event publishing
- Metrics emission
"""

import unittest
from unittest.mock import MagicMock, patch, call
from datetime import datetime, timezone, timedelta
import sys
import os

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from retry_stuck_documents import RetryStuckDocumentsJob


class TestRetryStuckDocumentsJob(unittest.TestCase):
    """Test RetryStuckDocumentsJob class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.job = RetryStuckDocumentsJob(
            mongodb_host="localhost",
            mongodb_port=27017,
            mongodb_database="test_copilot",
            rabbitmq_host="localhost",
            rabbitmq_port=5672,
            pushgateway_url="http://localhost:9091",
            base_delay_seconds=300,
            max_delay_seconds=3600,
            stuck_threshold_hours=24,
        )
    
    def test_calculate_backoff_delay(self):
        """Test exponential backoff calculation."""
        # First attempt: no delay
        self.assertEqual(self.job.calculate_backoff_delay(0), 0)
        self.assertEqual(self.job.calculate_backoff_delay(1), 0)
        
        # Second attempt: base delay (300s = 5 min)
        self.assertEqual(self.job.calculate_backoff_delay(2), 300)
        
        # Third attempt: 2x base delay (600s = 10 min)
        self.assertEqual(self.job.calculate_backoff_delay(3), 600)
        
        # Fourth attempt: 4x base delay (1200s = 20 min)
        self.assertEqual(self.job.calculate_backoff_delay(4), 1200)
        
        # Fifth attempt: 8x base delay (2400s = 40 min)
        self.assertEqual(self.job.calculate_backoff_delay(5), 2400)
        
        # Sixth+ attempts: capped at max delay (3600s = 60 min)
        self.assertEqual(self.job.calculate_backoff_delay(6), 3600)
        self.assertEqual(self.job.calculate_backoff_delay(10), 3600)
    
    def test_is_backoff_elapsed_never_attempted(self):
        """Test backoff check for never-attempted documents."""
        # Document never attempted (lastAttemptTime = None)
        self.assertTrue(self.job.is_backoff_elapsed(None, 0))
    
    def test_is_backoff_elapsed_first_retry(self):
        """Test backoff check for first retry (no delay)."""
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=1)
        
        # First retry: no delay required, should be eligible immediately
        self.assertTrue(self.job.is_backoff_elapsed(last_attempt, 1))
    
    def test_is_backoff_elapsed_second_retry_not_ready(self):
        """Test backoff check for second retry (not ready)."""
        # Second retry requires 300s delay
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=200)
        
        # Only 200s elapsed, need 300s
        self.assertFalse(self.job.is_backoff_elapsed(last_attempt, 2))
    
    def test_is_backoff_elapsed_second_retry_ready(self):
        """Test backoff check for second retry (ready)."""
        # Second retry requires 300s delay
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=400)
        
        # 400s elapsed, more than 300s required
        self.assertTrue(self.job.is_backoff_elapsed(last_attempt, 2))
    
    def test_is_backoff_elapsed_third_retry(self):
        """Test backoff check for third retry."""
        # Third retry requires 600s delay
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=500)
        self.assertFalse(self.job.is_backoff_elapsed(last_attempt, 3))
        
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=700)
        self.assertTrue(self.job.is_backoff_elapsed(last_attempt, 3))
    
    def test_build_event_data_archives(self):
        """Test event data building for archives."""
        doc = {
            "archive_id": "abc123",
            "file_path": "/data/test.mbox",
            "source": "ietf-quic",
            "message_count": 42,
        }
        
        event_data = self.job._build_event_data("archives", doc)
        
        self.assertEqual(event_data["archive_id"], "abc123")
        self.assertEqual(event_data["file_path"], "/data/test.mbox")
        self.assertEqual(event_data["source"], "ietf-quic")
        self.assertEqual(event_data["message_count"], 42)
    
    def test_build_event_data_messages(self):
        """Test event data building for messages."""
        doc = {
            "message_key": "msg123",
            "archive_id": "abc123",
        }
        
        event_data = self.job._build_event_data("messages", doc)
        
        self.assertEqual(event_data["archive_id"], "abc123")
        self.assertEqual(event_data["parsed_message_ids"], ["msg123"])
        self.assertEqual(event_data["message_count"], 1)
    
    def test_build_event_data_chunks(self):
        """Test event data building for chunks."""
        doc = {
            "chunk_key": "chunk123",
            "message_key": "msg123",
        }
        
        event_data = self.job._build_event_data("chunks", doc)
        
        self.assertEqual(event_data["message_keys"], ["msg123"])
        self.assertEqual(event_data["chunk_ids"], ["chunk123"])
    
    def test_build_event_data_threads(self):
        """Test event data building for threads."""
        doc = {
            "thread_id": "thread123",
            "archive_id": "abc123",
        }
        
        event_data = self.job._build_event_data("threads", doc)
        
        self.assertEqual(event_data["thread_id"], "thread123")
        self.assertEqual(event_data["archive_id"], "abc123")
    
    @patch('retry_stuck_documents.MongoClient')
    def test_find_stuck_documents(self, mock_mongo_client):
        """Test finding stuck documents."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db
        
        # Mock stuck documents
        now = datetime.now(timezone.utc)
        stuck_threshold = now - timedelta(hours=24)
        
        mock_stuck_docs = [
            {"archive_id": "abc1", "attemptCount": 0, "lastAttemptTime": None},
            {"archive_id": "abc2", "attemptCount": 1, "lastAttemptTime": now - timedelta(hours=25)},
            {"archive_id": "abc3", "attemptCount": 2, "lastAttemptTime": now - timedelta(hours=30)},
        ]
        mock_collection.find.return_value = mock_stuck_docs
        
        # Find stuck documents
        stuck_docs = self.job.find_stuck_documents("archives", max_attempts=3)
        
        # Verify query
        self.assertEqual(len(stuck_docs), 3)
        mock_collection.find.assert_called_once()
        
        # Check query structure
        call_args = mock_collection.find.call_args[0][0]
        self.assertIn("status", call_args)
        self.assertIn("attemptCount", call_args)
        self.assertIn("$or", call_args)
    
    @patch('retry_stuck_documents.MongoClient')
    def test_mark_max_retries_exceeded(self, mock_mongo_client):
        """Test marking documents as failed due to max retries."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db
        
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result
        
        # Mark as failed
        self.job.mark_max_retries_exceeded("archives", "abc123", "archive_id")
        
        # Verify update
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        
        # Check filter
        self.assertEqual(call_args[0][0], {"archive_id": "abc123"})
        
        # Check update
        update = call_args[0][1]
        self.assertIn("$set", update)
        self.assertEqual(update["$set"]["status"], "failed_max_retries")
        self.assertIsNotNone(update["$set"]["lastAttemptTime"])
    
    @patch('retry_stuck_documents.MongoClient')
    def test_update_attempt_count(self, mock_mongo_client):
        """Test updating attempt count."""
        # Mock MongoDB collection
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db
        
        # Update attempt count
        self.job.update_attempt_count("archives", "abc123", "archive_id")
        
        # Verify update
        mock_collection.update_one.assert_called_once()
        call_args = mock_collection.update_one.call_args
        
        # Check filter
        self.assertEqual(call_args[0][0], {"archive_id": "abc123"})
        
        # Check update
        update = call_args[0][1]
        self.assertIn("$inc", update)
        self.assertEqual(update["$inc"]["attemptCount"], 1)
        self.assertIn("$set", update)
        self.assertIsNotNone(update["$set"]["lastAttemptTime"])
    
    @patch('retry_stuck_documents.pika')
    def test_publish_retry_event(self, mock_pika):
        """Test publishing retry event to RabbitMQ."""
        # Mock RabbitMQ channel
        mock_channel = MagicMock()
        self.job.rabbitmq_channel = mock_channel
        
        doc = {
            "_id": "test_id",
            "archive_id": "abc123",
            "file_path": "/data/test.mbox",
            "source": "ietf-quic",
            "message_count": 42,
        }
        
        # Publish event
        self.job.publish_retry_event(
            event_type="ArchiveIngested",
            routing_key="archive.ingested",
            document=doc,
            collection_name="archives"
        )
        
        # Verify publish
        mock_channel.basic_publish.assert_called_once()
        call_args = mock_channel.basic_publish.call_args
        
        # Check exchange and routing key
        self.assertEqual(call_args[1]["exchange"], "copilot.events")
        self.assertEqual(call_args[1]["routing_key"], "archive.ingested")
        
        # Check message body
        import json
        body = json.loads(call_args[1]["body"])
        self.assertEqual(body["event_type"], "ArchiveIngested")
        self.assertEqual(body["data"]["archive_id"], "abc123")
        self.assertEqual(body["data"]["message_count"], 42)


class TestRetryConfiguration(unittest.TestCase):
    """Test retry configuration and thresholds."""
    
    def test_collection_configs(self):
        """Test collection-specific configurations."""
        configs = RetryStuckDocumentsJob.COLLECTION_CONFIGS
        
        # Check all collections are configured
        self.assertIn("archives", configs)
        self.assertIn("messages", configs)
        self.assertIn("chunks", configs)
        self.assertIn("threads", configs)
        
        # Check archives config
        self.assertEqual(configs["archives"]["max_attempts"], 3)
        self.assertEqual(configs["archives"]["event_type"], "ArchiveIngested")
        self.assertEqual(configs["archives"]["routing_key"], "archive.ingested")
        self.assertEqual(configs["archives"]["id_field"], "archive_id")
        
        # Check messages config
        self.assertEqual(configs["messages"]["max_attempts"], 3)
        self.assertEqual(configs["messages"]["event_type"], "JSONParsed")
        
        # Check chunks config (higher retry limit)
        self.assertEqual(configs["chunks"]["max_attempts"], 5)
        self.assertEqual(configs["chunks"]["event_type"], "ChunksPrepared")
        
        # Check threads config (higher retry limit)
        self.assertEqual(configs["threads"]["max_attempts"], 5)
        self.assertEqual(configs["threads"]["event_type"], "SummarizationRequested")
    
    def test_default_parameters(self):
        """Test default parameter values."""
        job = RetryStuckDocumentsJob()
        
        self.assertEqual(job.base_delay_seconds, 300)  # 5 minutes
        self.assertEqual(job.max_delay_seconds, 3600)  # 60 minutes
        self.assertEqual(job.stuck_threshold_hours, 24)  # 24 hours
        self.assertEqual(job.mongodb_database, "copilot")
        self.assertEqual(job.rabbitmq_username, "guest")


class TestMetricsEmission(unittest.TestCase):
    """Test metrics emission."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.job = RetryStuckDocumentsJob()
    
    def test_metrics_initialized(self):
        """Test that all metrics are initialized."""
        metrics = self.job.metrics
        
        # Check counters
        self.assertIsNotNone(metrics.documents_requeued)
        self.assertIsNotNone(metrics.documents_skipped_backoff)
        self.assertIsNotNone(metrics.documents_max_retries_exceeded)
        self.assertIsNotNone(metrics.runs_total)
        self.assertIsNotNone(metrics.errors_total)
        
        # Check gauges
        self.assertIsNotNone(metrics.stuck_documents)
        self.assertIsNotNone(metrics.failed_documents)
        
        # Check histogram
        self.assertIsNotNone(metrics.duration_seconds)


if __name__ == '__main__':
    unittest.main()
