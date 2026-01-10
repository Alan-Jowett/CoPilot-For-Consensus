#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Retry Stuck Documents Job

This script periodically checks for stuck or failed documents in MongoDB
and requeues them for retry according to the retry policy defined in
documents/RETRY_POLICY.md.

Features:
- Exponential backoff with configurable delays
- Maximum retry attempt limits per document type
- Metrics emission to Prometheus Pushgateway
- Automatic marking of documents exceeding retry limits
- Safe idempotent retry logic

Usage:
    # Run once
    python scripts/retry_stuck_documents.py --once

    # Run continuously (default)
    python scripts/retry_stuck_documents.py

    # Custom configuration
    python scripts/retry_stuck_documents.py \
        --interval 600 \
        --base-delay 300 \
        --max-delay 3600 \
        --stuck-threshold-hours 24
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from copilot_config import load_driver_config
from copilot_logging import create_logger

# Import dependencies - these will fail gracefully in main() if not installed
try:
    from pymongo import MongoClient
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    MongoClient = None  # type: ignore

try:
    import pika
    PIKA_AVAILABLE = True
except ImportError:
    PIKA_AVAILABLE = False
    pika = None  # type: ignore

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CollectorRegistry = None  # type: ignore
    Counter = None  # type: ignore
    Gauge = None  # type: ignore
    Histogram = None  # type: ignore
    push_to_gateway = None  # type: ignore

logger_config = load_driver_config(
    service=None,
    adapter="logger",
    driver="stdout",
    fields={"level": "INFO", "name": __name__}
)
logger = create_logger(driver_name="stdout", driver_config=logger_config)


def _get_env_or_secret(env_var: str, secret_name: str) -> str | None:
    """Return env var if set, otherwise read from /run/secrets/<secret_name>."""
    if env_var in os.environ and os.environ[env_var]:
        return os.environ[env_var]
    secret_path = Path("/run/secrets") / secret_name
    try:
        return secret_path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:  # pragma: no cover - hard to simulate
        logger.warning("Failed to read secret %s: %s", secret_path, exc)
        return None


class RetryJobMetrics:
    """Prometheus metrics for retry job."""

    def __init__(self, registry: CollectorRegistry):
        """Initialize metrics.

        Args:
            registry: Prometheus collector registry
        """
        self.documents_requeued = Counter(
            'retry_job_documents_requeued_total',
            'Total documents requeued for retry',
            ['collection'],
            registry=registry
        )

        self.documents_skipped_backoff = Counter(
            'retry_job_documents_skipped_backoff_total',
            'Documents skipped due to backoff delay',
            ['collection'],
            registry=registry
        )

        self.documents_max_retries_exceeded = Counter(
            'retry_job_documents_max_retries_exceeded_total',
            'Documents exceeding max retry attempts',
            ['collection'],
            registry=registry
        )

        self.runs_total = Counter(
            'retry_job_runs_total',
            'Retry job executions',
            ['status'],
            registry=registry
        )

        self.errors_total = Counter(
            'retry_job_errors_total',
            'Errors encountered during retry job',
            ['error_type'],
            registry=registry
        )

        self.stuck_documents = Gauge(
            'retry_job_stuck_documents',
            'Current count of stuck documents',
            ['collection'],
            registry=registry
        )

        self.failed_documents = Gauge(
            'retry_job_failed_documents',
            'Current count of failed documents (max retries)',
            ['collection'],
            registry=registry
        )

        self.duration_seconds = Histogram(
            'retry_job_duration_seconds',
            'Time taken to complete retry job',
            registry=registry
        )


