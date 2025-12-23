#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Test script for document processing status exporter.

This script validates that the exporter can:
1. Parse configuration from environment
2. Generate Prometheus metrics
3. Handle database queries gracefully
"""

import os
import sys
from unittest.mock import Mock, MagicMock, patch

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))


def test_exporter_imports():
    """Test that the exporter imports correctly."""
    try:
        from prometheus_client import Gauge
        print("✓ prometheus_client imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import prometheus_client: {e}")
        return False

    try:
        from pymongo import MongoClient
        print("✓ pymongo imports successfully")
    except ImportError as e:
        print(f"✗ Failed to import pymongo: {e}")
        return False

    return True


def test_exporter_configuration():
    """Test that the exporter reads configuration correctly."""
    # Set test environment variables
    os.environ["MONGO_URI"] = "mongodb://test:test@localhost:27017/admin"
    os.environ["MONGO_DB"] = "test_copilot"
    os.environ["PORT"] = "9999"
    os.environ["SCRAPE_INTERVAL_SEC"] = "10"

    # Import the exporter (this will read env vars)
    import document_processing_exporter as exporter

    assert exporter.MONGO_URI == "mongodb://test:test@localhost:27017/admin", "MONGO_URI not set correctly"
    assert exporter.DB_NAME == "test_copilot", "DB_NAME not set correctly"
    assert exporter.PORT == 9999, "PORT not set correctly"
    assert exporter.INTERVAL == 10.0, "INTERVAL not set correctly"

    print("✓ Configuration reading works correctly")
    return True


def test_exporter_metrics():
    """Test that the exporter defines metrics correctly."""
    import document_processing_exporter as exporter

    # Check that metrics are defined
    assert hasattr(exporter, 'document_status_count'), "document_status_count metric not defined"
    assert hasattr(exporter, 'document_processing_duration_seconds'), "document_processing_duration_seconds not defined"
    assert hasattr(exporter, 'document_age_seconds'), "document_age_seconds not defined"
    assert hasattr(exporter, 'document_attempt_count'), "document_attempt_count not defined"
    assert hasattr(exporter, 'chunks_embedding_status'), "chunks_embedding_status not defined"

    print("✓ All metrics are defined")
    return True


def test_get_archive_status_counts():
    """Test the get_archive_status_counts function."""
    import document_processing_exporter as exporter

    # Create a mock database
    mock_db = Mock()
    mock_archives = Mock()
    mock_db.archives = mock_archives

    # Mock the aggregate result
    mock_archives.aggregate.return_value = [
        {"_id": "pending", "count": 5},
        {"_id": "processed", "count": 10},
        {"_id": "failed", "count": 2},
    ]

    result = exporter.get_archive_status_counts(mock_db)

    assert result == {"pending": 5, "processed": 10, "failed": 2}, f"Unexpected result: {result}"
    print("✓ get_archive_status_counts works correctly")
    return True


def test_get_chunks_embedding_status():
    """Test the get_chunks_embedding_status function."""
    import document_processing_exporter as exporter

    # Create a mock database
    mock_db = Mock()
    mock_chunks = Mock()
    mock_db.chunks = mock_chunks

    # Mock the aggregate result
    mock_chunks.aggregate.return_value = [
        {"_id": True, "count": 100},
        {"_id": False, "count": 20},
    ]

    result = exporter.get_chunks_embedding_status(mock_db)

    assert result == {"True": 100, "False": 20}, f"Unexpected result: {result}"
    print("✓ get_chunks_embedding_status works correctly")
    return True


def test_collect_metrics():
    """Test the collect_metrics function with a mock database."""
    import document_processing_exporter as exporter

    # Create a mock MongoDB client
    mock_client = Mock()
    mock_db = Mock()
    mock_client.__getitem__ = Mock(return_value=mock_db)

    # Mock the database collections
    mock_db.archives = Mock()
    mock_db.chunks = Mock()

    # Mock archive status aggregation
    mock_db.archives.aggregate.return_value = [
        {"_id": "pending", "count": 5},
        {"_id": "processed", "count": 10},
        {"_id": "failed", "count": 2},
    ]

    # Mock chunk embedding status aggregation
    mock_db.chunks.aggregate.return_value = [
        {"_id": True, "count": 100},
        {"_id": False, "count": 20},
    ]

    # Call collect_metrics
    try:
        exporter.collect_metrics(mock_client)
        print("✓ collect_metrics executes without errors")
        return True
    except Exception as e:
        print(f"✗ collect_metrics failed: {e}")
        return False


def main():
    """Run all tests."""
    print("Testing Document Processing Status Exporter...")
    print("=" * 60)

    tests = [
        test_exporter_imports,
        test_exporter_configuration,
        test_exporter_metrics,
        test_get_archive_status_counts,
        test_get_chunks_embedding_status,
        test_collect_metrics,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} raised exception: {e}")
            failed += 1

    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed > 0:
        sys.exit(1)
    else:
        print("\n✓ All tests passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()
