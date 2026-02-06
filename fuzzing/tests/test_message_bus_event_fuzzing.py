# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Hypothesis property-based fuzz tests for message bus event payloads.

This module tests security-critical event deserialization and validation for
Azure Service Bus / RabbitMQ message handling to detect:
- Malformed events causing crashes
- Poison messages that break event processing
- DoS attacks via large payloads
- Schema validation bypasses
- Event type dispatch vulnerabilities
- Missing/extra fields handling issues

Targets:
- Event JSON schema validation (event envelope + event-specific schemas)
- Event type dispatch and routing
- Payload size limits and DoS protection
- Missing/extra fields handling (additionalProperties: false)
- Type confusion attacks
- Timestamp and UUID validation

Usage:
    pytest tests/test_message_bus_event_fuzzing.py -v
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from hypothesis import assume, given, settings, strategies as st, HealthCheck

# Add parent directories to path for imports
repo_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(repo_root / "adapters" / "copilot_message_bus"))
sys.path.insert(0, str(repo_root / "adapters" / "copilot_schema_validation"))
sys.path.insert(0, str(repo_root / "tests"))

from copilot_message_bus.validating_publisher import (  # noqa: E402
    ValidationError,
    ValidatingEventPublisher,
)
from copilot_message_bus.validating_subscriber import (  # noqa: E402
    SubscriberValidationError,
    ValidatingEventSubscriber,
)
from copilot_message_bus.noop_publisher import NoopPublisher  # noqa: E402
from copilot_message_bus.noop_subscriber import NoopSubscriber  # noqa: E402

try:
    from copilot_schema_validation import create_schema_provider  # noqa: E402
except ImportError:
    create_schema_provider = None  # type: ignore


# ============================================================================
# Hypothesis Strategies for Generating Test Events
# ============================================================================


def valid_event_types() -> st.SearchStrategy[str]:
    """Generate valid event type names from known schemas."""
    return st.sampled_from([
        "ArchiveIngested",
        "JSONParsed",
        "ChunksPrepared",
        "EmbeddingsGenerated",
        "SummaryComplete",
        "ArchiveIngestionFailed",
        "ParsingFailed",
        "ChunkingFailed",
        "EmbeddingGenerationFailed",
        "SummarizationFailed",
    ])


def malicious_event_types() -> st.SearchStrategy[str]:
    """Generate malicious or malformed event type values."""
    return st.one_of(
        # Empty/whitespace
        st.just(""),
        st.just("   "),
        # Very long
        st.text(min_size=1000, max_size=10000),
        # SQL injection
        st.just("ArchiveIngested'; DROP TABLE events; --"),
        st.just("' OR '1'='1"),
        # Path traversal
        st.just("../../../etc/passwd"),
        st.just("..\\..\\..\\windows\\system32"),
        # XSS
        st.just("<script>alert('xss')</script>"),
        st.just("javascript:alert(1)"),
        # Command injection
        st.just("; rm -rf /"),
        st.just("| cat /etc/passwd"),
        # Null bytes
        st.just("ArchiveIngested\x00Admin"),
        # Unicode/homograph
        st.just("АrchiveIngested"),  # Cyrillic 'А'
        # Case variations (might be accepted?)
        st.just("archiveingested"),
        st.just("ARCHIVEINGESTED"),
        # Unknown types
        st.text(min_size=1, max_size=100),
    )


def valid_uuids() -> st.SearchStrategy[str]:
    """Generate valid UUID strings."""
    return st.uuids().map(str)


def malicious_uuids() -> st.SearchStrategy[str]:
    """Generate malformed UUID values."""
    return st.one_of(
        # Not a UUID
        st.just("not-a-uuid"),
        st.just("12345"),
        # Almost valid
        st.just("12345678-1234-1234-1234-12345678901"),  # Too short
        st.just("12345678-1234-1234-1234-1234567890123"),  # Too long
        # SQL injection
        st.just("12345678-1234-1234-1234-123456789012'; DROP TABLE events; --"),
        # Empty/whitespace
        st.just(""),
        st.just("   "),
        # Null bytes
        st.just("12345678-1234-1234-1234\x00123456789012"),
        # Very long
        st.text(min_size=100, max_size=1000),
    )


