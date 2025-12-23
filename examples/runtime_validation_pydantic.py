# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Runtime Validation Examples with Pydantic

This module demonstrates how to use Pydantic for runtime validation
of JSON payloads, API responses, and configuration data to catch
missing fields and type errors at runtime.

Pydantic provides:
- Automatic validation of data against schemas
- Clear error messages for missing or invalid fields
- Type coercion and conversion
- IDE autocomplete and type checking support
"""

from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from enum import Enum

try:
    from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
    from pydantic import ValidationError
except ImportError:
    print("Pydantic not installed. Install with: pip install pydantic")
    raise


# Example 1: Message Event Validation
# ====================================

class EventType(str, Enum):
    """Valid event types in the system."""
    JSON_PARSED = "json_parsed"
    CHUNKS_PREPARED = "chunks_prepared"
    CHUNKS_EMBEDDED = "chunks_embedded"
    SUMMARY_READY = "summary_ready"


class MessageEvent(BaseModel):
    """
    Base model for all message bus events.

    This ensures all events have required fields and validates
    their types at runtime.
    """
    model_config = ConfigDict(
        use_enum_values=True,  # Convert enum to string
        validate_assignment=True,  # Validate on attribute assignment
    )

    event_type: EventType
    document_id: str = Field(..., min_length=1, description="Document identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ChunksPreparedEvent(MessageEvent):
    """Event emitted when chunks are prepared."""
    event_type: Literal[EventType.CHUNKS_PREPARED] = EventType.CHUNKS_PREPARED
    chunk_count: int = Field(..., gt=0, description="Number of chunks created")
    chunk_ids: List[str] = Field(..., min_length=1)

    @field_validator('chunk_ids')
    @classmethod
    def validate_chunk_ids(cls, v: List[str], info) -> List[str]:
        """Ensure chunk_ids count matches chunk_count."""
        chunk_count = info.data.get('chunk_count')
        if chunk_count is not None and len(v) != chunk_count:
            raise ValueError(
                f"chunk_ids length ({len(v)}) doesn't match chunk_count ({chunk_count})"
            )
        return v


# Example 2: API Response Validation
# ===================================

class DocumentSummary(BaseModel):
    """Model for document summary API responses."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "document_id": "msg_123",
                "thread_id": "thread_456",
                "subject": "Discussion on RFC 9999",
                "summary": "The working group discussed...",
                "consensus_level": "high",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        }
    )

    document_id: str
    thread_id: Optional[str] = None
    subject: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    consensus_level: Optional[str] = Field(None, pattern="^(high|medium|low|none)$")
    created_at: datetime
    updated_at: datetime


class PaginatedResponse(BaseModel):
    """Generic paginated response model."""
    items: List[DocumentSummary]
    total: int = Field(..., ge=0)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=100)

    @model_validator(mode='after')
    def validate_pagination(self):
        """Ensure pagination values are consistent."""
        if len(self.items) > self.page_size:
            raise ValueError(
                f"items length ({len(self.items)}) exceeds page_size ({self.page_size})"
            )
        return self


# Example 3: Configuration Validation
# ====================================

class DatabaseConfig(BaseModel):
    """MongoDB database configuration."""
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    database: str = Field(..., min_length=1)
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def connection_string(self) -> str:
        """Build MongoDB connection string."""
        if self.username and self.password:
            return f"mongodb://{self.username}:{self.password}@{self.host}:{self.port}/{self.database}"
        return f"mongodb://{self.host}:{self.port}/{self.database}"


class MessageBusConfig(BaseModel):
    """RabbitMQ message bus configuration."""
    host: str = Field(..., min_length=1)
    port: int = Field(..., ge=1, le=65535)
    queue_name: str = Field(..., min_length=1)
    prefetch_count: int = Field(default=1, ge=1)
    max_retries: int = Field(default=3, ge=0)


class ServiceConfig(BaseModel):
    """Complete service configuration model."""
    service_name: str = Field(..., min_length=1)
    database: DatabaseConfig
    message_bus: MessageBusConfig
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")

    @field_validator('service_name')
    @classmethod
    def validate_service_name(cls, v: str) -> str:
        """Ensure service name follows naming convention."""
        valid_services = [
            'ingestion', 'parsing', 'chunking', 'embedding',
            'orchestrator', 'summarization', 'reporting'
        ]
        if v not in valid_services:
            raise ValueError(
                f"service_name '{v}' not in valid services: {valid_services}"
            )
        return v


# Usage Examples
# ==============

