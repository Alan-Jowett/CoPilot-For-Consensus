# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for message key generator functions."""

import pytest
from copilot_schema_validation.message_key_generator import (
    generate_message_key,
    generate_chunk_key,
)


class TestGenerateMessageKey:
    """Test suite for generate_message_key function."""

    def test_basic_key_generation(self):
        """Test basic message key generation with minimal fields."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        
        key = generate_message_key(archive_id, message_id)
        
        # Should return 16-character hex string
        assert isinstance(key, str)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic_generation(self):
        """Test that the same inputs always produce the same key."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        date = "2023-10-15T10:00:00Z"
        sender = "sender@example.com"
        subject = "Test Subject"
        
        key1 = generate_message_key(archive_id, message_id, date, sender, subject)
        key2 = generate_message_key(archive_id, message_id, date, sender, subject)
        
        assert key1 == key2

    def test_different_inputs_produce_different_keys(self):
        """Test that different inputs produce different keys."""
        archive_id = "abc123def4567890"
        
        key1 = generate_message_key(archive_id, "<msg1@example.com>")
        key2 = generate_message_key(archive_id, "<msg2@example.com>")
        
        assert key1 != key2

    def test_optional_fields_affect_key(self):
        """Test that optional fields affect the generated key."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        
        key_minimal = generate_message_key(archive_id, message_id)
        key_with_date = generate_message_key(
            archive_id, message_id, date="2023-10-15T10:00:00Z"
        )
        key_with_sender = generate_message_key(
            archive_id, message_id, sender_email="sender@example.com"
        )
        key_with_subject = generate_message_key(
            archive_id, message_id, subject="Test"
        )
        
        # All keys should be different
        keys = [key_minimal, key_with_date, key_with_sender, key_with_subject]
        assert len(set(keys)) == len(keys)

    def test_with_all_optional_fields(self):
        """Test key generation with all optional fields provided."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        date = "2023-10-15T10:00:00Z"
        sender = "sender@example.com"
        subject = "Test Subject"
        
        key = generate_message_key(archive_id, message_id, date, sender, subject)
        
        assert isinstance(key, str)
        assert len(key) == 16

    def test_different_archive_ids_produce_different_keys(self):
        """Test that different archive IDs produce different keys."""
        message_id = "<test@example.com>"
        
        key1 = generate_message_key("abc123def4567890", message_id)
        key2 = generate_message_key("123abc456def7890", message_id)
        
        assert key1 != key2

    def test_none_values_handled_consistently(self):
        """Test that None values are handled consistently."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        
        # Explicitly passing None should be same as not passing the parameter
        key1 = generate_message_key(archive_id, message_id)
        key2 = generate_message_key(
            archive_id, message_id, date=None, sender_email=None, subject=None
        )
        
        assert key1 == key2

    def test_empty_string_treated_as_none(self):
        """Test that empty string is treated the same as None."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        
        key_none = generate_message_key(archive_id, message_id, date=None)
        key_empty = generate_message_key(archive_id, message_id, date="")
        
        # Empty string is falsy and not included, same as None
        assert key_none == key_empty

    def test_unicode_handling(self):
        """Test that unicode characters in fields are handled correctly."""
        archive_id = "abc123def4567890"
        message_id = "<test@example.com>"
        subject = "Test Subject with émojis 🎉"
        
        key = generate_message_key(archive_id, message_id, subject=subject)
        
        assert isinstance(key, str)
        assert len(key) == 16


class TestGenerateChunkKey:
    """Test suite for generate_chunk_key function."""

    def test_basic_chunk_key_generation(self):
        """Test basic chunk key generation."""
        message_key = "a1b2c3d4e5f67890"
        chunk_index = 0
        
        key = generate_chunk_key(message_key, chunk_index)
        
        assert isinstance(key, str)
        assert len(key) == 16
        assert all(c in "0123456789abcdef" for c in key)

    def test_deterministic_chunk_generation(self):
        """Test that the same inputs always produce the same chunk key."""
        message_key = "a1b2c3d4e5f67890"
        chunk_index = 5
        
        key1 = generate_chunk_key(message_key, chunk_index)
        key2 = generate_chunk_key(message_key, chunk_index)
        
        assert key1 == key2

    def test_different_indices_produce_different_keys(self):
        """Test that different chunk indices produce different keys."""
        message_key = "a1b2c3d4e5f67890"
        
        key0 = generate_chunk_key(message_key, 0)
        key1 = generate_chunk_key(message_key, 1)
        key2 = generate_chunk_key(message_key, 2)
        
        assert key0 != key1
        assert key1 != key2
        assert key0 != key2

    def test_different_message_keys_produce_different_chunk_keys(self):
        """Test that different message keys produce different chunk keys."""
        chunk_index = 0
        
        key1 = generate_chunk_key("a1b2c3d4e5f67890", chunk_index)
        key2 = generate_chunk_key("1234567890abcdef", chunk_index)
        
        assert key1 != key2

    def test_large_chunk_index(self):
        """Test chunk key generation with large chunk index."""
        message_key = "a1b2c3d4e5f67890"
        chunk_index = 99999
        
        key = generate_chunk_key(message_key, chunk_index)
        
        assert isinstance(key, str)
        assert len(key) == 16

    def test_chunk_key_uniqueness_across_messages(self):
        """Test that chunk keys are unique across different messages."""
        msg_key1 = "a1b2c3d4e5f67890"
        msg_key2 = "1234567890abcdef"
        
        # Same chunk index for different messages should produce different keys
        chunk_keys_msg1 = [generate_chunk_key(msg_key1, i) for i in range(10)]
        chunk_keys_msg2 = [generate_chunk_key(msg_key2, i) for i in range(10)]
        
        # No overlap between the two sets
        assert set(chunk_keys_msg1).isdisjoint(set(chunk_keys_msg2))

    def test_chunk_key_uniqueness_within_message(self):
        """Test that chunk keys are unique within a single message."""
        message_key = "a1b2c3d4e5f67890"
        
        chunk_keys = [generate_chunk_key(message_key, i) for i in range(100)]
        
        # All keys should be unique
        assert len(set(chunk_keys)) == len(chunk_keys)
