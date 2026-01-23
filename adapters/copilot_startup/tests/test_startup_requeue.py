# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for startup requeue utility."""

import uuid
from datetime import datetime
from unittest.mock import Mock

import pytest

# Schema validation is required - install copilot_schema_validation via install_adapters.py
from copilot_schema_validation import create_schema_provider, validate_json
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
        call_args, call_kwargs = first_call
        assert call_kwargs["exchange"] == "copilot.events"
        assert call_kwargs["routing_key"] == "archive.ingested"
        assert call_kwargs["event"]["event_type"] == "ArchiveIngested"
        assert call_kwargs["event"]["data"]["archive_id"] == "archive-001"
        assert call_kwargs["event"]["data"]["message_count"] == 10
        assert "timestamp" in call_kwargs["event"]
        # Verify required envelope fields added in this PR
        assert "event_id" in call_kwargs["event"]
        assert call_kwargs["event"]["version"] == "1.0.0"
        # Validate event_id is a valid UUID
        try:
            uuid.UUID(call_kwargs["event"]["event_id"])
        except ValueError:
            pytest.fail(f"event_id is not a valid UUID: {call_kwargs['event']['event_id']}")

        # Verify second event
        second_call = mock_publisher.publish.call_args_list[1]
        call_args, call_kwargs = second_call
        assert call_kwargs["event"]["event_type"] == "ArchiveIngested"
        assert call_kwargs["event"]["data"]["archive_id"] == "archive-002"

        # Verify metrics
        mock_metrics.increment.assert_called_once_with(
            "startup_requeue_documents_total", 2, tags={"collection": "archives"}
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
                "token_count": 128,
            },
            {
                "_id": "abcd5678abcd5678",
                "message_doc_id": "aabbccddaabbccdd",
                "embedding_generated": False,
                "token_count": 256,
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
                "chunk_count": 1,
                "chunks_ready": True,
                "chunking_strategy": "requeue",
                "avg_chunk_size_tokens": doc.get("token_count", 0),
            },
        )

        # Verify events were published
        assert mock_publisher.publish.call_count == 2
        assert count == 2

    def test_requeue_chunks_prepared_schema_validation(self):
        """Test that requeued ChunksPrepared events validate against schema."""
        # Setup mocks
        mock_store = Mock()
        mock_publisher = Mock()

        # Mock incomplete chunk with all required fields
        incomplete_chunks = [
            {
                "_id": "abcd1234abcd1234",
                "message_doc_id": "aabbccddaabbccdd",
                "embedding_generated": False,
                "token_count": 128,
            },
        ]

        mock_store.query_documents.return_value = incomplete_chunks

        # Create requeue utility
        requeue = StartupRequeue(
            document_store=mock_store,
            publisher=mock_publisher,
        )

        # Execute requeue with proper event data structure
        count = requeue.requeue_incomplete(
            collection="chunks",
            query={"embedding_generated": False},
            event_type="ChunksPrepared",
            routing_key="chunks.prepared",
            id_field="_id",
            build_event_data=lambda doc: {
                "chunk_ids": [doc.get("_id")],
                "message_doc_ids": [doc.get("message_doc_id")],
                "chunk_count": 1,
                "chunks_ready": True,
                "chunking_strategy": "requeue",
                "avg_chunk_size_tokens": doc.get("token_count", 0),
            },
        )

        # Verify event was published
        assert mock_publisher.publish.call_count == 1
        assert count == 1

        # Get the published event
        call_args, call_kwargs = mock_publisher.publish.call_args
        event = call_kwargs["event"]

        # Validate the event against the actual ChunksPrepared JSON schema
        schema_provider = create_schema_provider()
        schema = schema_provider.get_schema("ChunksPrepared")
        is_valid, errors = validate_json(event, schema, schema_provider=schema_provider)

        # Assert validation passes
        assert is_valid, f"ChunksPrepared event failed schema validation: {errors}"

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
        incomplete_docs = [{"_id": f"{i:016x}", "message_doc_id": "aabbccddaabbccdd"} for i in range(100)]

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


class TestPublishEvent:
    """Tests for StartupRequeue.publish_event helper."""

    def test_publish_event_builds_event_and_calls_publisher(self):
        mock_publisher = Mock()
        requeue = StartupRequeue(document_store=Mock(), publisher=mock_publisher)

        requeue.publish_event(
            event_type="SummarizationRequested",
            routing_key="summarization.requested",
            event_data={"thread_ids": ["t1"], "archive_id": "a1"},
        )

        mock_publisher.publish.assert_called_once()
        call_kwargs = mock_publisher.publish.call_args.kwargs
        assert call_kwargs["exchange"] == "copilot.events"
        assert call_kwargs["routing_key"] == "summarization.requested"
        event = call_kwargs["event"]
        assert event["event_type"] == "SummarizationRequested"
        assert event["data"] == {"thread_ids": ["t1"], "archive_id": "a1"}
        # Timestamp should be ISO 8601 with offset (consistent with requeue_incomplete)
        datetime.fromisoformat(event["timestamp"])
        # Verify envelope fields are present
        assert "event_id" in event
        assert "version" in event
        assert event["version"] == "1.0.0"
        # Validate event_id is a valid UUID
        try:
            uuid.UUID(event["event_id"])
        except ValueError:
            pytest.fail(f"event_id is not a valid UUID: {event['event_id']}")

    def test_publish_event_propagates_errors(self):
        mock_publisher = Mock()
        mock_publisher.publish.side_effect = RuntimeError("publish failed")
        requeue = StartupRequeue(document_store=Mock(), publisher=mock_publisher)

        with pytest.raises(RuntimeError, match="publish failed"):
            requeue.publish_event(
                event_type="SummarizationRequested",
                routing_key="summarization.requested",
                event_data={},
            )

    def test_publish_event_envelope_schema_compliance(self):
        """Test that publish_event creates events with all required envelope fields."""
        mock_publisher = Mock()
        requeue = StartupRequeue(document_store=Mock(), publisher=mock_publisher)

        requeue.publish_event(
            event_type="TestEvent",
            routing_key="test.event",
            event_data={"test_field": "test_value"},
        )

        # Extract the event that was published
        event = mock_publisher.publish.call_args.kwargs["event"]

        # Verify all required envelope fields are present
        required_fields = {"event_type", "event_id", "timestamp", "version", "data"}
        assert set(event.keys()) == required_fields, (
            f"Event envelope should have exactly these fields: {required_fields}, "
            f"but got: {set(event.keys())}"
        )

        # Verify field types and formats
        assert isinstance(event["event_type"], str) and event["event_type"] == "TestEvent"
        assert isinstance(event["event_id"], str)
        uuid.UUID(event["event_id"])  # Raises ValueError if not a valid UUID
        assert isinstance(event["timestamp"], str)
        datetime.fromisoformat(event["timestamp"])  # Raises ValueError if not valid ISO-8601
        assert isinstance(event["version"], str) and event["version"] == "1.0.0"
        assert isinstance(event["data"], dict) and event["data"] == {"test_field": "test_value"}