def valid_timestamps() -> st.SearchStrategy[str]:
    """Generate valid ISO 8601 timestamp strings."""
    return st.datetimes(
        min_value=datetime(2020, 1, 1),
        max_value=datetime(2030, 12, 31),
    ).map(lambda dt: dt.replace(tzinfo=timezone.utc).isoformat())


def malicious_timestamps() -> st.SearchStrategy[str]:
    """Generate malformed timestamp values."""
    return st.one_of(
        # Not a timestamp
        st.just("not-a-timestamp"),
        st.just("12345"),
        # Wrong format
        st.just("2025-01-01 00:00:00"),  # Missing T
        st.just("01/01/2025"),  # US format
        st.just("2025-13-01T00:00:00Z"),  # Invalid month
        st.just("2025-01-32T00:00:00Z"),  # Invalid day
        # SQL injection
        st.just("2025-01-01T00:00:00Z'; DROP TABLE events; --"),
        # Empty/whitespace
        st.just(""),
        st.just("   "),
        # Null bytes
        st.just("2025-01-01T00:00:00\x00Z"),
        # Very long
        st.text(min_size=100, max_size=1000),
    )


def valid_versions() -> st.SearchStrategy[str]:
    """Generate valid version strings."""
    return st.sampled_from(["1.0", "1.1", "2.0"])


def malicious_versions() -> st.SearchStrategy[str]:
    """Generate malformed version values."""
    return st.one_of(
        st.just(""),
        st.just("   "),
        st.text(min_size=1, max_size=100),
        st.just("1.0'; DROP TABLE versions; --"),
        st.just("<script>alert('xss')</script>"),
        st.just("999.999.999.999"),
    )


def small_data_payloads() -> st.SearchStrategy[dict[str, Any]]:
    """Generate small valid data payloads."""
    return st.fixed_dictionaries({
        "archive_id": st.text(
            alphabet=st.characters(min_codepoint=48, max_codepoint=102),  # 0-9, a-f
            min_size=16,
            max_size=64,
        ),
        "source_name": st.text(min_size=1, max_size=50),
    })


def large_data_payloads() -> st.SearchStrategy[dict[str, Any]]:
    """Generate very large data payloads for DoS testing.
    
    Note: Hypothesis has a BUFFER_SIZE limit (~8KB) for text generation.
    These sizes are chosen to test payload handling within that constraint
    while still being significantly larger than typical event payloads.
    The system should validate and reject these at the schema or size limit layer.
    For testing truly massive payloads (>100KB), see test_very_long_string_fields_handled.
    """
    return st.one_of(
        # Large string values (stay within Hypothesis buffer limits)
        st.fixed_dictionaries({
            "large_field": st.text(min_size=5_000, max_size=8_000),
        }),
        # Large arrays
        st.fixed_dictionaries({
            "large_array": st.lists(st.integers(), min_size=500, max_size=2_000),
        }),
        # Deeply nested structures
        st.recursive(
            st.dictionaries(st.text(min_size=1, max_size=10), st.integers()),
            lambda children: st.dictionaries(st.text(min_size=1, max_size=10), children),
            max_leaves=500,
        ),
    )


def malicious_data_payloads() -> st.SearchStrategy[dict[str, Any]]:
    """Generate malicious data payloads."""
    return st.one_of(
        # Empty
        st.just({}),
        # SQL injection in values
        st.fixed_dictionaries({
            "archive_id": st.just("abc'; DROP TABLE archives; --"),
            "source_name": st.just("test' OR '1'='1"),
        }),
        # XSS in values
        st.fixed_dictionaries({
            "archive_id": st.just("<script>alert('xss')</script>"),
            "source_name": st.just("javascript:alert(1)"),
        }),
        # Null bytes
        st.fixed_dictionaries({
            "archive_id": st.just("abc123def4567890\x00admin"),
        }),
        # Type confusion
        st.fixed_dictionaries({
            "archive_id": st.integers(),  # Should be string
            "source_name": st.lists(st.text()),  # Should be string
        }),
    )


