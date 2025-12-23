# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Thread and Message models."""

from datetime import datetime, timezone, timedelta

from copilot_consensus import Thread, Message


class TestMessage:
    """Tests for Message model."""

    def test_message_creation(self):
        """Test creating a message."""
        timestamp = datetime.now(timezone.utc)
        msg = Message(
            message_id="msg-123",
            author="user@example.com",
            subject="Test Subject",
            content="Test content",
            timestamp=timestamp,
        )

        assert msg.message_id == "msg-123"
        assert msg.author == "user@example.com"
        assert msg.subject == "Test Subject"
        assert msg.content == "Test content"
        assert msg.timestamp == timestamp
        assert msg.in_reply_to is None
        assert msg.metadata == {}

    def test_message_with_reply_to(self):
        """Test message with in_reply_to field."""
        timestamp = datetime.now(timezone.utc)
        msg = Message(
            message_id="msg-456",
            author="user@example.com",
            subject="Re: Test",
            content="Reply content",
            timestamp=timestamp,
            in_reply_to="msg-123",
        )

        assert msg.in_reply_to == "msg-123"

    def test_message_with_metadata(self):
        """Test message with metadata."""
        timestamp = datetime.now(timezone.utc)
        metadata = {"source": "mbox", "archived": True}
        msg = Message(
            message_id="msg-789",
            author="user@example.com",
            subject="Test",
            content="Content",
            timestamp=timestamp,
            metadata=metadata,
        )

        assert msg.metadata == metadata
        assert msg.metadata["source"] == "mbox"
        assert msg.metadata["archived"] is True


class TestThread:
    """Tests for Thread model."""

    def test_thread_creation_empty(self):
        """Test creating an empty thread."""
        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
        )

        assert thread.thread_id == "thread-1"
        assert thread.subject == "Test Thread"
        assert thread.messages == []
        assert thread.started_at is None
        assert thread.last_activity_at is None
        assert thread.metadata == {}

    def test_thread_with_messages(self):
        """Test thread with messages."""
        base_time = datetime.now(timezone.utc)
        messages = [
            Message(
                message_id="msg-1",
                author="user1@example.com",
                subject="Initial message",
                content="First message",
                timestamp=base_time,
            ),
            Message(
                message_id="msg-2",
                author="user2@example.com",
                subject="Re: Initial message",
                content="Reply",
                timestamp=base_time + timedelta(hours=1),
                in_reply_to="msg-1",
            ),
            Message(
                message_id="msg-3",
                author="user3@example.com",
                subject="Re: Initial message",
                content="Another reply",
                timestamp=base_time + timedelta(hours=2),
                in_reply_to="msg-1",
            ),
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
        )

        assert len(thread.messages) == 3
        assert thread.messages[0].message_id == "msg-1"
        assert thread.messages[1].message_id == "msg-2"
        assert thread.messages[2].message_id == "msg-3"

    def test_thread_timestamps_auto_set(self):
        """Test that timestamps are automatically set from messages."""
        base_time = datetime.now(timezone.utc)
        messages = [
            Message(
                message_id="msg-1",
                author="user1@example.com",
                subject="Test",
                content="Content 1",
                timestamp=base_time + timedelta(hours=2),
            ),
            Message(
                message_id="msg-2",
                author="user2@example.com",
                subject="Test",
                content="Content 2",
                timestamp=base_time,  # Earliest
            ),
            Message(
                message_id="msg-3",
                author="user3@example.com",
                subject="Test",
                content="Content 3",
                timestamp=base_time + timedelta(hours=5),  # Latest
            ),
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
        )

        # started_at should be the earliest timestamp
        assert thread.started_at == base_time
        # last_activity_at should be the latest timestamp
        assert thread.last_activity_at == base_time + timedelta(hours=5)

    def test_thread_timestamps_explicit(self):
        """Test that explicit timestamps are preserved."""
        base_time = datetime.now(timezone.utc)
        explicit_start = base_time - timedelta(days=1)
        explicit_end = base_time + timedelta(days=1)

        messages = [
            Message(
                message_id="msg-1",
                author="user@example.com",
                subject="Test",
                content="Content",
                timestamp=base_time,
            ),
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
            started_at=explicit_start,
            last_activity_at=explicit_end,
        )

        # Explicit timestamps should be preserved
        assert thread.started_at == explicit_start
        assert thread.last_activity_at == explicit_end

    def test_thread_message_count(self):
        """Test message_count property."""
        messages = [
            Message(
                message_id=f"msg-{i}",
                author=f"user{i}@example.com",
                subject="Test",
                content="Content",
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(5)
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
        )

        assert thread.message_count == 5

    def test_thread_reply_count(self):
        """Test reply_count property."""
        messages = [
            Message(
                message_id=f"msg-{i}",
                author=f"user{i}@example.com",
                subject="Test",
                content="Content",
                timestamp=datetime.now(timezone.utc),
            )
            for i in range(6)
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
        )

        # 6 messages means 5 replies (excluding root message)
        assert thread.reply_count == 5

    def test_thread_reply_count_zero(self):
        """Test reply_count for thread with no messages."""
        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=[],
        )

        assert thread.reply_count == 0

    def test_thread_participant_count(self):
        """Test participant_count property."""
        base_time = datetime.now(timezone.utc)
        messages = [
            Message(
                message_id="msg-1",
                author="alice@example.com",
                subject="Test",
                content="Content",
                timestamp=base_time,
            ),
            Message(
                message_id="msg-2",
                author="bob@example.com",
                subject="Test",
                content="Content",
                timestamp=base_time + timedelta(hours=1),
            ),
            Message(
                message_id="msg-3",
                author="alice@example.com",  # Duplicate
                subject="Test",
                content="Content",
                timestamp=base_time + timedelta(hours=2),
            ),
            Message(
                message_id="msg-4",
                author="charlie@example.com",
                subject="Test",
                content="Content",
                timestamp=base_time + timedelta(hours=3),
            ),
        ]

        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=messages,
        )

        # 3 unique participants: alice, bob, charlie
        assert thread.participant_count == 3

    def test_thread_participant_count_zero(self):
        """Test participant_count for empty thread."""
        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            messages=[],
        )

        assert thread.participant_count == 0

    def test_thread_with_metadata(self):
        """Test thread with metadata."""
        metadata = {"source": "mailing-list", "archived": True}
        thread = Thread(
            thread_id="thread-1",
            subject="Test Thread",
            metadata=metadata,
        )

        assert thread.metadata == metadata
        assert thread.metadata["source"] == "mailing-list"
