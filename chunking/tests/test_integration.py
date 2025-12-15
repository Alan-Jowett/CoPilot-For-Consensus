# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for the chunking service."""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
import uuid

from app.service import ChunkingService
from copilot_chunking import TokenWindowChunker, create_chunker


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
    messages = [
        {
            "message_id": "<test@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "a1b2c3d4e5f6789",
            "body_normalized": (
                "This is a test message that contains enough text to be split "
                "into multiple chunks. " * 20
            ),
            "from": {"email": "user@example.com", "name": "Test User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Test Subject",
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
        "parsed_message_ids": ["<test@example.com>"],
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
        messages = [
            {
                "message_id": f"<test-{strategy_name}@example.com>",
                "thread_id": "<thread@example.com>",
                "archive_id": "a1b2c3d4e5f6789",
                "body_normalized": (
                    "This is a test sentence. Another sentence follows. "
                    "Yet another sentence here. And one more for good measure. " * 10
                ),
                "from": {"email": "user@example.com", "name": "Test User"},
                "date": "2023-10-15T12:00:00Z",
                "subject": "Test Subject",
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
            "parsed_message_ids": [f"<test-{strategy_name}@example.com>"],
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
    messages = [
        {
            "message_id": "<large@example.com>",
            "thread_id": "<thread@example.com>",
            "archive_id": "a1b2c3d4e5f6789",
            "body_normalized": large_text,
            "from": {"email": "user@example.com", "name": "Test User"},
            "date": "2023-10-15T12:00:00Z",
            "subject": "Large Message",
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
        "parsed_message_ids": ["<large@example.com>"],
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
