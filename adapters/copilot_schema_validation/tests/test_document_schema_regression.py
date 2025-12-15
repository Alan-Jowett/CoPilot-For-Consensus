# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Regression tests for document schema validation.

These tests ensure that schemas properly handle:
- Null/empty values for optional fields
- Duplicate references in arrays
- Additional properties in documents
"""

import pytest
from copilot_schema_validation import validate_json


class TestMessageSchemaRegression:
    """Regression tests for messages schema."""

    @pytest.fixture
    def messages_schema(self, document_schema_provider):
        """Get messages schema."""
        return document_schema_provider.get_schema("messages")

    def test_message_with_null_date(self, messages_schema, document_schema_provider):
        """Test that a message with null date is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "date": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_null_subject(self, messages_schema, document_schema_provider):
        """Test that a message with null subject is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_null_from(self, messages_schema, document_schema_provider):
        """Test that a message with null from field is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "from": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_duplicate_references(self, messages_schema, document_schema_provider):
        """Test that a message with duplicate references is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "references": ["ref-1", "ref-2", "ref-1"],  # Duplicate ref-1
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_without_date_field(self, messages_schema, document_schema_provider):
        """Test that a message without date field is valid (date not required)."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_valid_non_empty_subject(self, messages_schema, document_schema_provider):
        """Test that a message with valid non-empty subject is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": "Valid Subject",
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_empty_subject_is_valid(self, messages_schema, document_schema_provider):
        """Test that a message with empty string subject remains valid (subject optional)."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": "",  # Empty string is allowed
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_empty_from_name_is_valid(self, messages_schema, document_schema_provider):
        """Test that a message allowing empty from.name remains valid (no minLength constraint)."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "from": {
                "name": "",  # Empty string now allowed
                "email": "sender@example.com"
            },
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }

        is_valid, errors = validate_json(message, messages_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestThreadSchemaRegression:
    """Regression tests for threads schema."""

    @pytest.fixture
    def threads_schema(self, document_schema_provider):
        """Get threads schema."""
        return document_schema_provider.get_schema("threads")

    def test_thread_with_null_first_message_date(self, threads_schema, document_schema_provider):
        """Test that a thread with null first_message_date is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "first_message_date": None,
            "last_message_date": "2025-01-02T00:00:00Z",
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_last_message_date(self, threads_schema, document_schema_provider):
        """Test that a thread with null last_message_date is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "first_message_date": "2025-01-01T00:00:00Z",
            "last_message_date": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_consensus_type(self, threads_schema, document_schema_provider):
        """Test that a thread with null consensus_type is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "consensus_type": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_summary_id(self, threads_schema, document_schema_provider):
        """Test that a thread with null summary_id is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "summary_id": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_without_optional_date_fields(self, threads_schema, document_schema_provider):
        """Test that a thread without first/last_message_date fields is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestArchiveSchemaRegression:
    """Regression tests for archives schema."""

    @pytest.fixture
    def archives_schema(self, document_schema_provider):
        """Get archives schema."""
        return document_schema_provider.get_schema("archives")

    def test_archive_with_additional_properties(self, archives_schema, document_schema_provider):
        """Test that an archive with additional properties is valid."""
        archive = {
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "source": "test-source",
            "ingestion_date": "2025-01-01T00:00:00Z",
            "status": "processed",
            "custom_field": "custom_value"  # Additional property
        }
        
        is_valid, errors = validate_json(archive, archives_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestChunkSchemaRegression:
    """Regression tests for chunks schema."""

    @pytest.fixture
    def chunks_schema(self, document_schema_provider):
        """Get chunks schema."""
        return document_schema_provider.get_schema("chunks")

    def test_chunk_with_additional_properties(self, chunks_schema, document_schema_provider):
        """Test that a chunk with additional properties is valid."""
        chunk = {
            "chunk_id": "550e8400-e29b-41d4-a716-446655440000",
            "message_id": "msg-123",
            "thread_id": "thread-1",
            "chunk_index": 0,
            "text": "Test chunk text",
            "created_at": "2025-01-01T00:00:00Z",
            "embedding_generated": False,
            "custom_field": "custom_value"  # Additional property
        }
        
        is_valid, errors = validate_json(chunk, chunks_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestSummarySchemaRegression:
    """Regression tests for summaries schema."""

    @pytest.fixture
    def summaries_schema(self, document_schema_provider):
        """Get summaries schema."""
        return document_schema_provider.get_schema("summaries")

    def test_summary_with_additional_properties(self, summaries_schema, document_schema_provider):
        """Test that a summary with additional properties is valid."""
        summary = {
            "summary_id": "550e8400-e29b-41d4-a716-446655440000",
            "summary_type": "thread",
            "generated_at": "2025-01-01T00:00:00Z",
            "content_markdown": "# Test Summary\n\nThis is a test.",
            "custom_field": "custom_value"  # Additional property
        }
        
        is_valid, errors = validate_json(summary, summaries_schema, schema_provider=document_schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"
