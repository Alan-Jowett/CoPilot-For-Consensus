# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the chunking service."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from app.service import ChunkingService
from copilot_chunking import TokenWindowChunker, create_chunker
from copilot_schema_validation import generate_message_doc_id


@pytest.mark.integration
def test_end_to_end_chunking(document_store):
    """Test end-to-end chunking with real chunker."""
    # Create real chunker
    chunker = TokenWindowChunker(chunk_size=100, overlap=20, min_chunk_size=50)

    # Create mocks for publisher/subscriber
    mock_publisher = Mock()
    mock_subscriber = Mock()

    now = datetime.now(timezone.utc).isoformat()

    # Setup test messages in document store
    archive_id = "feedfacecafebeef"
    message_id = "<test@example.com>"
    date = "2023-10-15T12:00:00Z"
    sender_email = "user@example.com"
    subject = "Test Subject"

    # Generate message_doc_id using the same logic as the parsing service
    message_doc_id = generate_message_doc_id(
        archive_id=archive_id,
        message_id=message_id,
        date=date,
        sender_email=sender_email,
        subject=subject
    )

    messages = [
        {
            "_id": message_doc_id,
            "message_id": message_id,
            "thread_id": "feedfacefeedface",
            "archive_id": archive_id,
            "body_normalized": (
                "This is a test message that contains enough text to be split "
                "into multiple chunks. " * 20
            ),
            "from": {"email": sender_email, "name": "Test User"},
            "date": date,
            "subject": subject,
            "draft_mentions": [],
            "created_at": now,
        }
    ]
    for msg in messages:
        document_store.insert_document("messages", msg)

    # Create service
    service = ChunkingService(
        document_store=document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=chunker,
    )

    # Process messages
    event_data = {
        "archive_id": messages[0]["archive_id"],
        "message_doc_ids": [message_doc_id],
    }

    service.process_messages(event_data)

    # Verify chunks were created and stored
    chunks = document_store.query_documents("chunks", {}, limit=100)
    assert len(chunks) > 1

    # Verify ChunksPrepared event was published
    assert mock_publisher.publish.call_count == 1
    publish_call = mock_publisher.publish.call_args
    assert publish_call[1]["routing_key"] == "chunks.prepared"

    event_data = publish_call[1]["event"]["data"]
    assert event_data["chunk_count"] > 1
    assert len(event_data["chunk_ids"]) > 1
    assert event_data["chunks_ready"] is True


@pytest.mark.integration
def test_different_chunking_strategies(document_store):
    """Test chunking with different strategies."""
    strategies = [
        ("token_window", {"chunk_size": 100, "overlap": 20}),
        ("semantic", {"chunk_size": 100}),
    ]

    for strategy_name, params in strategies:
        # Create chunker with strategy
        chunker = create_chunker(strategy_name, **params)

        # Create mocks for publisher/subscriber
        mock_publisher = Mock()
        mock_subscriber = Mock()

        now = datetime.now(timezone.utc).isoformat()

        # Setup test message
        archive_id = "feedfacecafebeef"
        message_id = f"<test-{strategy_name}@example.com>"
        date = "2023-10-15T12:00:00Z"
        sender_email = "user@example.com"
        subject = "Test Subject"

        # Generate message_doc_id using the same logic as the parsing service
        message_doc_id = generate_message_doc_id(
            archive_id=archive_id,
            message_id=message_id,
            date=date,
            sender_email=sender_email,
            subject=subject
        )

        messages = [
            {
                "_id": message_doc_id,
                "message_id": message_id,
                "thread_id": "feedfacefeedface",
                "archive_id": archive_id,
                "body_normalized": (
                    "This is a test sentence. Another sentence follows. "
                    "Yet another sentence here. And one more for good measure. " * 10
                ),
                "from": {"email": sender_email, "name": "Test User"},
                "date": date,
                "subject": subject,
                "draft_mentions": [],
                "created_at": now,
            }
        ]
        for msg in messages:
            document_store.insert_document("messages", msg)

        # Create service
        service = ChunkingService(
            document_store=document_store,
            publisher=mock_publisher,
            subscriber=mock_subscriber,
            chunker=chunker,
        )

        # Process messages
        event_data = {
            "archive_id": messages[0]["archive_id"],
            "message_doc_ids": [message_doc_id],
        }

        service.process_messages(event_data)

        # Verify chunks were created
        chunks = document_store.query_documents("chunks", {}, limit=100)
        assert len(chunks) > 0, f"Strategy {strategy_name} failed"
        assert mock_publisher.publish.call_count == 1, f"Strategy {strategy_name} failed"


@pytest.mark.integration
def test_oversize_message_handling(document_store):
    """Test handling of very large messages."""
    # Create chunker with small chunk size to force many chunks
    chunker = TokenWindowChunker(chunk_size=50, overlap=10, min_chunk_size=20)

    # Create mocks for publisher/subscriber
    mock_publisher = Mock()
    mock_subscriber = Mock()

    now = datetime.now(timezone.utc).isoformat()

    # Create a very large message
    large_text = "word " * 2000  # 2000 words
    archive_id = "feedfacecafebeef"
    message_id = "<large@example.com>"
    date = "2023-10-15T12:00:00Z"
    sender_email = "user@example.com"
    subject = "Large Message"

    # Generate message_doc_id using the same logic as the parsing service
    message_doc_id = generate_message_doc_id(
        archive_id=archive_id,
        message_id=message_id,
        date=date,
        sender_email=sender_email,
        subject=subject
    )

    messages = [
        {
            "_id": message_doc_id,
            "message_id": message_id,
            "thread_id": "feedfacefeedface",
            "archive_id": archive_id,
            "body_normalized": large_text,
            "from": {"email": sender_email, "name": "Test User"},
            "date": date,
            "subject": subject,
            "draft_mentions": [],
            "created_at": now,
        }
    ]
    for msg in messages:
        document_store.insert_document("messages", msg)

    # Create service
    service = ChunkingService(
        document_store=document_store,
        publisher=mock_publisher,
        subscriber=mock_subscriber,
        chunker=chunker,
    )

    # Process messages
    event_data = {
        "archive_id": messages[0]["archive_id"],
        "message_doc_ids": [message_doc_id],
    }

    service.process_messages(event_data)

    # Verify many chunks were created
    chunks = document_store.query_documents("chunks", {}, limit=1000)
    assert len(chunks) > 10

    # Verify event includes all chunks
    publish_call = mock_publisher.publish.call_args
    event_data = publish_call[1]["event"]["data"]
    assert event_data["chunk_count"] > 10
    assert len(event_data["chunk_ids"]) == event_data["chunk_count"]
