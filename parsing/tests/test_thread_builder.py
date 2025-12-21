# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for thread builder."""

import hashlib
from app.thread_builder import ThreadBuilder


def _generate_test_id(message_id: str) -> str:
    """Generate a simple test _id from message_id."""
    return hashlib.sha256(message_id.encode("utf-8")).hexdigest()[:16]


class TestThreadBuilder:
    """Tests for ThreadBuilder."""

    def test_build_single_message_thread(self):
        """Test building a thread from a single message."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Test Subject",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": ["RFC 9000"],
            }
        ]
        
        threads = builder.build_threads(messages)
        
        assert len(threads) == 1
        thread = threads[0]
        assert thread["thread_id"] == msg1_id
        assert thread["message_count"] == 1
        assert thread["subject"] == "Test Subject"
        assert len(thread["participants"]) == 1
        assert thread["draft_mentions"] == ["RFC 9000"]

    def test_build_multi_message_thread(self):
        """Test building a thread from multiple messages."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        msg2_id = _generate_test_id("msg2@example.com")
        msg3_id = _generate_test_id("msg3@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Test Subject",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": ["RFC 9000"],
            },
            {
                "_id": msg2_id,
                "message_id": "msg2@example.com",
                "archive_id": "archive1",
                "subject": "Re: Test Subject",
                "from": {"name": "Bob", "email": "bob@example.com"},
                "in_reply_to": "msg1@example.com",
                "date": "2024-01-01T13:00:00Z",
                "draft_mentions": ["RFC 9001"],
            },
            {
                "_id": msg3_id,
                "message_id": "msg3@example.com",
                "archive_id": "archive1",
                "subject": "Re: Test Subject",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": "msg2@example.com",
                "date": "2024-01-01T14:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        assert len(threads) == 1
        thread = threads[0]
        assert thread["thread_id"] == msg1_id
        assert thread["message_count"] == 3
        assert len(thread["participants"]) == 2  # Alice and Bob
        assert set(thread["draft_mentions"]) == {"RFC 9000", "RFC 9001"}

    def test_build_multiple_threads(self):
        """Test building multiple separate threads."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        msg2_id = _generate_test_id("msg2@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Thread 1",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": [],
            },
            {
                "_id": msg2_id,
                "message_id": "msg2@example.com",
                "archive_id": "archive1",
                "subject": "Thread 2",
                "from": {"name": "Bob", "email": "bob@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T13:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        assert len(threads) == 2
        thread_ids = {t["thread_id"] for t in threads}
        assert thread_ids == {msg1_id, msg2_id}

    def test_thread_date_range(self):
        """Test thread date range calculation."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        msg2_id = _generate_test_id("msg2@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Test",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": [],
            },
            {
                "_id": msg2_id,
                "message_id": "msg2@example.com",
                "archive_id": "archive1",
                "subject": "Re: Test",
                "from": {"name": "Bob", "email": "bob@example.com"},
                "in_reply_to": "msg1@example.com",
                "date": "2024-01-03T12:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        thread = threads[0]
        assert thread["first_message_date"] == "2024-01-01T12:00:00Z"
        assert thread["last_message_date"] == "2024-01-03T12:00:00Z"

    def test_participant_deduplication(self):
        """Test that participants are deduplicated by email."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        msg2_id = _generate_test_id("msg2@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Test",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": [],
            },
            {
                "_id": msg2_id,
                "message_id": "msg2@example.com",
                "archive_id": "archive1",
                "subject": "Re: Test",
                "from": {"name": "Alice Developer", "email": "alice@example.com"},
                "in_reply_to": "msg1@example.com",
                "date": "2024-01-01T13:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        thread = threads[0]
        # Should only have one participant despite two messages from same email
        assert len(thread["participants"]) == 1
        assert thread["participants"][0]["email"] == "alice@example.com"

    def test_draft_mention_aggregation(self):
        """Test draft mention aggregation across messages."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        msg2_id = _generate_test_id("msg2@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Test",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": ["RFC 9000", "RFC 9001"],
            },
            {
                "_id": msg2_id,
                "message_id": "msg2@example.com",
                "archive_id": "archive1",
                "subject": "Re: Test",
                "from": {"name": "Bob", "email": "bob@example.com"},
                "in_reply_to": "msg1@example.com",
                "date": "2024-01-01T13:00:00Z",
                "draft_mentions": ["RFC 9001", "draft-ietf-quic-transport-34"],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        thread = threads[0]
        # Should have unique draft mentions
        assert len(thread["draft_mentions"]) == 3
        assert set(thread["draft_mentions"]) == {"RFC 9000", "RFC 9001", "draft-ietf-quic-transport-34"}

    def test_empty_messages_list(self):
        """Test with empty messages list."""
        builder = ThreadBuilder()
        
        threads = builder.build_threads([])
        
        assert len(threads) == 0

    def test_missing_root_message(self):
        """Test handling of message with missing root (in_reply_to not in parsed set).
        
        When a message refers to a parent via in_reply_to that isn't in the parsed set,
        the message should be assigned its own _id as the thread root.
        """
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Re: Some earlier message",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": "parent@example.com",  # Parent not in parsed set
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        assert len(threads) == 1
        thread = threads[0]
        # Should use this message's own _id as the thread root
        assert thread["thread_id"] == msg1_id
        assert thread["message_count"] == 1

    def test_subject_cleaning(self):
        """Test subject line cleaning."""
        builder = ThreadBuilder()
        
        msg1_id = _generate_test_id("msg1@example.com")
        messages = [
            {
                "_id": msg1_id,
                "message_id": "msg1@example.com",
                "archive_id": "archive1",
                "subject": "Re: [QUIC] FWD: Test Subject",
                "from": {"name": "Alice", "email": "alice@example.com"},
                "in_reply_to": None,
                "date": "2024-01-01T12:00:00Z",
                "draft_mentions": [],
            },
        ]
        
        threads = builder.build_threads(messages)
        
        thread = threads[0]
        # Subject should be cleaned (Re:, [QUIC], FWD: removed)
        assert "Re:" not in thread["subject"]
        assert "FWD:" not in thread["subject"]
        assert "[QUIC]" not in thread["subject"]
        assert "Test Subject" in thread["subject"]
