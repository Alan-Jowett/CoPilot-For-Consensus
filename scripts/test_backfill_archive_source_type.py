#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for backfill_archive_source_type migration script."""

from unittest.mock import Mock, patch, MagicMock

# Add scripts directory to path for imports
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from backfill_archive_source_type import backfill_archive_source_type


def _create_mock_mongo_client():
    """Create a mock MongoDB client for testing."""
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_archives = MagicMock()

    mock_client.__getitem__.return_value = mock_db
    mock_db.archives = mock_archives

    # Mock admin commands
    mock_client.admin.command.return_value = {"ok": 1}

    return mock_client, mock_db, mock_archives


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_no_documents_found(mock_mongo_class):
    """Test migration when no legacy archives are found."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 0

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False
    )

    assert result["total_found"] == 0
    assert result["updated"] == 0
    assert result["errors"] == 0
    mock_archives.update_many.assert_not_called()


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_dry_run_mode(mock_mongo_class):
    """Test migration in dry-run mode does not modify database."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 100
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = [
        {"_id": "doc1", "archive_id": "archive1", "source": "test-source"},
        {"_id": "doc2", "archive_id": "archive2", "source": "test-source2"},
    ]
    mock_archives.find.return_value = mock_cursor

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=True
    )

    assert result["total_found"] == 100
    assert result["updated"] == 0
    assert result["errors"] == 0
    assert result["dry_run"] is True
    mock_archives.update_many.assert_not_called()


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_live_mode_updates_documents(mock_mongo_class):
    """Test migration in live mode updates documents."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 50

    # Mock the find method to return a cursor-like object
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = [{"_id": "doc1", "archive_id": "archive1", "source": "test-source"}]
    mock_archives.find.return_value = mock_cursor

    # Mock update result
    update_result = Mock()
    update_result.modified_count = 50
    mock_archives.update_many.return_value = update_result

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False
    )

    assert result["total_found"] == 50
    assert result["updated"] == 50
    assert result["errors"] == 0
    assert "timestamp" in result

    # Verify update was called with correct parameters
    mock_archives.update_many.assert_called_once()
    call_args = mock_archives.update_many.call_args
    assert call_args[0][0] == {"source_type": {"$exists": False}}
    assert call_args[0][1] == {"$set": {"source_type": "local"}}


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_with_limit(mock_mongo_class):
    """Test migration with document limit."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 1000

    # Mock the find method with limit
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = [
        {"_id": f"doc{i}", "archive_id": f"archive{i}", "source": "test-source"} for i in range(100)
    ]
    mock_archives.find.return_value = mock_cursor

    # Mock update result
    update_result = Mock()
    update_result.modified_count = 100
    mock_archives.update_many.return_value = update_result

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False, limit=100
    )

    assert result["total_found"] == 1000
    assert result["updated"] == 100
    assert result["errors"] == 0

    # Verify limit was applied
    mock_cursor.limit.assert_called_with(100)


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_handles_update_error(mock_mongo_class):
    """Test migration handles database update errors gracefully after successful connection."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 10

    # Mock the find method
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = [{"_id": "doc1", "archive_id": "archive1", "source": "test-source"}]
    mock_archives.find.return_value = mock_cursor

    mock_archives.update_many.side_effect = Exception("Database update error")

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False
    )

    assert result["total_found"] == 10  # Count was successful before update error
    assert result["updated"] == 0
    assert result["errors"] == 1
    assert "error_message" in result
    assert "Database update error" in result["error_message"]


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_query_format(mock_mongo_class):
    """Test that migration uses correct query to find legacy documents."""
    mock_client, mock_db, mock_archives = _create_mock_mongo_client()
    mock_mongo_class.return_value = mock_client
    mock_archives.count_documents.return_value = 5

    # Mock the find method
    mock_cursor = MagicMock()
    mock_cursor.limit.return_value = []
    mock_archives.find.return_value = mock_cursor

    update_result = Mock()
    update_result.modified_count = 5
    mock_archives.update_many.return_value = update_result

    backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False
    )

    # Verify count was called with correct query
    mock_archives.count_documents.assert_called_with({"source_type": {"$exists": False}})


@patch("backfill_archive_source_type.MongoClient")
def test_backfill_connection_failure(mock_mongo_class):
    """Test migration handles connection failures gracefully."""
    mock_mongo_class.side_effect = Exception("Connection refused")

    result = backfill_archive_source_type(
        mongodb_host="localhost", mongodb_port=27017, mongodb_database="test", dry_run=False
    )

    assert result["total_found"] == 0
    assert result["updated"] == 0
    assert result["errors"] == 1
    assert "error_message" in result
    # Error message is generic to avoid leaking credentials
    assert result["error_message"] == "ConnectionError"

