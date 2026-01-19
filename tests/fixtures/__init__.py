# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Shared test fixtures for schema-compliant test data generation.

This module exports all fixture helpers for creating schema-compliant
documents and events for testing.

Usage:
    from tests.fixtures import create_valid_message, create_valid_chunk

    message = create_valid_message(subject="Test")
    chunk = create_valid_chunk(text="Test chunk")
"""

from .document_fixtures import (  # noqa: F401
    create_valid_archive,
    create_valid_chunk,
    create_valid_message,
    create_valid_thread,
    generate_doc_id,
)
from .event_fixtures import (  # noqa: F401
    create_archive_ingested_event,
    create_chunks_prepared_event,
    create_embeddings_generated_event,
    create_failure_event,
    create_json_parsed_event,
    create_summary_complete_event,
    create_valid_event,
)

__all__ = [
    # Document fixtures
    "generate_doc_id",
    "create_valid_message",
    "create_valid_chunk",
    "create_valid_thread",
    "create_valid_archive",
    # Event fixtures
    "create_valid_event",
    "create_archive_ingested_event",
    "create_json_parsed_event",
    "create_chunks_prepared_event",
    "create_embeddings_generated_event",
    "create_summary_complete_event",
    "create_failure_event",
]
