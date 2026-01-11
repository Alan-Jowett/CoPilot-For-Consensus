# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for message parser."""

import os

import pytest
from app.parser import MessageParser


class TestMessageParser:
    """Tests for MessageParser."""

    def test_parse_mbox(self, sample_mbox_file):
        """Test parsing an mbox file."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-1")

        assert len(messages) == 2

        # Check first message
        msg1 = messages[0]
        assert msg1["message_id"] == "msg1@example.com"
        assert msg1["archive_id"] == "test-archive-1"
        assert msg1["subject"] == "QUIC connection migration"
        assert msg1["from"]["email"] == "alice@example.com"
        assert msg1["from"]["name"] == "Alice Developer"
        assert "draft-ietf-quic-transport-34" in msg1["draft_mentions"]

        # Check second message
        msg2 = messages[1]
        assert msg2["message_id"] == "msg2@example.com"
        assert msg2["in_reply_to"] == "msg1@example.com"
        assert "RFC 9000" in msg2["draft_mentions"]

    def test_parse_corrupted_mbox(self, corrupted_mbox_file):
        """Test parsing a corrupted mbox file."""
        from app.exceptions import MessageParsingError
        parser = MessageParser()

        # Corrupted file may still parse some messages, or raise exception if all fail
        try:
            messages = parser.parse_mbox(corrupted_mbox_file, "test-archive-2")
            # If it succeeds, should return a list
            assert isinstance(messages, list)
        except MessageParsingError:
            # If all messages fail to parse, should raise exception
            pass

    def test_parse_nonexistent_file(self):
        """Test parsing a nonexistent file."""
        from app.exceptions import MboxFileError
        parser = MessageParser()

        # Should raise MboxFileError for non-existent file
        with pytest.raises(MboxFileError):
            parser.parse_mbox("/nonexistent/file.mbox", "test-archive-3")

    def test_message_without_message_id(self, temp_dir):
        """Test handling message without Message-ID."""
        from app.exceptions import MessageParsingError
        # Create mbox with message missing Message-ID
        mbox_path = os.path.join(temp_dir, "no_id.mbox")
        with open(mbox_path, "w") as f:
            f.write("""From test@example.com Mon Jan 01 00:00:00 2024
From: test@example.com
Subject: Test
Date: Mon, 01 Jan 2024 12:00:00 +0000

Body text
""")

        parser = MessageParser()
        # If all messages fail to parse (in this case, the only message),
        # parse_mbox should raise MessageParsingError
        with pytest.raises(MessageParsingError, match="Failed to parse any messages"):
            parser.parse_mbox(mbox_path, "test-archive-4")

    def test_extract_headers(self, sample_mbox_file):
        """Test header extraction."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-5")

        msg = messages[0]
        assert msg["subject"] == "QUIC connection migration"
        assert msg["from"]["email"] == "alice@example.com"
        assert msg["to"][0]["email"] == "quic@ietf.org"
        assert msg["date"] is not None

    def test_thread_id_assignment(self, sample_mbox_file):
        """Test thread_id assignment."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-6")

        # First message: thread_id should equal message_id (no in_reply_to)
        msg1 = messages[0]
        assert msg1["thread_id"] == msg1["message_id"]

        # Second message: thread_id should equal in_reply_to
        msg2 = messages[1]
        assert msg2["thread_id"] == msg2["in_reply_to"]

    def test_body_normalization(self, sample_mbox_file):
        """Test that body is normalized."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-7")

        msg1 = messages[0]
        # Signature should be removed
        assert "Alice Developer" not in msg1["body_normalized"]
        assert "Example Corp" not in msg1["body_normalized"]
        # Content should remain
        assert "connection migration" in msg1["body_normalized"]

        msg2 = messages[1]
        # Quoted text should be removed
        assert ">" not in msg2["body_normalized"]
        # Original content should remain
        assert "I agree" in msg2["body_normalized"]

    def test_draft_detection_in_parsing(self, sample_mbox_file):
        """Test draft detection during parsing."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-8")

        msg1 = messages[0]
        assert len(msg1["draft_mentions"]) > 0
        assert "draft-ietf-quic-transport-34" in msg1["draft_mentions"]

        msg2 = messages[1]
        assert len(msg2["draft_mentions"]) > 0
        assert "RFC 9000" in msg2["draft_mentions"]

    def test_references_parsing(self, sample_mbox_file):
        """Test parsing of References header."""
        parser = MessageParser()

        messages = parser.parse_mbox(sample_mbox_file, "test-archive-9")

        msg2 = messages[1]
        assert len(msg2["references"]) == 1
        assert "msg1@example.com" in msg2["references"]


class TestMessageParserFromBytes:
    """Tests for bytes-based parsing in MessageParser."""

    def test_parse_mbox_from_bytes(self, sample_mbox_content):
        """Test parsing mbox content from bytes."""
        parser = MessageParser()

        # Convert string content to bytes
        content_bytes = sample_mbox_content.encode('utf-8')
        messages = parser.parse_mbox_from_bytes(content_bytes, "test-archive-bytes-1")

        assert len(messages) == 2

        # Check first message
        msg1 = messages[0]
        assert msg1["message_id"] == "msg1@example.com"
        assert msg1["archive_id"] == "test-archive-bytes-1"
        assert msg1["subject"] == "QUIC connection migration"
        assert msg1["from"]["email"] == "alice@example.com"
        assert msg1["from"]["name"] == "Alice Developer"
        assert "draft-ietf-quic-transport-34" in msg1["draft_mentions"]

        # Check second message
        msg2 = messages[1]
        assert msg2["message_id"] == "msg2@example.com"
        assert msg2["in_reply_to"] == "msg1@example.com"
        assert "RFC 9000" in msg2["draft_mentions"]

    def test_parse_mbox_from_bytes_empty_content(self):
        """Test parsing empty bytes content."""
        parser = MessageParser()

        # Empty content should return empty list (no messages)
        messages = parser.parse_mbox_from_bytes(b"", "test-archive-bytes-2")
        assert messages == []

    def test_parse_mbox_from_bytes_invalid_utf8(self):
        """Test parsing content with invalid UTF-8 sequences."""
        parser = MessageParser()

        # Create content with invalid UTF-8 byte sequence
        # but still parseable structure
        content = b"""From test@example.com Mon Jan 01 00:00:00 2024
