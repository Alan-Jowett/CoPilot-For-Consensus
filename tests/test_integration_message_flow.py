# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""End-to-end integration tests for message flow across services.

These tests demonstrate complete workflows where events flow through multiple
services, validating that:
1. Events published by one service can be consumed by another
2. All events validate against their JSON schemas
3. Message transformations preserve required data

Note: These tests use the FileSchemaProvider to validate events against
their JSON schemas, demonstrating that schema validation can be integrated
into service tests.
"""

import pytest
from typing import List, Dict, Any

from copilot_schema_validation import FileSchemaProvider, validate_json


def validate_event(event: Dict[str, Any]) -> None:
    """Validate an event against its JSON schema."""
    event_type = event.get("event_type")
    assert event_type, "Event missing event_type field"
    
    schema_provider = FileSchemaProvider()
    schema = schema_provider.get_schema(event_type)
    assert schema, f"No schema found for event type {event_type}"
    
    is_valid, errors = validate_json(event, schema, schema_provider=schema_provider)
    assert is_valid, f"Event validation failed: {'; '.join(errors)}"


class TestEventSchemaValidation:
    """Tests for validating events against JSON schemas."""
    
    def test_all_event_schemas_available(self):
        """Test that all event types have schemas available.
        
        This test ensures schema validation is working for all event types.
        """
        schema_provider = FileSchemaProvider()
        event_types = schema_provider.list_event_types()
        
        # Should have schemas for all major events
        expected_events = [
            "ArchiveIngested",
            "ArchiveIngestionFailed",
            "JSONParsed",
            "ParsingFailed",
            "ChunksPrepared",
            "ChunkingFailed",
            "EmbeddingsGenerated",
            "EmbeddingGenerationFailed",
            "SummarizationRequested",
            "SummaryComplete",
            "SummarizationFailed",
            "OrchestrationFailed",
            "ReportPublished",
            "ReportDeliveryFailed",
        ]
        
        for event_type in expected_events:
            assert event_type in event_types, f"Missing schema for {event_type}"
            
            # Verify schema can be loaded
            schema = schema_provider.get_schema(event_type)
            assert schema is not None, f"Failed to load schema for {event_type}"
    
    def test_archive_ingested_event_validation(self):
        """Test validation of a well-formed ArchiveIngested event."""
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "test-123",
            "timestamp": "2023-10-15T12:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_name": "test-source",
                "source_type": "local",
                "source_url": "/path/to/file",
                "file_path": "/path/to/file.mbox",
                "file_size_bytes": 1024,
                "file_hash_sha256": "abc123def456",
                "ingestion_started_at": "2023-10-15T12:00:00Z",
                "ingestion_completed_at": "2023-10-15T12:01:00Z",
            }
        }
        
        # Should pass validation
        validate_event(event)
    
    def test_json_parsed_event_validation(self):
        """Test validation of a well-formed JSONParsed event."""
        event = {
            "event_type": "JSONParsed",
            "event_id": "test-456",
            "timestamp": "2023-10-15T12:02:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "parsed_message_ids": ["<msg1@example.com>", "<msg2@example.com>"],
                "thread_ids": ["<thread@example.com>"],
                "message_count": 2,
                "thread_count": 1,
                "parsing_duration_seconds": 1.5,
            }
        }
        
        # Should pass validation
        validate_event(event)
    
    def test_chunks_prepared_event_validation(self):
        """Test validation of a well-formed ChunksPrepared event."""
        event = {
            "event_type": "ChunksPrepared",
            "event_id": "test-789",
            "timestamp": "2023-10-15T12:03:00Z",
            "version": "1.0",
            "data": {
                "chunk_ids": ["chunk_1", "chunk_2"],
                "message_ids": ["<msg1@example.com>"],
                "chunk_count": 2,
                "avg_chunk_size_tokens": 256,
                "chunks_ready": True,
                "chunking_strategy": "token_window",
            }
        }
        
        # Should pass validation
        validate_event(event)
    
    def test_summarization_requested_event_validation(self):
        """Test validation of a well-formed SummarizationRequested event."""
        event = {
            "event_type": "SummarizationRequested",
            "event_id": "test-abc",
            "timestamp": "2023-10-15T12:04:00Z",
            "version": "1.0",
            "data": {
                "thread_ids": ["<thread@example.com>"],
                "top_k": 10,
                "llm_backend": "ollama",
                "llm_model": "llama2",
                "context_window_tokens": 3000,
                "prompt_template": "Summarize the following discussion:",
            }
        }
        
        # Should pass validation
        validate_event(event)
    
    def test_summary_complete_event_validation(self):
        """Test validation of a well-formed SummaryComplete event."""
        event = {
            "event_type": "SummaryComplete",
            "event_id": "test-def",
            "timestamp": "2023-10-15T12:05:00Z",
            "version": "1.0",
            "data": {
                "thread_id": "<thread@example.com>",
                "summary_markdown": "# Summary\n\nThis is a test summary.",
                "citations": [
                    {
                        "message_id": "<msg1@example.com>",
                        "chunk_id": "chunk_1",
                        "offset": 0,
                    }
                ],
                "llm_backend": "ollama",
                "llm_model": "llama2",
                "tokens_prompt": 100,
                "tokens_completion": 50,
                "latency_ms": 1500,
            }
        }
        
        # Should pass validation
        validate_event(event)
    
    def test_invalid_event_missing_required_field(self):
        """Test that validation fails for events missing required fields."""
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "test-invalid",
            "timestamp": "2023-10-15T12:00:00Z",
            "version": "1.0",
            "data": {
                # Missing required fields
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
        
        # Should fail validation
        with pytest.raises(AssertionError) as exc_info:
            validate_event(event)
        
        assert "validation failed" in str(exc_info.value).lower()
    
    def test_invalid_event_wrong_type(self):
        """Test that validation fails for events with wrong field types."""
        event = {
            "event_type": "JSONParsed",
            "event_id": "test-wrong-type",
            "timestamp": "2023-10-15T12:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "parsed_message_ids": "not-an-array",  # Should be array
                "thread_ids": ["<thread@example.com>"],
                "message_count": 1,
                "thread_count": 1,
                "parsing_duration_seconds": 1.0,
            }
        }
        
        # Should fail validation
        with pytest.raises(AssertionError) as exc_info:
            validate_event(event)
        
        assert "validation failed" in str(exc_info.value).lower()


class TestMessageFlowPatterns:
    """Tests demonstrating message flow patterns without actual service instances.
    
    These tests document the expected event flows and data transformations
    without needing to instantiate actual services.
    """
    
    def test_ingestion_produces_archive_ingested(self):
        """Document that ingestion service produces ArchiveIngested events."""
        # Example event that ingestion service would publish
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "ing-001",
            "timestamp": "2023-10-15T12:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_name": "test-source",
                "source_type": "local",
                "source_url": "/path/to/source",
                "file_path": "/path/to/file.mbox",
                "file_size_bytes": 2048,
                "file_hash_sha256": "abc123",
                "ingestion_started_at": "2023-10-15T12:00:00Z",
                "ingestion_completed_at": "2023-10-15T12:00:30Z",
            }
        }
        
        validate_event(event)
        
        # Parsing service consumes this and produces JSONParsed
        # (documented in next test)
    
    def test_parsing_consumes_archive_ingested_produces_json_parsed(self):
        """Document that parsing service consumes ArchiveIngested and produces JSONParsed."""
        # Input: ArchiveIngested event
        input_event = {
            "event_type": "ArchiveIngested",
            "event_id": "ing-001",
            "timestamp": "2023-10-15T12:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "source_name": "test-source",
                "source_type": "local",
                "source_url": "/path/to/source",
                "file_path": "/path/to/file.mbox",
                "file_size_bytes": 2048,
                "file_hash_sha256": "abc123",
                "ingestion_started_at": "2023-10-15T12:00:00Z",
                "ingestion_completed_at": "2023-10-15T12:00:30Z",
            }
        }
        
        validate_event(input_event)
        
        # Output: JSONParsed event (same archive_id)
        output_event = {
            "event_type": "JSONParsed",
            "event_id": "par-001",
            "timestamp": "2023-10-15T12:01:00Z",
            "version": "1.0",
            "data": {
                "archive_id": input_event["data"]["archive_id"],  # Preserved
                "parsed_message_ids": ["<msg1@example.com>", "<msg2@example.com>"],
                "thread_ids": ["<thread@example.com>"],
                "message_count": 2,
                "thread_count": 1,
                "parsing_duration_seconds": 30.0,
            }
        }
        
        validate_event(output_event)
        
        # Verify data flow: archive_id is preserved
        assert output_event["data"]["archive_id"] == input_event["data"]["archive_id"]
    
    def test_chunking_consumes_json_parsed_produces_chunks_prepared(self):
        """Document that chunking service consumes JSONParsed and produces ChunksPrepared."""
        # Input: JSONParsed event
        input_event = {
            "event_type": "JSONParsed",
            "event_id": "par-001",
            "timestamp": "2023-10-15T12:01:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "550e8400-e29b-41d4-a716-446655440000",
                "parsed_message_ids": ["<msg1@example.com>", "<msg2@example.com>"],
                "thread_ids": ["<thread@example.com>"],
                "message_count": 2,
                "thread_count": 1,
                "parsing_duration_seconds": 30.0,
            }
        }
        
        validate_event(input_event)
        
        # Output: ChunksPrepared event
        output_event = {
            "event_type": "ChunksPrepared",
            "event_id": "chu-001",
            "timestamp": "2023-10-15T12:02:00Z",
            "version": "1.0",
            "data": {
                "chunk_ids": ["chunk_1", "chunk_2", "chunk_3"],
                "message_ids": input_event["data"]["parsed_message_ids"],  # Preserved
                "chunk_count": 3,
                "avg_chunk_size_tokens": 256,
                "chunks_ready": True,
                "chunking_strategy": "token_window",
            }
        }
        
        validate_event(output_event)
        
        # Verify data flow: message_ids are preserved
        assert output_event["data"]["message_ids"] == input_event["data"]["parsed_message_ids"]
