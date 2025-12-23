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

import os
import sys
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

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

        # Second attempt: base delay * 2^(2-1) = 300 * 2 = 600s (10 min)
        self.assertEqual(self.job.calculate_backoff_delay(2), 600)

        # Third attempt: base delay * 2^(3-1) = 300 * 4 = 1200s (20 min)
        self.assertEqual(self.job.calculate_backoff_delay(3), 1200)

        # Fourth attempt: base delay * 2^(4-1) = 300 * 8 = 2400s (40 min)
        self.assertEqual(self.job.calculate_backoff_delay(4), 2400)

        # Fifth attempt: base delay * 2^(5-1) = 300 * 16 = 4800s, capped at 3600s (60 min)
        self.assertEqual(self.job.calculate_backoff_delay(5), 3600)

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
        # Second retry requires 600s delay (10 min)
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=400)

        # Only 400s elapsed, need 600s
        self.assertFalse(self.job.is_backoff_elapsed(last_attempt, 2))

    def test_is_backoff_elapsed_second_retry_ready(self):
        """Test backoff check for second retry (ready)."""
        # Second retry requires 600s delay (10 min)
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=700)

        # 700s elapsed, more than 600s required
        self.assertTrue(self.job.is_backoff_elapsed(last_attempt, 2))

    def test_is_backoff_elapsed_third_retry(self):
        """Test backoff check for third retry."""
        # Third retry requires 1200s delay (20 min)
        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=1000)
        self.assertFalse(self.job.is_backoff_elapsed(last_attempt, 3))

        last_attempt = datetime.now(timezone.utc) - timedelta(seconds=1300)
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
            "_id": "aaa1111bbb222222",
            "archive_id": "abc123",
        }

        event_data = self.job._build_event_data("messages", doc)

        self.assertEqual(event_data["archive_id"], "abc123")
        self.assertEqual(event_data["parsed_message_ids"], ["aaa1111bbb222222"])
        self.assertEqual(event_data["message_count"], 1)

    def test_build_event_data_chunks(self):
        """Test event data building for chunks."""
        doc = {
            "_id": "cccc3333dddd4444",
            "archive_id": "abc123",
        }

        event_data = self.job._build_event_data("chunks", doc)

        self.assertEqual(event_data["archive_id"], "abc123")
        self.assertEqual(event_data["chunk_ids"], ["cccc3333dddd4444"])

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