def example_event_validation():
    """Demonstrate event validation."""
    print("\n=== Event Validation Example ===\n")

    # Valid event
    try:
        event = ChunksPreparedEvent(
            document_id="doc_123",
            chunk_count=3,
            chunk_ids=["chunk_1", "chunk_2", "chunk_3"]
        )
        print("✓ Valid event created:")
        print(f"  {event.model_dump_json(indent=2)}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")

    # Invalid event - missing required field
    print("\nAttempting to create event with missing chunk_ids...")
    try:
        invalid_event = ChunksPreparedEvent(
            document_id="doc_123",
            chunk_count=3
            # Missing chunk_ids!
        )
        print(f"✗ Should have failed but got: {invalid_event}")
    except ValidationError as e:
        print("✓ Validation correctly caught missing field:")
        print(f"  {e}")

    # Invalid event - mismatched counts
    print("\nAttempting to create event with mismatched counts...")
    try:
        invalid_event = ChunksPreparedEvent(
            document_id="doc_123",
            chunk_count=3,
            chunk_ids=["chunk_1", "chunk_2"]  # Only 2 chunks, not 3!
        )
        print(f"✗ Should have failed but got: {invalid_event}")
    except ValidationError as e:
        print("✓ Validation correctly caught count mismatch:")
        print(f"  {e}")


def example_api_response_validation():
    """Demonstrate API response validation."""
    print("\n=== API Response Validation Example ===\n")

    # Simulate API response
    api_response = {
        "items": [
            {
                "document_id": "msg_1",
                "subject": "Test Subject",
                "summary": "Test summary",
                "consensus_level": "high",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        ],
        "total": 100,
        "page": 1,
        "page_size": 10
    }

    try:
        response = PaginatedResponse(**api_response)
        print("✓ Valid API response parsed:")
        print(f"  Total: {response.total}, Page: {response.page}")
        print(f"  Items: {len(response.items)}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")

    # Invalid response - missing required field
    print("\nAttempting to parse response with missing 'subject'...")
    invalid_response = {
        "items": [
            {
                "document_id": "msg_1",
                # Missing 'subject'!
                "summary": "Test summary",
                "created_at": "2025-01-15T10:30:00Z",
                "updated_at": "2025-01-15T10:30:00Z"
            }
        ],
        "total": 1,
        "page": 1,
        "page_size": 10
    }

    try:
        response = PaginatedResponse(**invalid_response)
        print(f"✗ Should have failed but got: {response}")
    except ValidationError as e:
        print("✓ Validation correctly caught missing field:")
        print(f"  {e}")


def example_config_validation():
    """Demonstrate configuration validation."""
    print("\n=== Configuration Validation Example ===\n")

    # Valid configuration
    config_data = {
        "service_name": "chunking",
        "database": {
            "host": "localhost",
            "port": 27017,
            "database": "consensus"
        },
        "message_bus": {
            "host": "messagebus",
            "port": 5672,
            "queue_name": "chunking_queue"
        },
        "log_level": "INFO"
    }

    try:
        config = ServiceConfig(**config_data)
        print("✓ Valid configuration loaded:")
        print(f"  Service: {config.service_name}")
        print(f"  DB Connection: {config.database.connection_string}")
        print(f"  Queue: {config.message_bus.queue_name}")
    except ValidationError as e:
        print(f"✗ Validation failed: {e}")

    # Invalid configuration - wrong port
    print("\nAttempting to load config with invalid port...")
    invalid_config = {
        "service_name": "chunking",
        "database": {
            "host": "localhost",
            "port": 99999,  # Invalid port!
            "database": "consensus"
        },
        "message_bus": {
            "host": "messagebus",
            "port": 5672,
            "queue_name": "chunking_queue"
        }
    }

    try:
        config = ServiceConfig(**invalid_config)
        print(f"✗ Should have failed but got: {config}")
    except ValidationError as e:
        print("✓ Validation correctly caught invalid port:")
        print(f"  {e}")


def example_external_api_validation():
    """Demonstrate validation of external API responses."""
    print("\n=== External API Validation Example ===\n")

    # Simulating an external API response with potential issues
    external_response = {
        "document_id": "msg_123",
        "subject": "Test",
        "summary": "Summary",
        "consensus_level": "INVALID",  # Not in allowed values!
        "created_at": "2025-01-15T10:30:00Z",
        "updated_at": "2025-01-15T10:30:00Z"
    }

    try:
        summary = DocumentSummary(**external_response)
        print(f"✗ Should have failed but got: {summary}")
    except ValidationError as e:
        print("✓ Validation caught invalid consensus_level:")
        print(f"  {e}")
        print("\nThis prevents runtime errors from invalid external data!")


if __name__ == "__main__":
    """Run all validation examples."""
    print("=" * 60)
    print("Runtime Validation Examples with Pydantic")
    print("=" * 60)

    example_event_validation()
    example_api_response_validation()
    example_config_validation()
    example_external_api_validation()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("""
Pydantic provides runtime validation that:
  ✓ Catches missing required fields at runtime
  ✓ Validates field types and constraints
  ✓ Provides clear error messages
  ✓ Enables static type checking with mypy/pyright
  ✓ Auto-generates JSON schemas for documentation
  ✓ Integrates seamlessly with FastAPI

Use Pydantic models for:
  • Message bus event payloads
  • API request/response bodies
  • Configuration files
  • External API responses
  • Database document schemas
    """)