From: test@example.com
Subject: Test with \xff\xfe invalid bytes
Message-ID: <test@example.com>
Date: Mon, 01 Jan 2024 12:00:00 +0000

Body with invalid UTF-8 \xff\xfe sequence
"""

        # Should handle gracefully with 'replace' error handling
        messages = parser.parse_mbox_from_bytes(content, "test-archive-bytes-3")

        # Should still parse the message
        assert len(messages) == 1
        assert messages[0]["message_id"] == "test@example.com"

    def test_parse_mbox_from_bytes_message_without_message_id(self):
        """Test handling message without Message-ID in bytes content."""
        from app.exceptions import MessageParsingError
        parser = MessageParser()

        content = b"""From test@example.com Mon Jan 01 00:00:00 2024
From: test@example.com
Subject: Test
Date: Mon, 01 Jan 2024 12:00:00 +0000

Body text
"""

        # Should raise MessageParsingError when all messages fail
        with pytest.raises(MessageParsingError, match="Failed to parse any messages"):
            parser.parse_mbox_from_bytes(content, "test-archive-bytes-4")

    def test_parse_mbox_from_bytes_multiple_messages(self, sample_mbox_content):
        """Test parsing multiple messages from bytes."""
        parser = MessageParser()

        content_bytes = sample_mbox_content.encode('utf-8')
        messages = parser.parse_mbox_from_bytes(content_bytes, "test-archive-bytes-5")

        # Should parse both messages
        assert len(messages) == 2
        assert messages[0]["message_id"] == "msg1@example.com"
        assert messages[1]["message_id"] == "msg2@example.com"

    def test_parse_mbox_from_bytes_thread_id_assignment(self, sample_mbox_content):
        """Test thread_id assignment in bytes-based parsing."""
        parser = MessageParser()

        content_bytes = sample_mbox_content.encode('utf-8')
        messages = parser.parse_mbox_from_bytes(content_bytes, "test-archive-bytes-6")

        # First message: thread_id should equal message_id (no in_reply_to)
        msg1 = messages[0]
        assert msg1["thread_id"] == msg1["message_id"]

        # Second message: thread_id should equal in_reply_to
        msg2 = messages[1]
        assert msg2["thread_id"] == msg2["in_reply_to"]

    def test_parse_mbox_from_bytes_body_normalization(self, sample_mbox_content):
        """Test that body is normalized in bytes-based parsing."""
        parser = MessageParser()

        content_bytes = sample_mbox_content.encode('utf-8')
        messages = parser.parse_mbox_from_bytes(content_bytes, "test-archive-bytes-7")

        msg1 = messages[0]
        # Signature should be removed
        assert "Alice Developer" not in msg1["body_normalized"]
        assert "Example Corp" not in msg1["body_normalized"]
        # Content should remain
        assert "connection migration" in msg1["body_normalized"]

        msg2 = messages[1]
        # Quoted text should be removed
        assert ">" not in msg2["body_normalized"]
        # Original content should remain
        assert "I agree" in msg2["body_normalized"]

    def test_parse_mbox_from_bytes_corrupted_content(self):
        """Test parsing corrupted bytes content."""
        from app.exceptions import MessageParsingError
        parser = MessageParser()

        # Corrupted content that doesn't look like mbox
        content = b"This is not a valid mbox file\n"

        # Should raise MessageParsingError
        with pytest.raises(MessageParsingError):
            parser.parse_mbox_from_bytes(content, "test-archive-bytes-8")

    def test_bytes_and_file_parsing_equivalence(self, sample_mbox_file, sample_mbox_content):
        """Test that bytes-based and file-based parsing produce equivalent results."""
        parser = MessageParser()

        # Parse from file
        messages_from_file = parser.parse_mbox(sample_mbox_file, "test-archive-equiv-1")

        # Parse from bytes
        content_bytes = sample_mbox_content.encode('utf-8')
        messages_from_bytes = parser.parse_mbox_from_bytes(content_bytes, "test-archive-equiv-2")

        # Should have same number of messages
        assert len(messages_from_file) == len(messages_from_bytes)

        # Compare key fields (excluding archive_id which differs)
        for msg_file, msg_bytes in zip(messages_from_file, messages_from_bytes):
            assert msg_file["message_id"] == msg_bytes["message_id"]
            assert msg_file["subject"] == msg_bytes["subject"]
            assert msg_file["from"] == msg_bytes["from"]
            assert msg_file["to"] == msg_bytes["to"]
            assert msg_file["body_normalized"] == msg_bytes["body_normalized"]
            assert msg_file["draft_mentions"] == msg_bytes["draft_mentions"]