class RetryStuckDocumentsJob:
    """Retry job for stuck/failed documents."""

    # Collection-specific configurations
    COLLECTION_CONFIGS = {
        "archives": {
            "max_attempts": 3,
            "event_type": "ArchiveIngested",
            "routing_key": "archive.ingested",
            "id_field": "archive_id",
        },
        "messages": {
            "max_attempts": 3,
            "event_type": "JSONParsed",
            "routing_key": "json.parsed",
            "id_field": "_id",
        },
        "chunks": {
            "max_attempts": 5,
            "event_type": "ChunksPrepared",
            "routing_key": "chunks.prepared",
            "id_field": "_id",
        },
        "threads": {
            "max_attempts": 5,
            "event_type": "SummarizationRequested",
            "routing_key": "summarization.requested",
            "id_field": "thread_id",
        },
    }

    def __init__(
        self,
        mongodb_host: str = "localhost",
        mongodb_port: int = 27017,
        mongodb_database: str = "copilot",
        mongodb_username: str | None = None,
        mongodb_password: str | None = None,
        rabbitmq_host: str = "localhost",
        rabbitmq_port: int = 5672,
        rabbitmq_username: str = "guest",
        rabbitmq_password: str = "guest",
        pushgateway_url: str = "http://localhost:9091",
        base_delay_seconds: int = 300,
        max_delay_seconds: int = 3600,
        stuck_threshold_hours: int = 24,
    ):
        """Initialize retry job.

        Args:
            mongodb_host: MongoDB host
            mongodb_port: MongoDB port
            mongodb_database: MongoDB database name
            mongodb_username: MongoDB username (optional)
            mongodb_password: MongoDB password (optional)
            rabbitmq_host: RabbitMQ host
            rabbitmq_port: RabbitMQ port
            rabbitmq_username: RabbitMQ username
            rabbitmq_password: RabbitMQ password
            pushgateway_url: Prometheus Pushgateway URL
            base_delay_seconds: Base delay for exponential backoff
            max_delay_seconds: Maximum backoff delay
            stuck_threshold_hours: Hours before document is "stuck"
        """
        self.mongodb_host = mongodb_host
        self.mongodb_port = mongodb_port
        self.mongodb_database = mongodb_database
        self.mongodb_username = mongodb_username
        self.mongodb_password = mongodb_password
        self.rabbitmq_host = rabbitmq_host
        self.rabbitmq_port = rabbitmq_port
        self.rabbitmq_username = rabbitmq_username
        self.rabbitmq_password = rabbitmq_password
        self.pushgateway_url = pushgateway_url
        self.base_delay_seconds = base_delay_seconds
        self.max_delay_seconds = max_delay_seconds
        self.stuck_threshold_hours = stuck_threshold_hours

        # Initialize connections
        self.mongo_client = None
        self.db = None
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None

        # Initialize metrics
        self.registry = CollectorRegistry()
        self.metrics = RetryJobMetrics(self.registry)

    def connect_mongodb(self):
        """Connect to MongoDB."""
        if self.mongodb_username and self.mongodb_password:
            connection_string = (
                f"mongodb://{self.mongodb_username}:{self.mongodb_password}@"
                f"{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_database}?authSource=admin"
            )
        else:
            connection_string = f"mongodb://{self.mongodb_host}:{self.mongodb_port}/{self.mongodb_database}"

        self.mongo_client = MongoClient(connection_string, serverSelectionTimeoutMS=5000)
        self.db = self.mongo_client[self.mongodb_database]

        # Test connection
        self.mongo_client.admin.command('ping')
        logger.info(f"Connected to MongoDB at {self.mongodb_host}:{self.mongodb_port}")

    def disconnect_mongodb(self):
        """Disconnect from MongoDB."""
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("Disconnected from MongoDB")

    def connect_rabbitmq(self):
        """Connect to RabbitMQ."""
        credentials = pika.PlainCredentials(self.rabbitmq_username, self.rabbitmq_password)
        parameters = pika.ConnectionParameters(
            host=self.rabbitmq_host,
            port=self.rabbitmq_port,
            credentials=credentials,
        )
        self.rabbitmq_connection = pika.BlockingConnection(parameters)
        self.rabbitmq_channel = self.rabbitmq_connection.channel()

        # Ensure exchange exists
        self.rabbitmq_channel.exchange_declare(
            exchange="copilot.events",
            exchange_type="topic",
            durable=True,
        )

        logger.info(f"Connected to RabbitMQ at {self.rabbitmq_host}:{self.rabbitmq_port}")

    def disconnect_rabbitmq(self):
        """Disconnect from RabbitMQ."""
        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            self.rabbitmq_connection.close()
            logger.info("Disconnected from RabbitMQ")

    def calculate_backoff_delay(self, attempt_count: int) -> int:
        """Calculate exponential backoff delay.

        Args:
            attempt_count: Number of attempts so far

        Returns:
            Delay in seconds
        """
        if attempt_count <= 1:
            return 0  # No delay for first retry

        # Exponential: base * 2^(attempt - 1)
        delay = self.base_delay_seconds * (2 ** (attempt_count - 1))
        return min(delay, self.max_delay_seconds)

    def is_backoff_elapsed(self, last_attempt_time: datetime, attempt_count: int) -> bool:
        """Check if backoff period has elapsed.

        Args:
            last_attempt_time: Timestamp of last attempt
            attempt_count: Number of attempts so far

        Returns:
            True if backoff delay has elapsed
        """
        if last_attempt_time is None:
            return True  # Never attempted, eligible for retry

        backoff_delay = self.calculate_backoff_delay(attempt_count)
        next_attempt_time = last_attempt_time + timedelta(seconds=backoff_delay)

        return datetime.now(timezone.utc) >= next_attempt_time

    def find_stuck_documents(self, collection_name: str, max_attempts: int) -> list[dict[str, Any]]:
        """Find stuck documents eligible for retry.

        Args:
            collection_name: Name of collection
            max_attempts: Maximum retry attempts for this collection

        Returns:
            List of stuck documents
        """
        collection = self.db[collection_name]
        stuck_threshold = datetime.now(timezone.utc) - timedelta(hours=self.stuck_threshold_hours)

        # Query for stuck documents
        query = {
            "status": {"$in": ["pending", "processing"]},
            "attemptCount": {"$lt": max_attempts},
            "$or": [
                {"lastAttemptTime": None},
                {"lastAttemptTime": {"$lt": stuck_threshold}}
            ]
        }

        stuck_docs = list(collection.find(query))
        logger.info(f"Found {len(stuck_docs)} stuck documents in {collection_name}")

        return stuck_docs

    def find_failed_documents(self, collection_name: str, max_attempts: int) -> int:
        """Count documents that have exceeded max retries.

        Args:
            collection_name: Name of collection
            max_attempts: Maximum retry attempts for this collection

        Returns:
            Count of failed documents
        """
        collection = self.db[collection_name]

        query = {
            "attemptCount": {"$gte": max_attempts},
            "status": {"$nin": ["completed", "failed_max_retries"]}
        }

        return collection.count_documents(query)

    def mark_max_retries_exceeded(self, collection_name: str, doc_id: Any, id_field: str):
        """Mark document as permanently failed due to max retries.

        Args:
            collection_name: Name of collection
            doc_id: Document ID
            id_field: ID field name
        """
        collection = self.db[collection_name]

        result = collection.update_one(
            {id_field: doc_id},
            {
                "$set": {
                    "status": "failed_max_retries",
                    "lastAttemptTime": datetime.now(timezone.utc)
                }
            }
        )

        if result.modified_count > 0:
            logger.error(
                f"Document {doc_id} in {collection_name} exceeded max retries. "
                f"Marked as failed_max_retries."
            )
            self.metrics.documents_max_retries_exceeded.labels(collection=collection_name).inc()

    def update_attempt_count(self, collection_name: str, doc_id: Any, id_field: str):
        """Increment attempt count and update last attempt time.

        Args:
            collection_name: Name of collection
            doc_id: Document ID
            id_field: ID field name
        """
        collection = self.db[collection_name]

        collection.update_one(
            {id_field: doc_id},
            {
                "$inc": {"attemptCount": 1},
                "$set": {"lastAttemptTime": datetime.now(timezone.utc)}
            }
        )

    def publish_retry_event(
        self,
        event_type: str,
        routing_key: str,
        document: dict[str, Any],
        collection_name: str
    ):
        """Publish event to trigger document reprocessing.

        Args:
            event_type: Event type name
            routing_key: RabbitMQ routing key
            document: Document data
            collection_name: Collection name
        """
        # Build event payload based on collection type
        event_data = self._build_event_data(collection_name, document)

        event = {
            "event_type": event_type,
            "event_id": f"retry-{document.get('_id', 'unknown')}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": "1.0",
            "data": event_data
        }

        # Publish to RabbitMQ
        self.rabbitmq_channel.basic_publish(
            exchange="copilot.events",
            routing_key=routing_key,
            body=json.dumps(event),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,  # Persistent
            )
        )

        logger.info(f"Published {event_type} event for retry: {routing_key}")

    def _build_event_data(self, collection_name: str, document: dict[str, Any]) -> dict[str, Any]:
        """Build event data payload for retry.

        Args:
            collection_name: Collection name
            document: Document from MongoDB

        Returns:
            Event data dictionary
        """
        if collection_name == "archives":
            return {
                "archive_id": document.get("archive_id"),
                "file_path": document.get("file_path"),
                "source": document.get("source"),
                "message_count": document.get("message_count", 0),
            }
        elif collection_name == "messages":
            return {
                "archive_id": document.get("archive_id"),
                "parsed_message_ids": [document.get("_id")],
                "message_count": 1,
            }
        elif collection_name == "chunks":
            return {
                "archive_id": document.get("archive_id"),
                "chunk_ids": [document.get("_id")],
            }
        elif collection_name == "threads":
            return {
                "thread_id": document.get("thread_id"),
                "archive_id": document.get("archive_id"),
            }
        else:
            return {}

    def process_collection(self, collection_name: str, config: dict[str, Any]):
        """Process stuck documents in a collection.

        Args:
            collection_name: Name of collection
            config: Collection configuration
        """
        logger.info(f"Processing collection: {collection_name}")

        max_attempts = config["max_attempts"]
        event_type = config["event_type"]
        routing_key = config["routing_key"]
        id_field = config["id_field"]

        # Find stuck documents
        stuck_docs = self.find_stuck_documents(collection_name, max_attempts)

        # Update stuck documents gauge
        self.metrics.stuck_documents.labels(collection=collection_name).set(len(stuck_docs))

        # Process each stuck document
        requeued_count = 0
        skipped_count = 0

        for doc in stuck_docs:
            doc_id = doc.get(id_field)
            attempt_count = doc.get("attemptCount", 0)
            last_attempt_time = doc.get("lastAttemptTime")

            # Check if max retries exceeded
            if attempt_count >= max_attempts:
                self.mark_max_retries_exceeded(collection_name, doc_id, id_field)
                continue

            # Check backoff eligibility
            if not self.is_backoff_elapsed(last_attempt_time, attempt_count):
                logger.debug(
                    f"Skipping {doc_id} in {collection_name}: "
                    f"backoff not elapsed (attempt {attempt_count})"
                )
                self.metrics.documents_skipped_backoff.labels(collection=collection_name).inc()
                skipped_count += 1
                continue

            # Update attempt count
            self.update_attempt_count(collection_name, doc_id, id_field)

            # Publish retry event
            try:
                self.publish_retry_event(event_type, routing_key, doc, collection_name)
                self.metrics.documents_requeued.labels(collection=collection_name).inc()
                requeued_count += 1
            except Exception as e:
                logger.error(f"Failed to publish retry event for {doc_id}: {e}")
                self.metrics.errors_total.labels(error_type="publish_error").inc()

        # Count failed documents (exceeded max retries)
        failed_count = self.find_failed_documents(collection_name, max_attempts)
        self.metrics.failed_documents.labels(collection=collection_name).set(failed_count)

        logger.info(
            f"Processed {collection_name}: "
            f"{requeued_count} requeued, {skipped_count} skipped (backoff), "
            f"{failed_count} failed (max retries)"
        )

    def run_once(self):
        """Run retry job once."""
        logger.info("Starting retry job execution")
        start_time = time.time()

        # Initialize all gauges to 0 to ensure metrics exist even on failure
        for collection_name in self.COLLECTION_CONFIGS.keys():
            self.metrics.stuck_documents.labels(collection=collection_name).set(0)
            self.metrics.failed_documents.labels(collection=collection_name).set(0)

        try:
            # Connect to dependencies
            self.connect_mongodb()
            self.connect_rabbitmq()

            # Process each collection
            for collection_name, config in self.COLLECTION_CONFIGS.items():
                try:
                    self.process_collection(collection_name, config)
                except Exception as e:
                    logger.error(f"Error processing collection {collection_name}: {e}", exc_info=True)
                    self.metrics.errors_total.labels(error_type="collection_error").inc()
                    # Gauges already initialized to 0 above

            # Record success
            self.metrics.runs_total.labels(status="success").inc()

        except Exception as e:
            logger.error(f"Retry job failed: {e}", exc_info=True)
            self.metrics.runs_total.labels(status="failure").inc()
            self.metrics.errors_total.labels(error_type="job_error").inc()
            raise

        finally:
            # Disconnect
            self.disconnect_rabbitmq()
            self.disconnect_mongodb()

            # Record duration
            duration = time.time() - start_time
            self.metrics.duration_seconds.observe(duration)

            # Push metrics to Pushgateway
            try:
                push_to_gateway(
                    self.pushgateway_url,
                    job='retry-job',
                    registry=self.registry
                )
                logger.info(f"Pushed metrics to {self.pushgateway_url}")
            except Exception as e:
                logger.warning(f"Failed to push metrics to Pushgateway: {e}")

            logger.info(f"Retry job completed in {duration:.2f} seconds")

    def run_loop(self, interval_seconds: int):
        """Run retry job in a loop.

        Args:
            interval_seconds: Seconds between executions
        """
        logger.info(f"Starting retry job loop (interval: {interval_seconds}s)")

        while True:
            try:
                self.run_once()
            except Exception as e:
                logger.error(f"Retry job execution failed: {e}")

            logger.info(f"Sleeping for {interval_seconds} seconds...")
            time.sleep(interval_seconds)


