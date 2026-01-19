#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Document Processing Status Exporter for Prometheus.

Exposes document processing status metrics including:
- Document counts by status (pending, processing, completed, failed)
- Processing duration metrics
- Document age metrics (time since last update)
- Attempt count distributions

Environment Variables:
    MONGO_URI: MongoDB connection URI (default: mongodb://root:example@documentdb:27017/admin)
    MONGO_DB: Database name (default: copilot)
    PORT: Exporter HTTP port (default: 9502)
    SCRAPE_INTERVAL_SEC: Metrics collection interval (default: 5)
"""

import os
import time
from datetime import datetime, timezone

from prometheus_client import Gauge, start_http_server
from pymongo import MongoClient
from pymongo.errors import PyMongoError

# Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://root:example@documentdb:27017/admin")
DB_NAME = os.environ.get("MONGO_DB", "copilot")
PORT = int(os.environ.get("PORT", "9502"))
INTERVAL = float(os.environ.get("SCRAPE_INTERVAL_SEC", "5"))


# Prometheus metrics
document_status_count = Gauge(
    "copilot_document_status_count",
    "Count of documents by collection and status",
    ["database", "collection", "status"],
)

document_processing_duration_seconds = Gauge(
    "copilot_document_processing_duration_seconds",
    "Processing duration for documents (time between creation and completion)",
    ["database", "collection"],
)

document_age_seconds = Gauge(
    "copilot_document_age_seconds",
    "Time since document was last updated (for monitoring stuck documents)",
    ["database", "collection", "status"],
)

document_attempt_count = Gauge(
    "copilot_document_attempt_count",
    "Distribution of document attempt counts",
    ["database", "collection"],
)

chunks_embedding_status = Gauge(
    "copilot_chunks_embedding_status_count",
    "Count of chunks by embedding generation status",
    ["database", "embedding_generated"],
)

exporter_scrape_errors_total = Gauge(
    "copilot_document_exporter_scrape_errors_total",
    "Total number of errors while scraping document status",
    [],
)


def get_archive_status_counts(db) -> dict[str, int]:
    """Get counts of archives by status."""
    try:
        pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
        results = db.archives.aggregate(pipeline)
        counts = {}
        for result in results:
            status = result["_id"] if result["_id"] else "unknown"
            counts[status] = result["count"]
        return counts
    except PyMongoError as e:
        print(f"Error getting archive status counts: {e}")
        return {}


def get_chunks_embedding_status(db) -> dict[str, int]:
    """Get counts of chunks by embedding generation status."""
    try:
        pipeline = [{"$group": {"_id": "$embedding_generated", "count": {"$sum": 1}}}]
        results = db.chunks.aggregate(pipeline)
        counts = {}
        for result in results:
            status = str(result["_id"]) if result["_id"] is not None else "unknown"
            counts[status] = result["count"]
        return counts
    except PyMongoError as e:
        print(f"Error getting chunk embedding status: {e}")
        return {}


def get_document_age_metrics(db, collection_name: str, status_field: str = "status") -> dict[str, float]:
    """
    Calculate average age of documents by status (time since last update).

    Args:
        db: MongoDB database
        collection_name: Name of collection to query
        status_field: Field name for status (default: "status")

    Returns:
        Dictionary with status as key and average age in seconds as value
    """
    try:
        # Find documents with updated_at or created_at timestamps
        now = datetime.now(timezone.utc)

        # Try to use updated_at if available, otherwise created_at
        pipeline = [
            {"$project": {"status": f"${status_field}", "timestamp": {"$ifNull": ["$updated_at", "$created_at"]}}},
            {"$match": {"timestamp": {"$exists": True}}},
            {"$group": {"_id": "$status", "avg_timestamp": {"$avg": {"$toLong": {"$toDate": "$timestamp"}}}}},
        ]

        results = db[collection_name].aggregate(pipeline)
        age_metrics = {}

        for result in results:
            status = result["_id"] if result["_id"] else "unknown"
            if result["avg_timestamp"]:
                # Convert milliseconds to seconds
                avg_timestamp_sec = result["avg_timestamp"] / 1000.0
                avg_dt = datetime.fromtimestamp(avg_timestamp_sec, tz=timezone.utc)
                age_seconds = (now - avg_dt).total_seconds()
                age_metrics[status] = max(0, age_seconds)  # Ensure non-negative

        return age_metrics
    except PyMongoError as e:
        print(f"Error calculating document age for {collection_name}: {e}")
        return {}


def get_processing_duration_metrics(db, collection_name: str) -> float:
    """
    Calculate average processing duration for completed documents.

    For documents with both created_at and updated_at timestamps,
    calculate the difference.

    Args:
        db: MongoDB database
        collection_name: Name of collection to query

    Returns:
        Average processing duration in seconds, or 0 if no data
    """
    try:
        pipeline = [
            {"$match": {"created_at": {"$exists": True}, "updated_at": {"$exists": True}}},
            {
                "$project": {
                    "duration": {
                        "$subtract": [{"$toLong": {"$toDate": "$updated_at"}}, {"$toLong": {"$toDate": "$created_at"}}]
                    }
                }
            },
            {"$group": {"_id": None, "avg_duration_ms": {"$avg": "$duration"}}},
        ]

        results = list(db[collection_name].aggregate(pipeline))
        if results and results[0]["avg_duration_ms"]:
            # Convert milliseconds to seconds
            return results[0]["avg_duration_ms"] / 1000.0
        return 0.0
    except PyMongoError as e:
        print(f"Error calculating processing duration for {collection_name}: {e}")
        return 0.0


def get_attempt_count_metrics(db, collection_name: str) -> float:
    """
    Calculate average attempt count for documents.

    Args:
        db: MongoDB database
        collection_name: Name of collection to query

    Returns:
        Average attempt count, or 0 if field doesn't exist
    """
    try:
        pipeline = [
            {"$match": {"attemptCount": {"$exists": True}}},
            {"$group": {"_id": None, "avg_attempts": {"$avg": "$attemptCount"}}},
        ]

        results = list(db[collection_name].aggregate(pipeline))
        if results and results[0]["avg_attempts"] is not None:
            return results[0]["avg_attempts"]
        return 0.0
    except PyMongoError as e:
        print(f"Error calculating attempt counts for {collection_name}: {e}")
        return 0.0


def collect_metrics(client: MongoClient):
    """Collect all document processing metrics."""
    db = client[DB_NAME]

    try:
        # Archive status counts
        archive_status = get_archive_status_counts(db)
        for status, count in archive_status.items():
            document_status_count.labels(database=DB_NAME, collection="archives", status=status).set(count)

        # Ensure all expected statuses are represented (set to 0 if not present)
        # Note: Using subset of schema statuses that are commonly monitored.
        # Full schema: ['pending', 'processing', 'completed', 'failed', 'failed_max_retries']
        for status in ["pending", "processing", "completed", "failed", "failed_max_retries"]:
            if status not in archive_status:
                document_status_count.labels(database=DB_NAME, collection="archives", status=status).set(0)

        # Chunk embedding status
        chunk_embedding = get_chunks_embedding_status(db)
        for status, count in chunk_embedding.items():
            chunks_embedding_status.labels(database=DB_NAME, embedding_generated=status).set(count)

        # Document age metrics for archives
        archive_ages = get_document_age_metrics(db, "archives", "status")
        for status, age in archive_ages.items():
            document_age_seconds.labels(database=DB_NAME, collection="archives", status=status).set(age)

        # Processing duration for archives
        archive_duration = get_processing_duration_metrics(db, "archives")
        if archive_duration > 0:
            document_processing_duration_seconds.labels(database=DB_NAME, collection="archives").set(archive_duration)

        # Attempt count metrics (if the field exists)
        for collection_name in ["archives", "messages", "chunks"]:
            avg_attempts = get_attempt_count_metrics(db, collection_name)
            if avg_attempts > 0:
                document_attempt_count.labels(database=DB_NAME, collection=collection_name).set(avg_attempts)

        # Reset error counter on success
        exporter_scrape_errors_total.set(0)

    except Exception as e:
        print(f"Error collecting metrics: {e}")
        exporter_scrape_errors_total.inc()


def main():
    """Main exporter loop."""
    print(f"Starting Document Processing Status Exporter on port {PORT}")
    print(f"MongoDB: {MONGO_URI}")
    print(f"Database: {DB_NAME}")
    print(f"Scrape interval: {INTERVAL}s")

    start_http_server(PORT)
    client = MongoClient(MONGO_URI, directConnection=True)

    print("Exporter started successfully")

    while True:
        collect_metrics(client)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
