# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures for chunking service tests."""

import os
import sys
from pathlib import Path

import pytest
from copilot_schema_validation import FileSchemaProvider
from copilot_storage import InMemoryDocumentStore, ValidatingDocumentStore

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def create_query_with_in_support(original_query):
    """Create a custom query function that supports MongoDB $in operator."""
    def custom_query(collection, filter_dict, limit=100):
        # Handle $in operator for _id (canonical document primary key)
        if "_id" in filter_dict and isinstance(filter_dict["_id"], dict):
            doc_ids = filter_dict["_id"].get("$in", [])
            results = []
            for doc_id in doc_ids:
                doc_results = original_query(collection, {"_id": doc_id}, limit)
                results.extend(doc_results)
            return results[:limit]
        # Handle $in operator for message_doc_id (chunk foreign key reference)
        elif "message_doc_id" in filter_dict and isinstance(filter_dict["message_doc_id"], dict):
            message_doc_ids = filter_dict["message_doc_id"].get("$in", [])
            results = []
            for message_doc_id in message_doc_ids:
                msg_results = original_query(collection, {"message_doc_id": message_doc_id}, limit)
                results.extend(msg_results)
            return results[:limit]
        else:
            return original_query(collection, filter_dict, limit)
    return custom_query


@pytest.fixture
def document_store():
    """Create in-memory document store with schema validation."""
    # Create base in-memory store
    base_store = InMemoryDocumentStore()
    base_store.connect()

    # Override query_documents to support $in operator
    base_store.query_documents = create_query_with_in_support(base_store.query_documents)

    # Wrap with validation using document schemas
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
    schema_provider = FileSchemaProvider(schema_dir=schema_dir)
    validating_store = ValidatingDocumentStore(
        store=base_store,
        schema_provider=schema_provider
    )

    return validating_store