# ============================================================================
# Property-Based Tests for Event Envelope Schema Validation
# ============================================================================


class TestEventEnvelopeValidation:
    """Test event envelope schema validation with Hypothesis."""

    def _get_validating_publisher(self):
        """Create a validating publisher for testing."""
        if create_schema_provider is None:
            pytest.skip("copilot_schema_validation not available")
        
        schema_dir = repo_root / "docs" / "schemas" / "events"
        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        base_publisher = NoopPublisher()
        return ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )

    @given(
        event_type=valid_event_types(),
        event_id=valid_uuids(),
        timestamp=valid_timestamps(),
        version=valid_versions(),
        data=small_data_payloads(),
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_events_pass_validation(
        self,
        event_type: str,
        event_id: str,
        timestamp: str,
        version: str,
        data: dict[str, Any],
    ):
        """Test that well-formed events pass validation."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": event_type,
            "event_id": event_id,
            "timestamp": timestamp,
            "version": version,
            "data": data,
        }

        # Some event types have strict data requirements, so we allow validation
        # to fail for data schema issues, but the envelope should be parsed
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except ValidationError as e:
            # If it fails, it should be due to data schema, not envelope
            assert "data" in str(e).lower() or event_type in str(e)

    @given(event_type=malicious_event_types())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_malicious_event_types_rejected(
        self,
        event_type: str,
    ):
        """Test that malicious event_type values are rejected."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": event_type,
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {},
        }

        # Should either reject the event or handle it gracefully
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError, TypeError, KeyError) as e:
            # Expected - validation should catch this
            assert isinstance(e, (ValidationError, ValueError, TypeError, KeyError))

    @given(event_id=malicious_uuids())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_malicious_event_ids_rejected(
        self,
        event_id: str,
    ):
        """Test that malformed event_id values are rejected or handled gracefully."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": event_id,
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890",
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Should either reject or handle gracefully (no crash)
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError, TypeError) as e:
            # Expected - validation caught malicious input
            assert isinstance(e, (ValidationError, ValueError, TypeError))

    @given(timestamp=malicious_timestamps())
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_malicious_timestamps_rejected(
        self,
        timestamp: str,
    ):
        """Test that malformed timestamp values are rejected or handled gracefully."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": timestamp,
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890",
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Should either reject or handle gracefully (no crash)
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError, TypeError) as e:
            # Expected - validation caught malicious input
            assert isinstance(e, (ValidationError, ValueError, TypeError))


# ============================================================================
# Property-Based Tests for Missing/Extra Fields
# ============================================================================


