# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for message parser."""

import os

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
        import pytest
        with pytest.raises(MboxFileError):
            parser.parse_mbox("/nonexistent/file.mbox", "test-archive-3")

    def test_message_without_message_id(self, temp_dir):
        """Test handling message without Message-ID."""
        from app.exceptions import RequiredFieldMissingError
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
        # Parse should succeed but skip the message without Message-ID
        # It should not raise if there's just one bad message
        messages = parser.parse_mbox(mbox_path, "test-archive-4")
        
        # Should skip message without Message-ID
        assert len(messages) == 0

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
        
        messages, _ = parser.parse_mbox(sample_mbox_file, "test-archive-6")
        
        # First message: thread_id should equal message_id (no in_reply_to)
        msg1 = messages[0]
        assert msg1["thread_id"] == msg1["message_id"]
        
        # Second message: thread_id should equal in_reply_to
        msg2 = messages[1]
        assert msg2["thread_id"] == msg2["in_reply_to"]

    def test_body_normalization(self, sample_mbox_file):
        """Test that body is normalized."""
        parser = MessageParser()
        
        messages, _ = parser.parse_mbox(sample_mbox_file, "test-archive-7")
        
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
        
        messages, _ = parser.parse_mbox(sample_mbox_file, "test-archive-8")
        
        msg1 = messages[0]
        assert len(msg1["draft_mentions"]) > 0
        assert "draft-ietf-quic-transport-34" in msg1["draft_mentions"]
        
        msg2 = messages[1]
        assert len(msg2["draft_mentions"]) > 0
        assert "RFC 9000" in msg2["draft_mentions"]

    def test_references_parsing(self, sample_mbox_file):
        """Test parsing of References header."""
        parser = MessageParser()
        
        messages, _ = parser.parse_mbox(sample_mbox_file, "test-archive-9")
        
        msg2 = messages[1]
        assert len(msg2["references"]) == 1
        assert "msg1@example.com" in msg2["references"]
