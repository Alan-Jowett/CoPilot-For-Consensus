# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Regression tests for document schema validation.

These tests ensure that schemas properly handle:
- Null/empty values for optional fields
- Duplicate references in arrays
- Additional properties in documents
"""

import pytest
from copilot_schema_validation import FileSchemaProvider, validate_json
from pathlib import Path


class TestMessageSchemaRegression:
    """Regression tests for messages schema."""

    @pytest.fixture
    def schema_provider(self):
        """Get schema provider for document schemas."""
        schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
        return FileSchemaProvider(schema_dir=schema_dir)

    @pytest.fixture
    def messages_schema(self, schema_provider):
        """Get messages schema."""
        return schema_provider.get_schema("messages")

    def test_message_with_null_date(self, messages_schema, schema_provider):
        """Test that a message with null date is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "date": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_null_subject(self, messages_schema, schema_provider):
        """Test that a message with null subject is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_null_from(self, messages_schema, schema_provider):
        """Test that a message with null from field is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "from": None,
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_duplicate_references(self, messages_schema, schema_provider):
        """Test that a message with duplicate references is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "references": ["ref-1", "ref-2", "ref-1"],  # Duplicate ref-1
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_without_date_field(self, messages_schema, schema_provider):
        """Test that a message without date field is valid (date not required)."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_valid_non_empty_subject(self, messages_schema, schema_provider):
        """Test that a message with valid non-empty subject is valid."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": "Valid Subject",
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_message_with_empty_subject_should_fail(self, messages_schema, schema_provider):
        """Test that a message with empty string subject is invalid (minLength=1)."""
        message = {
            "message_id": "msg-123",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "thread_id": "thread-1",
            "subject": "",  # Empty string should fail minLength validation
            "body_normalized": "Test message body",
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(message, messages_schema, schema_provider=schema_provider)
        assert not is_valid, "Empty subject should fail validation"


class TestThreadSchemaRegression:
    """Regression tests for threads schema."""

    @pytest.fixture
    def schema_provider_threads(self):
        """Get schema provider for document schemas."""
        schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
        return FileSchemaProvider(schema_dir=schema_dir)

    @pytest.fixture
    def threads_schema(self, schema_provider_threads):
        """Get threads schema."""
        return schema_provider_threads.get_schema("threads")

    def test_thread_with_null_first_message_date(self, threads_schema, schema_provider_threads):
        """Test that a thread with null first_message_date is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "first_message_date": None,
            "last_message_date": "2025-01-02T00:00:00Z",
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=schema_provider_threads)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_last_message_date(self, threads_schema, schema_provider_threads):
        """Test that a thread with null last_message_date is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "first_message_date": "2025-01-01T00:00:00Z",
            "last_message_date": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=schema_provider_threads)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_consensus_type(self, threads_schema, schema_provider_threads):
        """Test that a thread with null consensus_type is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "consensus_type": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=schema_provider_threads)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_with_null_summary_id(self, threads_schema, schema_provider_threads):
        """Test that a thread with null summary_id is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "summary_id": None,
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=schema_provider_threads)
        assert is_valid, f"Validation failed with errors: {errors}"

    def test_thread_without_optional_date_fields(self, threads_schema, schema_provider_threads):
        """Test that a thread without first/last_message_date fields is valid."""
        thread = {
            "thread_id": "thread-1",
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "has_consensus": False,
            "created_at": "2025-01-01T00:00:00Z"
        }
        
        is_valid, errors = validate_json(thread, threads_schema, schema_provider=schema_provider_threads)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestArchiveSchemaRegression:
    """Regression tests for archives schema."""

    @pytest.fixture
    def schema_provider_archives(self):
        """Get schema provider for document schemas."""
        schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
        return FileSchemaProvider(schema_dir=schema_dir)

    @pytest.fixture
    def archives_schema(self, schema_provider_archives):
        """Get archives schema."""
        return schema_provider_archives.get_schema("archives")

    def test_archive_with_additional_properties(self, archives_schema, schema_provider_archives):
        """Test that an archive with additional properties is valid."""
        archive = {
            "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            "source": "test-source",
            "ingestion_date": "2025-01-01T00:00:00Z",
            "status": "processed",
            "custom_field": "custom_value"  # Additional property
        }
        
        is_valid, errors = validate_json(archive, archives_schema, schema_provider=schema_provider_archives)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestChunkSchemaRegression:
    """Regression tests for chunks schema."""

    @pytest.fixture
    def schema_provider_chunks(self):
        """Get schema provider for document schemas."""
        schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
        return FileSchemaProvider(schema_dir=schema_dir)

    @pytest.fixture
    def chunks_schema(self, schema_provider_chunks):
        """Get chunks schema."""
        return schema_provider_chunks.get_schema("chunks")

    def test_chunk_with_additional_properties(self, chunks_schema, schema_provider_chunks):
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
        
        is_valid, errors = validate_json(chunk, chunks_schema, schema_provider=schema_provider_chunks)
        assert is_valid, f"Validation failed with errors: {errors}"


class TestSummarySchemaRegression:
    """Regression tests for summaries schema."""

    @pytest.fixture
    def schema_provider_summaries(self):
        """Get schema provider for document schemas."""
        schema_dir = Path(__file__).parent.parent.parent.parent / "documents" / "schemas" / "documents"
        return FileSchemaProvider(schema_dir=schema_dir)

    @pytest.fixture
    def summaries_schema(self, schema_provider_summaries):
        """Get summaries schema."""
        return schema_provider_summaries.get_schema("summaries")

    def test_summary_with_additional_properties(self, summaries_schema, schema_provider_summaries):
        """Test that a summary with additional properties is valid."""
        summary = {
            "summary_id": "550e8400-e29b-41d4-a716-446655440000",
            "summary_type": "thread",
            "generated_at": "2025-01-01T00:00:00Z",
            "content_markdown": "# Test Summary\n\nThis is a test.",
            "custom_field": "custom_value"  # Additional property
        }
        
        is_valid, errors = validate_json(summary, summaries_schema, schema_provider=schema_provider_summaries)
        assert is_valid, f"Validation failed with errors: {errors}"
