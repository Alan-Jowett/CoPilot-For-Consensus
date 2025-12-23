# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for UUID conversion and original ID preservation in Qdrant."""

import uuid
from unittest.mock import Mock, patch

from copilot_vectorstore.qdrant_store import QdrantVectorStore, _string_to_uuid


def test_string_to_uuid_deterministic():
    """UUID generation should be deterministic for same input."""
    id1 = "chunk-abc123"
    uuid1 = _string_to_uuid(id1)
    uuid2 = _string_to_uuid(id1)
    assert uuid1 == uuid2


def test_string_to_uuid_unique_for_different_inputs():
    """Different string IDs should produce different UUIDs."""
    uuid1 = _string_to_uuid("chunk-1")
    uuid2 = _string_to_uuid("chunk-2")
    uuid3 = _string_to_uuid("chunk-10")
    # Verify all three UUIDs are unique
    assert uuid1 != uuid2
    assert uuid2 != uuid3
    assert uuid1 != uuid3


def test_string_to_uuid_format():
    """UUID should be valid UUID5 format."""
    result = _string_to_uuid("test-id")
    # Should parse as valid UUID
    uuid_obj = uuid.UUID(result)
    # Should be UUID version 5
    assert uuid_obj.version == 5


@patch('qdrant_client.QdrantClient')
def test_add_embedding_stores_original_id_in_payload(mock_client_class):
    """Original ID should be preserved in _original_id payload field."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_collections.return_value = Mock(collections=[])
    mock_client.retrieve.return_value = []

    store = QdrantVectorStore(vector_size=3)
    original_id = "chunk-sha256-abc123"
    store.add_embedding(original_id, [1.0, 0.0, 0.0], {"text": "test"})

    # Extract the point passed to upsert
    call_args = mock_client.upsert.call_args
    point = call_args[1]['points'][0]

    # Verify UUID was used for point ID
    assert point.id != original_id
    # Verify original ID is in payload
    assert point.payload["_original_id"] == original_id
    # Verify other metadata preserved
    assert point.payload["text"] == "test"


@patch('qdrant_client.QdrantClient')
def test_add_embeddings_batch_uses_uuids_for_upsert(mock_client_class):
    """Batch add should use UUID IDs when upserting points."""
    mock_client = Mock()
    mock_client_class.return_value = mock_client
    mock_client.get_collections.return_value = Mock(collections=[])

    store = QdrantVectorStore(vector_size=3)
    original_ids = ["chunk-1", "chunk-2"]
    store.add_embeddings(
        ids=original_ids,
        vectors=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        metadatas=[{"x": 1}, {"x": 2}]
    )

    # Verify upsert was called with UUID point IDs and original IDs in payload
    upsert_call = mock_client.upsert.call_args
    points = upsert_call[1]['points']

    # Should have 2 points
    assert len(points) == 2

    # Each point should have UUID as ID and original ID in payload
    for i, point in enumerate(points):
        # UUID should differ from original ID
        assert point.id != original_ids[i]
        # Should be valid UUID format
        uuid.UUID(point.id)  # Raises if invalid
        # Original ID should be in payload
        assert point.payload["_original_id"] == original_ids[i]
