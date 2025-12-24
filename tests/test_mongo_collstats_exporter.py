#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Test script for MongoDB collection stats exporter.

This script validates that the exporter can:
1. Parse configuration from environment
2. Generate Prometheus metrics
3. Handle database queries gracefully
"""

import os
import sys
from unittest.mock import Mock

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
    import mongo_collstats_exporter as exporter

    assert exporter.MONGO_URI == "mongodb://test:test@localhost:27017/admin", "MONGO_URI not set correctly"
    assert exporter.DB_NAME == "test_copilot", "DB_NAME not set correctly"
    assert exporter.PORT == 9999, "PORT not set correctly"
    assert exporter.INTERVAL == 10.0, "INTERVAL not set correctly"

    print("✓ Configuration reading works correctly")
    return True


def test_exporter_metrics():
    """Test that the exporter defines metrics correctly."""
    import mongo_collstats_exporter as exporter

    # Check that metrics are defined
    assert hasattr(exporter, 'storage_size_gauge'), "storage_size_gauge metric not defined"
    assert hasattr(exporter, 'count_gauge'), "count_gauge metric not defined"
    assert hasattr(exporter, 'avg_obj_size_gauge'), "avg_obj_size_gauge not defined"
    assert hasattr(exporter, 'total_index_size_gauge'), "total_index_size_gauge not defined"
    assert hasattr(exporter, 'index_sizes_gauge'), "index_sizes_gauge not defined"

    print("✓ All metrics are defined")
    return True


def test_get_collection_stats():
    """Test the get_collection_stats function."""
    import mongo_collstats_exporter as exporter

    # Create a mock database
    mock_db = Mock()

    # Mock the command result
    mock_db.command.return_value = {
        "ns": "copilot.archives",
        "count": 100,
        "size": 50000,
        "storageSize": 40960,
        "avgObjSize": 500,
        "totalIndexSize": 8192,
        "indexSizes": {
            "_id_": 4096,
            "status_1": 4096
        }
    }

    result = exporter.get_collection_stats(mock_db, "archives")

    assert result["count"] == 100, f"Unexpected count: {result.get('count')}"
    assert result["storageSize"] == 40960, f"Unexpected storageSize: {result.get('storageSize')}"
    assert result["avgObjSize"] == 500, f"Unexpected avgObjSize: {result.get('avgObjSize')}"

    print("✓ get_collection_stats works correctly")
    return True


def test_collect_metrics():
    """Test the collect_metrics function with a mock database."""
    import mongo_collstats_exporter as exporter

    # Create a mock MongoDB client
    mock_client = Mock()
    mock_db = Mock()
    mock_client.__getitem__ = Mock(return_value=mock_db)

    # Mock the command method to return collection stats
    def mock_command(cmd, collection_name):
        return {
            "ns": f"copilot.{collection_name}",
            "count": 100,
            "size": 50000,
            "storageSize": 40960,
            "avgObjSize": 500,
            "totalIndexSize": 8192,
            "indexSizes": {
                "_id_": 4096,
                "status_1": 4096
            }
        }

    mock_db.command = mock_command

    # Call collect_metrics
    try:
        exporter.collect_metrics(mock_client)
        print("✓ collect_metrics executes without errors")
        return True
    except Exception as e:
        print(f"✗ collect_metrics failed: {e}")
        return False


def test_target_collections():
    """Test that TARGET_COLLECTIONS is defined."""
    import mongo_collstats_exporter as exporter

    assert hasattr(exporter, 'TARGET_COLLECTIONS'), "TARGET_COLLECTIONS not defined"
    assert isinstance(exporter.TARGET_COLLECTIONS, list), "TARGET_COLLECTIONS should be a list"
    assert len(exporter.TARGET_COLLECTIONS) > 0, "TARGET_COLLECTIONS should not be empty"

    # Check that expected collections are present
    expected = ["archives", "messages", "chunks", "threads", "summaries", "reports", "sources"]
    for coll in expected:
        assert coll in exporter.TARGET_COLLECTIONS, f"Collection '{coll}' not in TARGET_COLLECTIONS"

    print("✓ TARGET_COLLECTIONS is properly defined")
    return True


def main():
    """Run all tests."""
    print("Testing MongoDB CollStats Exporter...")
    print("=" * 60)

    tests = [
        test_exporter_imports,
        test_exporter_configuration,
        test_exporter_metrics,
        test_target_collections,
        test_get_collection_stats,
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
