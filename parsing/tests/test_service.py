# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for parsing service."""

import os
import pytest

from copilot_events import NoopPublisher, NoopSubscriber
from copilot_storage import InMemoryDocumentStore

from app.service import ParsingService


class TestParsingService:
    """Integration tests for ParsingService."""

    @pytest.fixture
    def document_store(self):
        """Create in-memory document store."""
        store = InMemoryDocumentStore()
        store.connect()
        return store

    @pytest.fixture
    def publisher(self):
        """Create noop publisher."""
        pub = NoopPublisher()
        pub.connect()
        return pub

    @pytest.fixture
    def subscriber(self):
        """Create noop subscriber."""
        sub = NoopSubscriber()
        sub.connect()
        return sub

    @pytest.fixture
    def service(self, document_store, publisher, subscriber):
        """Create parsing service."""
        return ParsingService(
            document_store=document_store,
            publisher=publisher,
            subscriber=subscriber,
        )

    def test_service_initialization(self, service):
        """Test service initialization."""
        assert service.document_store is not None
        assert service.publisher is not None
        assert service.subscriber is not None
        assert service.parser is not None
        assert service.thread_builder is not None

    def test_process_archive_success(self, service, sample_mbox_file):
        """Test successful archive processing."""
        archive_data = {
            "archive_id": "test-archive-1",
            "file_path": sample_mbox_file,
        }
        
        service.process_archive(archive_data)
        
        # Check stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2
        assert stats["threads_created"] == 1
        assert stats["last_processing_time_seconds"] > 0
        
        # Check document store
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 2
        
        threads = service.document_store.query_documents("threads", {})
        assert len(threads) == 1

    def test_process_archive_with_corrupted_file(self, service, corrupted_mbox_file):
        """Test processing corrupted archive."""
        archive_data = {
            "archive_id": "test-archive-2",
            "file_path": corrupted_mbox_file,
        }
        
        # Should handle gracefully
        service.process_archive(archive_data)
        
        # No messages should be parsed from corrupted file
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 0

    def test_process_archive_missing_file(self, service):
        """Test processing nonexistent archive."""
        archive_data = {
            "archive_id": "test-archive-3",
            "file_path": "/nonexistent/file.mbox",
        }
        
        # Should handle gracefully without crashing
        service.process_archive(archive_data)
        
        # No messages should be stored
        messages = service.document_store.query_documents("messages", {})
        assert len(messages) == 0

    def test_message_persistence(self, service, sample_mbox_file):
        """Test that messages are persisted correctly."""
        archive_data = {
            "archive_id": "test-archive-4",
            "file_path": sample_mbox_file,
        }
        
        service.process_archive(archive_data)
        
        # Retrieve messages
        messages = service.document_store.query_documents("messages", {})
        
        # Check required fields
        for msg in messages:
            assert "message_id" in msg
            assert "archive_id" in msg
            assert msg["archive_id"] == "test-archive-4"
            assert "thread_id" in msg
            assert "subject" in msg
            assert "from" in msg
            assert "body_normalized" in msg
            assert "draft_mentions" in msg
            assert "created_at" in msg

    def test_thread_persistence(self, service, sample_mbox_file):
        """Test that threads are persisted correctly."""
        archive_data = {
            "archive_id": "test-archive-5",
            "file_path": sample_mbox_file,
        }
        
        service.process_archive(archive_data)
        
        # Retrieve threads
        threads = service.document_store.query_documents("threads", {})
        
        assert len(threads) == 1
        thread = threads[0]
        
        # Check required fields
        assert "thread_id" in thread
        assert "archive_id" in thread
        assert thread["archive_id"] == "test-archive-5"
        assert "subject" in thread
        assert "participants" in thread
        assert "message_count" in thread
        assert thread["message_count"] == 2
        assert "draft_mentions" in thread
        assert "has_consensus" in thread
        assert "consensus_type" in thread
        assert "summary_id" in thread

    def test_draft_detection_integration(self, service, sample_mbox_file):
        """Test draft detection in full pipeline."""
        archive_data = {
            "archive_id": "test-archive-6",
            "file_path": sample_mbox_file,
        }
        
        service.process_archive(archive_data)
        
        # Check messages for draft mentions
        messages = service.document_store.query_documents("messages", {})
        
        draft_mentions_found = []
        for msg in messages:
            draft_mentions_found.extend(msg["draft_mentions"])
        
        # Should have detected drafts from the sample messages
        assert len(draft_mentions_found) > 0
        assert any("draft-ietf-quic-transport" in d for d in draft_mentions_found)
        assert any("RFC" in d for d in draft_mentions_found)

    def test_thread_relationships(self, service, sample_mbox_file):
        """Test thread relationship building."""
        archive_data = {
            "archive_id": "test-archive-7",
            "file_path": sample_mbox_file,
        }
        
        service.process_archive(archive_data)
        
        # Retrieve messages
        messages = service.document_store.query_documents("messages", {})
        
        # Both messages should be in the same thread
        thread_ids = [msg["thread_id"] for msg in messages]
        assert len(set(thread_ids)) == 1  # All same thread
        
        # The thread_id should be the root message
        root_msg = [m for m in messages if not m.get("in_reply_to")][0]
        assert all(tid == root_msg["message_id"] for tid in thread_ids)

    def test_get_stats(self, service, sample_mbox_file):
        """Test statistics reporting."""
        # Initial stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 0
        assert stats["messages_parsed"] == 0
        assert stats["threads_created"] == 0
        
        # Process archive
        archive_data = {
            "archive_id": "test-archive-8",
            "file_path": sample_mbox_file,
        }
        service.process_archive(archive_data)
        
        # Updated stats
        stats = service.get_stats()
        assert stats["archives_processed"] == 1
        assert stats["messages_parsed"] == 2
        assert stats["threads_created"] == 1
        assert stats["last_processing_time_seconds"] > 0
