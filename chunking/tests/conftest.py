# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Pytest configuration and fixtures for chunking service tests."""

import os
import sys
from pathlib import Path

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_Inmemory,
)
from copilot_schema_validation import create_schema_provider
from copilot_storage import create_document_store

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Add repo root to path for test fixtures
_repo_root = Path(__file__).parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


@pytest.fixture(scope="session", autouse=True)
def set_test_environment():
    """Set required environment variables for all chunking tests."""
    os.environ["SERVICE_VERSION"] = "0.1.0"

    # Set discriminant types for adapters (use noop/inmemory for tests)
    os.environ["CHUNKER_TYPE"] = "token_window"
    os.environ["DOCUMENT_STORE_TYPE"] = "inmemory"
    os.environ["MESSAGE_BUS_TYPE"] = "noop"
    os.environ["METRICS_TYPE"] = "noop"
    os.environ["SECRET_PROVIDER_TYPE"] = "local"

    yield

    # Clean up environment variables
    os.environ.pop("SERVICE_VERSION", None)
    os.environ.pop("CHUNKER_TYPE", None)
    os.environ.pop("DOCUMENT_STORE_TYPE", None)
    os.environ.pop("MESSAGE_BUS_TYPE", None)
    os.environ.pop("METRICS_TYPE", None)
    os.environ.pop("SECRET_PROVIDER_TYPE", None)


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
    # Create in-memory store via factory (already wrapped with validation)
    schema_dir = Path(__file__).parent.parent.parent / "docs" / "schemas" / "documents"
    schema_provider = create_schema_provider(schema_dir=schema_dir, schema_type="documents")

    document_store = create_document_store(
        AdapterConfig_DocumentStore(
            doc_store_type="inmemory",
            driver=DriverConfig_DocumentStore_Inmemory(),
        ),
        enable_validation=True,
        schema_provider=schema_provider,
    )
    document_store.connect()

    # Extend query_documents to support $in operator for tests
    # Store original method
    original_query = document_store.query_documents

    def enhanced_query(collection, filter_dict, limit=100):
        """Query that supports MongoDB-style $in operator."""
        # Handle $in operator for _id
        if "_id" in filter_dict and isinstance(filter_dict["_id"], dict):
            if "$in" in filter_dict["_id"]:
                doc_ids = filter_dict["_id"]["$in"]
                results = []
                for doc_id in doc_ids:
                    docs = original_query(collection, {"_id": doc_id}, limit)
                    results.extend(docs)
                return results[:limit]

        # Handle $in operator for message_doc_id
        if "message_doc_id" in filter_dict and isinstance(filter_dict["message_doc_id"], dict):
            if "$in" in filter_dict["message_doc_id"]:
                message_doc_ids = filter_dict["message_doc_id"]["$in"]
                results = []
                for message_doc_id in message_doc_ids:
                    docs = original_query(collection, {"message_doc_id": message_doc_id}, limit)
                    results.extend(docs)
                return results[:limit]

        # Default: use original query
        return original_query(collection, filter_dict, limit)

    # Replace the query method on the document store
    document_store.query_documents = enhanced_query

    return document_store