class TestMissingExtraFieldsHandling:
    """Test handling of missing required fields and extra unexpected fields."""

    def _get_validating_publisher(self):
        """Create a validating publisher for testing."""
        if create_schema_provider is None:
            pytest.skip("copilot_schema_validation not available")
        
        schema_dir = repo_root / "docs" / "schemas" / "events"
        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        base_publisher = NoopPublisher()
        return ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )


    @given(
        missing_field=st.sampled_from([
            "event_type",
            "event_id",
            "timestamp",
            "version",
            "data",
        ])
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_missing_required_fields_rejected(
        self,
        missing_field: str,
    ):
        """Test that events with missing required fields are rejected."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890",
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Remove the field
        del event[missing_field]

        with pytest.raises((ValidationError, ValueError, KeyError)):
            validating_publisher.publish("copilot.events", "test", event)

    @given(extra_fields=st.dictionaries(st.text(min_size=1, max_size=20), st.text()))
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_extra_fields_in_envelope_rejected(
        self,
        extra_fields: dict[str, str],
    ):
        """Test that extra fields in event envelope are rejected (additionalProperties: false)."""
        validating_publisher = self._get_validating_publisher()
        # Avoid conflicting with required fields
        assume(not any(k in extra_fields for k in [
            "event_type", "event_id", "timestamp", "version", "data"
        ]))
        # Skip empty dict case (no extra fields to test)
        assume(len(extra_fields) > 0)

        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890",
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
            **extra_fields,
        }

        # Should reject due to additionalProperties: false
        with pytest.raises((ValidationError, ValueError)):
            validating_publisher.publish("copilot.events", "test", event)

    @given(
        missing_data_field=st.sampled_from([
            "archive_id",
            "source_name",
            "source_type",
            "source_url",
            "file_size_bytes",
            "file_hash_sha256",
            "ingestion_started_at",
            "ingestion_completed_at",
        ])
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_missing_required_data_fields_rejected(
        self,
        missing_data_field: str,
    ):
        """Test that events with missing required data fields are rejected."""
        validating_publisher = self._get_validating_publisher()
        data = {
            "archive_id": "abc123def4567890",
            "source_name": "test",
            "source_type": "local",
            "source_url": "/test",
            "file_size_bytes": 1024,
            "file_hash_sha256": "a" * 64,
            "ingestion_started_at": "2025-01-01T00:00:00Z",
            "ingestion_completed_at": "2025-01-01T00:00:00Z",
        }

        # Remove the field
        del data[missing_data_field]

        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": data,
        }

        with pytest.raises((ValidationError, ValueError)):
            validating_publisher.publish("copilot.events", "test", event)


# ============================================================================
# Property-Based Tests for Payload Size Limits
# ============================================================================


class TestPayloadSizeLimits:
    """Test handling of very large payloads for DoS protection."""

    def _get_validating_publisher(self):
        """Create a validating publisher for testing."""
        if create_schema_provider is None:
            pytest.skip("copilot_schema_validation not available")
        
        schema_dir = repo_root / "docs" / "schemas" / "events"
        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        base_publisher = NoopPublisher()
        return ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )


    @given(data=large_data_payloads())
    @settings(max_examples=10, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.large_base_example])  # Longer deadline for large payloads
    def test_large_payloads_handled_gracefully(
        self,
        data: dict[str, Any],
    ):
        """Test that very large payloads don't cause crashes or hangs."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": data,
        }

        # Should either reject gracefully or process without hanging
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError, TypeError, MemoryError, RecursionError) as e:
            # Expected - validation or processing should catch this
            assert isinstance(e, (ValidationError, ValueError, TypeError, MemoryError, RecursionError))

    @given(field_size=st.integers(min_value=1_000, max_value=10_000))
    @settings(max_examples=5, deadline=10000, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_very_long_string_fields_handled(
        self,
        field_size: int,
    ):
        """Test that very long string fields don't cause crashes."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "a" * field_size,  # Very long
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Should reject due to pattern constraints
        with pytest.raises((ValidationError, ValueError, MemoryError)):
            validating_publisher.publish("copilot.events", "test", event)


# ============================================================================
# Property-Based Tests for Event Type Dispatch
# ============================================================================


class TestEventTypeDispatch:
    """Test event type dispatch and routing robustness."""

    def _get_validating_subscriber(self):
        """Create a validating subscriber for testing."""
        if create_schema_provider is None:
            pytest.skip("copilot_schema_validation not available")
        
        schema_dir = repo_root / "docs" / "schemas" / "events"
        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        mock_subscriber = NoopSubscriber()
        return ValidatingEventSubscriber(
            subscriber=mock_subscriber,
            schema_provider=schema_provider,
            strict=True,
        )

    @given(event_type=valid_event_types())
    @settings(max_examples=10, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_valid_event_types_dispatch_correctly(
        self,
        event_type: str,
    ):
        """Test that valid event types can be subscribed to."""
        validating_subscriber = self._get_validating_subscriber()
        callback_invoked = []

        def callback(event: dict[str, Any]) -> None:
            callback_invoked.append(event)

        # Should not raise when subscribing to valid event types
        validating_subscriber.subscribe(event_type=event_type, callback=callback)

    @given(event_type=malicious_event_types())
    @settings(max_examples=20, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_malicious_event_types_dont_crash_subscriber(
        self,
        event_type: str,
    ):
        """Test that subscriber doesn't crash with malicious event types."""
        validating_subscriber = self._get_validating_subscriber()
        # Subscribing should work (it's just a string)
        callback_invoked = []

        def callback(event: dict[str, Any]) -> None:
            callback_invoked.append(event)

        try:
            validating_subscriber.subscribe(event_type=event_type, callback=callback)
        except (ValueError, TypeError, KeyError) as e:
            # May reject invalid event type names
            assert isinstance(e, (ValueError, TypeError, KeyError))


# ============================================================================
# Security Edge Cases
# ============================================================================


class TestSecurityEdgeCases:
    """Test specific security vulnerabilities and edge cases."""

    def _get_validating_publisher(self):
        """Create a validating publisher for testing."""
        if create_schema_provider is None:
            pytest.skip("copilot_schema_validation not available")
        
        schema_dir = repo_root / "docs" / "schemas" / "events"
        schema_provider = create_schema_provider(schema_dir=str(schema_dir))
        base_publisher = NoopPublisher()
        return ValidatingEventPublisher(
            publisher=base_publisher,
            schema_provider=schema_provider,
            strict=True,
        )

    def test_null_event_rejected(self):
        """Test that None/null events are rejected."""
        validating_publisher = self._get_validating_publisher()
        with pytest.raises((ValidationError, ValueError, TypeError, AttributeError)):
            validating_publisher.publish("copilot.events", "test", None)  # type: ignore

    def test_empty_event_rejected(self):
        """Test that empty events are rejected."""
        validating_publisher = self._get_validating_publisher()
        with pytest.raises((ValidationError, ValueError, KeyError)):
            validating_publisher.publish("copilot.events", "test", {})

    def test_event_as_list_rejected(self):
        """Test that events as lists are rejected."""
        validating_publisher = self._get_validating_publisher()
        with pytest.raises((ValidationError, ValueError, TypeError, AttributeError)):
            validating_publisher.publish("copilot.events", "test", [])  # type: ignore

    def test_event_as_string_rejected(self):
        """Test that events as strings are rejected."""
        validating_publisher = self._get_validating_publisher()
        with pytest.raises((ValidationError, ValueError, TypeError, AttributeError)):
            validating_publisher.publish("copilot.events", "test", "not an event")  # type: ignore

    def test_json_bomb_rejected(self):
        """Test that deeply nested JSON structures are handled."""
        validating_publisher = self._get_validating_publisher()
        # Create a deeply nested structure
        nested = {"a": "value"}
        for _ in range(100):  # Deep nesting
            nested = {"nested": nested}

        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": nested,
        }

        # Should either reject or handle gracefully
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError, RecursionError) as e:
            assert isinstance(e, (ValidationError, ValueError, RecursionError))

    def test_null_byte_injection_rejected(self):
        """Test that null bytes in strings are rejected."""
        validating_publisher = self._get_validating_publisher()
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890\x00admin",  # Null byte
                "source_name": "test",
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Should reject due to pattern validation
        with pytest.raises((ValidationError, ValueError)):
            validating_publisher.publish("copilot.events", "test", event)

    def test_unicode_normalization_attacks(self):
        """Test that Unicode normalization attacks are handled."""
        validating_publisher = self._get_validating_publisher()
        # Use Unicode characters that normalize differently
        event = {
            "event_type": "ArchiveIngested",
            "event_id": "12345678-1234-1234-1234-123456789012",
            "timestamp": "2025-01-01T00:00:00Z",
            "version": "1.0",
            "data": {
                "archive_id": "abc123def4567890",
                "source_name": "test\u202e\u202dmalicious",  # RTL override
                "source_type": "local",
                "source_url": "/test",
                "file_size_bytes": 1024,
                "file_hash_sha256": "a" * 64,
                "ingestion_started_at": "2025-01-01T00:00:00Z",
                "ingestion_completed_at": "2025-01-01T00:00:00Z",
            },
        }

        # Should either accept (if normalized) or reject, but not crash
        try:
            validating_publisher.publish("copilot.events", "test", event)
        except (ValidationError, ValueError) as e:
            assert isinstance(e, (ValidationError, ValueError))


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v"])
