# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup requeue utility."""

import pytest
from unittest.mock import Mock

from copilot_startup import StartupRequeue


class TestStartupRequeue:
    """Test cases for StartupRequeue utility."""
    
    def test_requeue_incomplete_archives(self):
        """Test requeuing incomplete archives."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        mock_metrics = Mock()
        
        # Mock incomplete documents
        incomplete_archives = [
            {
                "archive_id": "archive-001",
                "file_path": "/data/archives/test1.mbox",
                "source": "test-source",
                "message_count": 10,
                "status": "pending",
            },
            {
                "archive_id": "archive-002",
                "file_path": "/data/archives/test2.mbox",
                "source": "test-source",
                "message_count": 5,
                "status": "processing",
            },
        ]
        
        mock_store.query_documents.return_value = incomplete_archives
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
            metrics_collector=mock_metrics,
        )
        
        # Execute requeue
        count = requeue.requeue_incomplete(
            collection="archives",
            query={"status": {"$in": ["pending", "processing"]}},
            event_type="ArchiveIngested",
            routing_key="archive.ingested",
            id_field="archive_id",
            build_event_data=lambda doc: {
                "archive_id": doc.get("archive_id"),
                "file_path": doc.get("file_path"),
                "source": doc.get("source"),
                "message_count": doc.get("message_count", 0),
            },
            limit=1000,
        )
        
        # Verify query was called correctly
        mock_store.query_documents.assert_called_once_with(
            collection="archives",
            filter_dict={"status": {"$in": ["pending", "processing"]}},
            limit=1000,
        )
        
        # Verify events were published
        assert mock_publisher.publish.call_count == 2
        
        # Verify first event
        first_call = mock_publisher.publish.call_args_list[0]
        assert first_call[1]["event_type"] == "ArchiveIngested"
        assert first_call[1]["routing_key"] == "archive.ingested"
        assert first_call[1]["data"]["archive_id"] == "archive-001"
        assert first_call[1]["data"]["message_count"] == 10
        
        # Verify second event
        second_call = mock_publisher.publish.call_args_list[1]
        assert second_call[1]["event_type"] == "ArchiveIngested"
        assert second_call[1]["data"]["archive_id"] == "archive-002"
        
        # Verify metrics
        mock_metrics.increment.assert_called_once_with(
            "startup_requeue_documents_total",
            2,
            tags={"collection": "archives"}
        )
        
        # Verify return count
        assert count == 2
    
    def test_requeue_incomplete_chunks(self):
        """Test requeuing chunks without embeddings."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        
        # Mock incomplete chunks
        incomplete_chunks = [
            {
                "_id": "abcd1234abcd1234",
                "message_doc_id": "aabbccddaabbccdd",
                "embedding_generated": False,
            },
            {
                "_id": "abcd5678abcd5678",
                "message_doc_id": "aabbccddaabbccdd",
                "embedding_generated": False,
            },
        ]
        
        mock_store.query_documents.return_value = incomplete_chunks
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
        )
        
        # Execute requeue
        count = requeue.requeue_incomplete(
            collection="chunks",
            query={"embedding_generated": False},
            event_type="ChunksPrepared",
            routing_key="chunks.prepared",
            id_field="_id",
            build_event_data=lambda doc: {
                "chunk_ids": [doc.get("_id")],
                "message_doc_ids": [doc.get("message_doc_id")],
            },
        )
        
        # Verify events were published
        assert mock_publisher.publish.call_count == 2
        assert count == 2
    
    def test_requeue_no_incomplete_documents(self):
        """Test requeue when no incomplete documents exist."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        mock_metrics = Mock()
        
        # No incomplete documents
        mock_store.query_documents.return_value = []
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
            metrics_collector=mock_metrics,
        )
        
        # Execute requeue
        count = requeue.requeue_incomplete(
            collection="archives",
            query={"status": "pending"},
            event_type="ArchiveIngested",
            routing_key="archive.ingested",
            id_field="archive_id",
            build_event_data=lambda doc: {"archive_id": doc.get("archive_id")},
        )
        
        # Verify no events were published
        assert mock_publisher.publish.call_count == 0
        
        # Verify no metrics were emitted
        assert mock_metrics.increment.call_count == 0
        
        # Verify return count is zero
        assert count == 0
    
    def test_requeue_handles_individual_failures(self):
        """Test requeue continues on individual document failures."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        
        # Mock incomplete documents
        incomplete_docs = [
            {"thread_id": "thread-001", "summary_id": None},
            {"thread_id": "thread-002", "summary_id": None},
            {"thread_id": "thread-003", "summary_id": None},
        ]
        
        mock_store.query_documents.return_value = incomplete_docs
        
        # Make second publish fail
        mock_publisher.publish.side_effect = [
            None,  # First succeeds
            Exception("Network error"),  # Second fails
            None,  # Third succeeds
        ]
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
        )
        
        # Execute requeue
        count = requeue.requeue_incomplete(
            collection="threads",
            query={"summary_id": None},
            event_type="SummarizationRequested",
            routing_key="summarization.requested",
            id_field="thread_id",
            build_event_data=lambda doc: {
                "thread_ids": [doc.get("thread_id")],
            },
        )
        
        # Verify all 3 publish attempts were made
        assert mock_publisher.publish.call_count == 3
        
        # Verify only 2 succeeded
        assert count == 2
    
    def test_requeue_with_limit(self):
        """Test requeue respects limit parameter."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        
        # Mock 100 incomplete documents
        incomplete_docs = [
            {"_id": f"{i:016x}", "message_doc_id": "aabbccddaabbccdd"}
            for i in range(100)
        ]
        
        mock_store.query_documents.return_value = incomplete_docs
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
        )
        
        # Execute requeue with limit
        requeue.requeue_incomplete(
            collection="chunks",
            query={"embedding_generated": False},
            event_type="ChunksPrepared",
            routing_key="chunks.prepared",
            id_field="_id",
            build_event_data=lambda doc: {"chunk_ids": [doc.get("_id")]},
            limit=50,
        )
        
        # Verify query used limit
        mock_store.query_documents.assert_called_once()
        call_kwargs = mock_store.query_documents.call_args[1]
        assert call_kwargs["limit"] == 50
    
    def test_requeue_emits_error_metrics_on_failure(self):
        """Test error metrics are emitted on query failure."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()
        mock_metrics = Mock()
        
        # Make query fail
        mock_store.query_documents.side_effect = Exception("Database unavailable")
        
        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
            metrics_collector=mock_metrics,
        )
        
        # Execute requeue should raise
        with pytest.raises(Exception, match="Database unavailable"):
            requeue.requeue_incomplete(
                collection="archives",
                query={"status": "pending"},
                event_type="ArchiveIngested",
                routing_key="archive.ingested",
                id_field="archive_id",
                build_event_data=lambda doc: {},
            )
        
        # Verify error metric was emitted
        mock_metrics.increment.assert_called_once()
        call_args = mock_metrics.increment.call_args
        assert call_args[0][0] == "startup_requeue_errors_total"
        assert call_args[0][1] == 1
        assert call_args[1]["tags"]["collection"] == "archives"
        assert call_args[1]["tags"]["error_type"] == "Exception"