class TestProcessCollection(unittest.TestCase):
    """Test process_collection method."""

    def setUp(self):
        """Set up test fixtures."""
        self.job = RetryStuckDocumentsJob(
            mongodb_host="localhost",
            mongodb_port=27017,
            mongodb_database="test_copilot",
        )

    @patch('retry_stuck_documents.MongoClient')
    def test_process_collection_success(self, mock_mongo_client):
        """Test successful processing of a collection."""
        # Mock MongoDB
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db

        # Mock RabbitMQ
        self.job.rabbitmq_channel = MagicMock()

        # Setup stuck documents
        now = datetime.now(timezone.utc)
        stuck_docs = [
            {
                "archive_id": "abc1",
                "attemptCount": 0,
                "lastAttemptTime": None,
                "status": "pending",
                "file_path": "/data/test1.mbox",
                "source": "ietf-quic",
                "message_count": 10,
            },
            {
                "archive_id": "abc2",
                "attemptCount": 1,
                "lastAttemptTime": now - timedelta(hours=25),
                "status": "processing",
                "file_path": "/data/test2.mbox",
                "source": "ietf-quic",
                "message_count": 20,
            },
        ]
        mock_collection.find.return_value = stuck_docs
        mock_collection.count_documents.return_value = 0
        mock_collection.update_one.return_value = MagicMock()

        # Config for archives collection
        config = {
            "max_attempts": 3,
            "event_type": "ArchiveIngested",
            "routing_key": "archive.ingested",
            "id_field": "archive_id",
        }

        # Process collection
        self.job.process_collection("archives", config)

        # Verify documents were processed
        self.assertEqual(mock_collection.find.call_count, 1)
        # Should requeue 2 documents (both eligible)
        self.assertEqual(self.job.rabbitmq_channel.basic_publish.call_count, 2)
        # Should update attempt count 2 times
        self.assertEqual(mock_collection.update_one.call_count, 2)

    @patch('retry_stuck_documents.MongoClient')
    def test_process_collection_with_backoff_skip(self, mock_mongo_client):
        """Test processing skips documents not ready due to backoff."""
        # Mock MongoDB
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db

        # Mock RabbitMQ
        self.job.rabbitmq_channel = MagicMock()

        # Document with recent attempt (backoff not elapsed)
        now = datetime.now(timezone.utc)
        stuck_docs = [
            {
                "archive_id": "abc1",
                "attemptCount": 2,
                "lastAttemptTime": now - timedelta(seconds=500),  # Need 1200s for attempt 3
                "status": "pending",
                "file_path": "/data/test.mbox",
                "source": "ietf-quic",
                "message_count": 10,
            },
        ]
        mock_collection.find.return_value = stuck_docs
        mock_collection.count_documents.return_value = 0

        config = {
            "max_attempts": 3,
            "event_type": "ArchiveIngested",
            "routing_key": "archive.ingested",
            "id_field": "archive_id",
        }

        # Process collection
        self.job.process_collection("archives", config)

        # Verify document was skipped (backoff not elapsed)
        self.assertEqual(self.job.rabbitmq_channel.basic_publish.call_count, 0)

    @patch('retry_stuck_documents.MongoClient')
    def test_process_collection_max_retries_exceeded(self, mock_mongo_client):
        """Test processing marks documents exceeding max retries."""
        # Mock MongoDB
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db

        # Document at max retries
        now = datetime.now(timezone.utc)
        stuck_docs = [
            {
                "archive_id": "abc1",
                "attemptCount": 3,  # Max for archives
                "lastAttemptTime": now - timedelta(hours=25),
                "status": "pending",
                "file_path": "/data/test.mbox",
                "source": "ietf-quic",
                "message_count": 10,
            },
        ]
        mock_collection.find.return_value = stuck_docs
        mock_collection.count_documents.return_value = 1
        mock_result = MagicMock()
        mock_result.modified_count = 1
        mock_collection.update_one.return_value = mock_result

        config = {
            "max_attempts": 3,
            "event_type": "ArchiveIngested",
            "routing_key": "archive.ingested",
            "id_field": "archive_id",
        }

        # Process collection
        self.job.process_collection("archives", config)

        # Verify document was marked as failed_max_retries
        self.assertEqual(mock_collection.update_one.call_count, 1)
        call_args = mock_collection.update_one.call_args[0][1]
        self.assertEqual(call_args["$set"]["status"], "failed_max_retries")

    @patch('retry_stuck_documents.MongoClient')
    def test_process_collection_publish_error_handling(self, mock_mongo_client):
        """Test error handling when publishing fails."""
        # Mock MongoDB
        mock_collection = MagicMock()
        mock_db = MagicMock()
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        self.job.db = mock_db

        # Mock RabbitMQ to raise exception
        mock_channel = MagicMock()
        mock_channel.basic_publish.side_effect = Exception("RabbitMQ connection failed")
        self.job.rabbitmq_channel = mock_channel

        stuck_docs = [
            {
                "archive_id": "abc1",
                "attemptCount": 0,
                "lastAttemptTime": None,
                "status": "pending",
                "file_path": "/data/test.mbox",
                "source": "ietf-quic",
                "message_count": 10,
            },
        ]
        mock_collection.find.return_value = stuck_docs
        mock_collection.count_documents.return_value = 0
        mock_collection.update_one.return_value = MagicMock()

        config = {
            "max_attempts": 3,
            "event_type": "ArchiveIngested",
            "routing_key": "archive.ingested",
            "id_field": "archive_id",
        }

        # Process collection - should handle error gracefully
        self.job.process_collection("archives", config)

        # Verify attempt count was updated despite publish failure
        self.assertEqual(mock_collection.update_one.call_count, 1)