def main():
    """Main CLI entry point."""
    # Check for required dependencies
    if not PYMONGO_AVAILABLE:
        print("Error: pymongo library not installed. Run: pip install pymongo", file=sys.stderr)
        sys.exit(1)

    if not PIKA_AVAILABLE:
        print("Error: pika library not installed. Run: pip install pika", file=sys.stderr)
        sys.exit(1)

    if not PROMETHEUS_AVAILABLE:
        print("Error: prometheus_client not installed. Run: pip install prometheus_client", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Retry stuck documents in Copilot-for-Consensus pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  MONGODB_HOST           MongoDB host (default: localhost)
  MONGODB_PORT           MongoDB port (default: 27017)
  MONGODB_DATABASE       MongoDB database (default: copilot)
  MONGODB_USERNAME       MongoDB username (optional)
  MONGODB_PASSWORD       MongoDB password (optional)
  RABBITMQ_HOST          RabbitMQ host (default: localhost)
  RABBITMQ_PORT          RabbitMQ port (default: 5672)
  RABBITMQ_USERNAME      RabbitMQ username (default: guest)
  RABBITMQ_PASSWORD      RabbitMQ password (default: guest)
  PUSHGATEWAY_URL        Prometheus Pushgateway URL (default: http://localhost:9091)
  RETRY_JOB_INTERVAL_SECONDS      Interval between runs (default: 900)
  RETRY_JOB_BASE_DELAY_SECONDS    Base backoff delay (default: 300)
  RETRY_JOB_MAX_DELAY_SECONDS     Max backoff delay (default: 3600)
  RETRY_JOB_STUCK_THRESHOLD_HOURS Stuck threshold (default: 24)

For full documentation, see documents/RETRY_POLICY.md
        """
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (default: run continuously)"
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("RETRY_JOB_INTERVAL_SECONDS", "900")),
        help="Interval between runs in seconds (default: 900)"
    )

    parser.add_argument(
        "--base-delay",
        type=int,
        default=int(os.getenv("RETRY_JOB_BASE_DELAY_SECONDS", "300")),
        help="Base backoff delay in seconds (default: 300)"
    )

    parser.add_argument(
        "--max-delay",
        type=int,
        default=int(os.getenv("RETRY_JOB_MAX_DELAY_SECONDS", "3600")),
        help="Max backoff delay in seconds (default: 3600)"
    )

    parser.add_argument(
        "--stuck-threshold-hours",
        type=int,
        default=int(os.getenv("RETRY_JOB_STUCK_THRESHOLD_HOURS", "24")),
        help="Hours before document is 'stuck' (default: 24)"
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    global logger
    if args.verbose:
        logger_config = load_driver_config(
            service=None,
            adapter="logger",
            driver="stdout",
            fields={"level": "DEBUG", "name": __name__}
        )
        logger = create_logger(driver_name="stdout", driver_config=logger_config)

    mongodb_username = _get_env_or_secret("MONGODB_USERNAME", "document_database_user")
    mongodb_password = _get_env_or_secret("MONGODB_PASSWORD", "document_database_password")
    rabbitmq_username = _get_env_or_secret("RABBITMQ_USERNAME", "message_bus_user") or "guest"
    rabbitmq_password = _get_env_or_secret("RABBITMQ_PASSWORD", "message_bus_password") or "guest"

    # Create retry job
    job = RetryStuckDocumentsJob(
        mongodb_host=os.getenv("MONGODB_HOST", "localhost"),
        mongodb_port=int(os.getenv("MONGODB_PORT", "27017")),
        mongodb_database=os.getenv("MONGODB_DATABASE", "copilot"),
        mongodb_username=mongodb_username,
        mongodb_password=mongodb_password,
        rabbitmq_host=os.getenv("RABBITMQ_HOST", "localhost"),
        rabbitmq_port=int(os.getenv("RABBITMQ_PORT", "5672")),
        rabbitmq_username=rabbitmq_username,
        rabbitmq_password=rabbitmq_password,
        pushgateway_url=os.getenv("PUSHGATEWAY_URL", "http://localhost:9091"),
        base_delay_seconds=args.base_delay,
        max_delay_seconds=args.max_delay,
        stuck_threshold_hours=args.stuck_threshold_hours,
    )

    # Run
    try:
        if args.once:
            job.run_once()
        else:
            job.run_loop(args.interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
