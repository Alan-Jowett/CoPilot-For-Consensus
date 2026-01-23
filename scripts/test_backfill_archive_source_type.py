#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for backfill_archive_source_type migration script."""

import pytest
from unittest.mock import Mock, patch

# Add scripts directory to path for imports
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from backfill_archive_source_type import backfill_archive_source_type


@pytest.fixture
def mock_document_store():
    """Create a mock document store for testing."""
    store = Mock()
    store.count = Mock(return_value=0)
    store.find = Mock(return_value=[])
    store.update_many = Mock()
    return store


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_no_documents_found(mock_create_store, mock_document_store):
    """Test migration when no legacy archives are found."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 0
    
    result = backfill_archive_source_type(dry_run=False)
    
    assert result["total_found"] == 0
    assert result["updated"] == 0
    assert result["errors"] == 0
    mock_document_store.update_many.assert_not_called()


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_dry_run_mode(mock_create_store, mock_document_store):
    """Test migration in dry-run mode does not modify database."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 100
    mock_document_store.find.return_value = [
        {"_id": "doc1", "archive_id": "archive1", "source": "test-source"},
        {"_id": "doc2", "archive_id": "archive2", "source": "test-source2"},
    ]
    
    result = backfill_archive_source_type(dry_run=True)
    
    assert result["total_found"] == 100
    assert result["updated"] == 0
    assert result["errors"] == 0
    assert result["dry_run"] is True
    mock_document_store.update_many.assert_not_called()


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_live_mode_updates_documents(mock_create_store, mock_document_store):
    """Test migration in live mode updates documents."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 50
    mock_document_store.find.return_value = [
        {"_id": "doc1", "archive_id": "archive1", "source": "test-source"},
    ]
    
    # Mock update result
    update_result = Mock()
    update_result.modified_count = 50
    mock_document_store.update_many.return_value = update_result
    
    result = backfill_archive_source_type(dry_run=False)
    
    assert result["total_found"] == 50
    assert result["updated"] == 50
    assert result["errors"] == 0
    assert "timestamp" in result
    
    # Verify update was called with correct parameters
    mock_document_store.update_many.assert_called_once()
    call_args = mock_document_store.update_many.call_args
    assert call_args[0][0] == "archives"
    assert call_args[0][1] == {"source_type": {"$exists": False}}
    assert call_args[0][2] == {"$set": {"source_type": "local"}}


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_with_limit(mock_create_store, mock_document_store):
    """Test migration with document limit."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 1000
    mock_document_store.find.return_value = [
        {"_id": f"doc{i}", "archive_id": f"archive{i}", "source": "test-source"}
        for i in range(100)
    ]
    
    # Mock update result
    update_result = Mock()
    update_result.modified_count = 100
    mock_document_store.update_many.return_value = update_result
    
    result = backfill_archive_source_type(dry_run=False, limit=100)
    
    assert result["total_found"] == 1000
    assert result["updated"] == 100
    assert result["errors"] == 0
    
    # Verify limit was applied in find call
    mock_document_store.find.assert_called()
    call_args = mock_document_store.find.call_args
    assert call_args[1]["limit"] == 100


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_handles_update_error(mock_create_store, mock_document_store):
    """Test migration handles database update errors gracefully."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 10
    mock_document_store.find.return_value = [
        {"_id": "doc1", "archive_id": "archive1", "source": "test-source"},
    ]
    mock_document_store.update_many.side_effect = Exception("Database connection error")
    
    result = backfill_archive_source_type(dry_run=False)
    
    assert result["total_found"] == 10
    assert result["updated"] == 0
    assert result["errors"] == 1
    assert "error_message" in result
    assert "Database connection error" in result["error_message"]


@patch("backfill_archive_source_type.create_document_store")
def test_backfill_query_format(mock_create_store, mock_document_store):
    """Test that migration uses correct query to find legacy documents."""
    mock_create_store.return_value = mock_document_store
    mock_document_store.count.return_value = 5
    mock_document_store.find.return_value = []
    
    update_result = Mock()
    update_result.modified_count = 5
    mock_document_store.update_many.return_value = update_result
    
    backfill_archive_source_type(dry_run=False)
    
    # Verify count was called with correct query
    count_call = mock_document_store.count.call_args
    assert count_call[0][0] == "archives"
    assert count_call[0][1] == {"source_type": {"$exists": False}}