class TestRunOnce(unittest.TestCase):
    """Test run_once method."""

    def setUp(self):
        """Set up test fixtures."""
        self.job = RetryStuckDocumentsJob(
            mongodb_host="localhost",
            mongodb_port=27017,
            mongodb_database="test_copilot",
        )

    @patch('retry_stuck_documents.push_to_gateway')
    @patch('retry_stuck_documents.MongoClient')
    @patch('retry_stuck_documents.pika.BlockingConnection')
    def test_run_once_success(self, mock_rabbitmq, mock_mongo, mock_push):
        """Test successful run_once execution."""
        # Mock MongoDB connection
        mock_mongo_instance = MagicMock()
        mock_mongo_instance.admin.command.return_value = True
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find.return_value = []  # No stuck documents
        mock_collection.count_documents.return_value = 0
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_mongo_instance.__getitem__ = MagicMock(return_value=mock_db)
        mock_mongo.return_value = mock_mongo_instance

        # Mock RabbitMQ connection
        mock_rabbitmq_instance = MagicMock()
        mock_channel = MagicMock()
        mock_rabbitmq_instance.channel.return_value = mock_channel
        mock_rabbitmq_instance.is_closed = False
        mock_rabbitmq.return_value = mock_rabbitmq_instance

        # Run job
        self.job.run_once()

        # Verify connections were established
        mock_mongo.assert_called_once()
        mock_rabbitmq.assert_called_once()

        # Verify all collections were processed
        self.assertEqual(mock_collection.find.call_count, 4)  # archives, messages, chunks, threads

        # Verify metrics were pushed
        mock_push.assert_called_once()

        # Verify success metric was incremented
        # Note: Can't directly verify counter increment without access to registry

    @patch('retry_stuck_documents.push_to_gateway')
    @patch('retry_stuck_documents.MongoClient')
    @patch('retry_stuck_documents.pika.BlockingConnection')
    def test_run_once_initializes_gauges_before_processing(self, mock_rabbitmq, mock_mongo, mock_push):
        """Test that gauges are initialized to 0 before processing collections."""
        # Mock MongoDB connection failure to ensure gauges are still initialized
        mock_mongo.side_effect = Exception("MongoDB connection failed")

        # Spy on gauge .set() method
        stuck_docs_gauge = self.job.metrics.stuck_documents
        failed_docs_gauge = self.job.metrics.failed_documents

        stuck_set_calls = []
        failed_set_calls = []

        original_stuck_set = stuck_docs_gauge.labels
        original_failed_set = failed_docs_gauge.labels

        def stuck_labels_wrapper(**kwargs):
            gauge = original_stuck_set(**kwargs)
            original_set = gauge.set
            def set_wrapper(value):
                stuck_set_calls.append((kwargs, value))
                return original_set(value)
            gauge.set = set_wrapper
            return gauge

        def failed_labels_wrapper(**kwargs):
            gauge = original_failed_set(**kwargs)
            original_set = gauge.set
            def set_wrapper(value):
                failed_set_calls.append((kwargs, value))
                return original_set(value)
            gauge.set = set_wrapper
            return gauge

        stuck_docs_gauge.labels = stuck_labels_wrapper
        failed_docs_gauge.labels = failed_labels_wrapper

        # Run job - should raise exception but gauges should still be initialized
        with self.assertRaises(Exception) as context:
            self.job.run_once()

        self.assertIn("MongoDB connection failed", str(context.exception))

        # Verify gauges were initialized to 0 for all collections before connection failed
        self.assertEqual(len(stuck_set_calls), 4)  # archives, messages, chunks, threads
        self.assertEqual(len(failed_set_calls), 4)

        # Verify all gauges were set to 0
        for kwargs, value in stuck_set_calls:
            self.assertEqual(value, 0)
            self.assertIn(kwargs['collection'], ['archives', 'messages', 'chunks', 'threads'])

        for kwargs, value in failed_set_calls:
            self.assertEqual(value, 0)
            self.assertIn(kwargs['collection'], ['archives', 'messages', 'chunks', 'threads'])

        # Verify metrics were still pushed (in finally block)
        mock_push.assert_called_once()

    @patch('retry_stuck_documents.push_to_gateway')
    @patch('retry_stuck_documents.MongoClient')
    @patch('retry_stuck_documents.pika.BlockingConnection')
    def test_run_once_mongodb_connection_failure(self, mock_rabbitmq, mock_mongo, mock_push):
        """Test run_once handles MongoDB connection failure."""
        # Mock MongoDB connection failure
        mock_mongo.side_effect = Exception("MongoDB connection failed")

        # Run job - should raise exception
        with self.assertRaises(Exception) as context:
            self.job.run_once()

        self.assertIn("MongoDB connection failed", str(context.exception))

        # Verify metrics were still pushed (in finally block)
        mock_push.assert_called_once()

    @patch('retry_stuck_documents.push_to_gateway')
    @patch('retry_stuck_documents.MongoClient')
    @patch('retry_stuck_documents.pika.BlockingConnection')
    def test_run_once_collection_error_continues(self, mock_rabbitmq, mock_mongo, mock_push):
        """Test run_once continues processing if one collection fails."""
        # Mock MongoDB connection
        mock_mongo_instance = MagicMock()
        mock_mongo_instance.admin.command.return_value = True
        mock_db = MagicMock()

        # First collection raises error, subsequent should still process
        call_count = [0]
        def find_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Collection processing error")
            return []

        mock_collection = MagicMock()
        mock_collection.find.side_effect = find_side_effect
        mock_collection.count_documents.return_value = 0
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_mongo_instance.__getitem__ = MagicMock(return_value=mock_db)
        mock_mongo.return_value = mock_mongo_instance

        # Mock RabbitMQ connection
        mock_rabbitmq_instance = MagicMock()
        mock_channel = MagicMock()
        mock_rabbitmq_instance.channel.return_value = mock_channel
        mock_rabbitmq_instance.is_closed = False
        mock_rabbitmq.return_value = mock_rabbitmq_instance

        # Run job - should complete despite error in first collection
        self.job.run_once()

        # Verify all collections were attempted (4 total)
        self.assertEqual(mock_collection.find.call_count, 4)

        # Verify metrics were pushed
        mock_push.assert_called_once()

    @patch('retry_stuck_documents.push_to_gateway')
    @patch('retry_stuck_documents.MongoClient')
    @patch('retry_stuck_documents.pika.BlockingConnection')
    def test_run_once_metrics_push_failure(self, mock_rabbitmq, mock_mongo, mock_push):
        """Test run_once handles metrics push failure gracefully."""
        # Mock MongoDB and RabbitMQ connections
        mock_mongo_instance = MagicMock()
        mock_mongo_instance.admin.command.return_value = True
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_collection.find.return_value = []
        mock_collection.count_documents.return_value = 0
        mock_db.__getitem__ = MagicMock(return_value=mock_collection)
        mock_mongo_instance.__getitem__ = MagicMock(return_value=mock_db)
        mock_mongo.return_value = mock_mongo_instance

        mock_rabbitmq_instance = MagicMock()
        mock_channel = MagicMock()
        mock_rabbitmq_instance.channel.return_value = mock_channel
        mock_rabbitmq_instance.is_closed = False
        mock_rabbitmq.return_value = mock_rabbitmq_instance

        # Mock push_to_gateway to fail
        mock_push.side_effect = Exception("Pushgateway unavailable")

        # Run job - should complete despite metrics push failure
        self.job.run_once()

        # Verify job completed (no exception raised)
        mock_push.assert_called_once()


if __name__ == '__main__':
    unittest.main()
