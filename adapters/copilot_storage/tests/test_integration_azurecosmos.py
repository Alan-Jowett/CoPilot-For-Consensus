# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for Azure Cosmos DB document store against a real Cosmos DB instance."""

import logging
import os
import time

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_AzureCosmosdb,
)
from copilot_storage import DocumentNotFoundError, DocumentStoreNotConnectedError, create_document_store
from copilot_storage.azure_cosmos_document_store import AzureCosmosDocumentStore

logger = logging.getLogger(__name__)


def get_azurecosmos_config():
    """Get Azure Cosmos DB configuration from environment variables."""
    return AdapterConfig_DocumentStore(
        doc_store_type="azure_cosmosdb",
        driver=DriverConfig_DocumentStore_AzureCosmosdb(
            endpoint=os.getenv("COSMOS_ENDPOINT"),
            key=os.getenv("COSMOS_KEY"),
            database=os.getenv("COSMOS_DATABASE", "test_copilot"),
        ),
    )


@pytest.fixture(scope="module")
def azurecosmos_store():
    """Create and connect to a real Azure Cosmos DB instance for integration tests."""
    config = get_azurecosmos_config()

    # Skip tests if Cosmos DB is not configured
    if not config.driver.endpoint or not config.driver.key:
        pytest.skip("Azure Cosmos DB not configured - set COSMOS_ENDPOINT and COSMOS_KEY")

    # Disable validation for integration tests - we're testing the raw Cosmos DB store.
    # ValidatingDocumentStore wrapper is tested separately in unit tests.
    # Here we verify AzureCosmosDocumentStore works correctly with real Cosmos DB.
    store = create_document_store(config, enable_validation=False)
    assert isinstance(store, AzureCosmosDocumentStore)

    # Attempt to connect with retries using exponential backoff
    max_retries = 3
    base_delay_seconds = 2
    for i in range(max_retries):
        try:
            store.connect()
            break
        except Exception as e:
            if i < max_retries - 1:
                # Exponential backoff: 2, 4, 8 seconds
                time.sleep(base_delay_seconds * (2**i))
            else:
                pytest.skip(f"Could not connect to Azure Cosmos DB - skipping integration tests: {str(e)}")

    yield store

    # Cleanup
    store.disconnect()


def delete_all_items_in_container(store, collection_name: str) -> None:
    """Delete all items in a Cosmos DB container using raw SDK.

    This bypasses the document store's sanitization to get the actual document IDs.
    
    Note: Accesses private method _get_container_for_collection() directly because:
    1. This is test infrastructure, not production code
    2. Integration tests may need internal access for proper cleanup
    3. Adding a public wrapper would expose implementation details unnecessarily
    
    The container uses document ID as the partition key, which is the default
    configuration for this Cosmos DB setup.
    """
    try:
        container = store._get_container_for_collection(collection_name)
        # Query with raw SDK to get document IDs (not sanitized)
        items = list(container.query_items(
            query="SELECT c.id FROM c",
            enable_cross_partition_query=True
        ))
        for item in items:
            try:
                # Uses id as partition key (default for this setup)
                container.delete_item(item=item["id"], partition_key=item["id"])
            except Exception:
                pass  # Ignore individual deletion failures
    except Exception as e:
        logger.debug(f"Cleanup failed (may be expected): {e}")


@pytest.fixture
def clean_collection(azurecosmos_store):
    """Ensure a clean collection for each test."""
    collection_name = "test_integration"

    # Clean up before test using raw SDK
    if azurecosmos_store.database is not None:
        delete_all_items_in_container(azurecosmos_store, collection_name)

    yield collection_name

    # Clean up after test using raw SDK
    if azurecosmos_store.database is not None:
        delete_all_items_in_container(azurecosmos_store, collection_name)


@pytest.mark.integration
class TestAzureCosmosIntegration:
    """Integration tests for Azure Cosmos DB document store."""

    def test_connection(self, azurecosmos_store):
        """Test that we can connect to Azure Cosmos DB."""
        assert azurecosmos_store.client is not None
        assert azurecosmos_store.database is not None

    def test_insert_and_get_document(self, azurecosmos_store, clean_collection):
        """Test inserting and retrieving a document."""
        doc = {
            "name": "Integration Test User",
            "email": "integration@test.com",
            "age": 30,
        }

        doc_id = azurecosmos_store.insert_document(clean_collection, doc)
        assert doc_id is not None

        retrieved = azurecosmos_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert retrieved["name"] == "Integration Test User"
        assert retrieved["email"] == "integration@test.com"
        assert retrieved["age"] == 30

    def test_insert_multiple_documents(self, azurecosmos_store, clean_collection):
        """Test inserting multiple documents."""
        docs = [
            {"name": "User 1", "age": 25},
            {"name": "User 2", "age": 30},
            {"name": "User 3", "age": 35},
        ]

        doc_ids = []
        for doc in docs:
            doc_id = azurecosmos_store.insert_document(clean_collection, doc)
            doc_ids.append(doc_id)

        assert len(doc_ids) == 3

        # Verify all documents can be retrieved
        for doc_id in doc_ids:
            retrieved = azurecosmos_store.get_document(clean_collection, doc_id)
            assert retrieved is not None

    def test_query_documents(self, azurecosmos_store, clean_collection):
        """Test querying documents with filters."""
        # Insert test documents
        azurecosmos_store.insert_document(clean_collection, {"name": "Alice", "age": 30, "city": "NYC"})
        azurecosmos_store.insert_document(clean_collection, {"name": "Bob", "age": 25, "city": "LA"})
        azurecosmos_store.insert_document(clean_collection, {"name": "Charlie", "age": 30, "city": "NYC"})

        # Wait for Cosmos DB indexing (eventual consistency model)
        # Note: This is necessary as Cosmos DB uses eventual consistency for secondary indexes
        time.sleep(1)

        # Query by age
        results = azurecosmos_store.query_documents(clean_collection, {"age": 30})
        assert len(results) == 2
        assert all(doc["age"] == 30 for doc in results)

        # Query by city
        results = azurecosmos_store.query_documents(clean_collection, {"city": "NYC"})
        assert len(results) == 2
        assert all(doc["city"] == "NYC" for doc in results)

        # Query with multiple filters
        results = azurecosmos_store.query_documents(clean_collection, {"age": 30, "city": "NYC"})
        assert len(results) == 2

    def test_query_documents_with_limit(self, azurecosmos_store, clean_collection):
        """Test querying documents with a limit."""
        # Insert multiple documents
        for i in range(10):
            azurecosmos_store.insert_document(clean_collection, {"index": i, "type": "test"})

        # Wait for Cosmos DB indexing (eventual consistency model)
        time.sleep(1)

        # Query with limit
        results = azurecosmos_store.query_documents(clean_collection, {"type": "test"}, limit=5)
        assert len(results) == 5

    @pytest.mark.skipif(
        os.getenv("USE_AZURE_EMULATORS") == "true",
        reason="Cosmos DB vnext-preview emulator has SDK compatibility issue with replace_item - "
               "raises BadRequest error when replacing items. This is a known emulator limitation, "
               "not a code issue. Test passes against real Azure Cosmos DB."
    )
    def test_update_document(self, azurecosmos_store, clean_collection):
        """Test updating a document."""
        # Insert a document
        doc_id = azurecosmos_store.insert_document(clean_collection, {"name": "Update Test", "age": 25, "city": "NYC"})

        # Update the document
        azurecosmos_store.update_document(clean_collection, doc_id, {"age": 26, "city": "LA"})

        # Verify the update
        updated = azurecosmos_store.get_document(clean_collection, doc_id)
        assert updated["age"] == 26
        assert updated["city"] == "LA"
        assert updated["name"] == "Update Test"  # Unchanged field

    def test_update_nonexistent_document(self, azurecosmos_store, clean_collection):
        """Test updating a document that doesn't exist."""

        with pytest.raises(DocumentNotFoundError):
            azurecosmos_store.update_document(clean_collection, "nonexistent_id", {"age": 50})

    def test_delete_document(self, azurecosmos_store, clean_collection):
        """Test deleting a document."""
        # Insert a document
        doc_id = azurecosmos_store.insert_document(clean_collection, {"name": "Delete Test", "age": 30})

        # Verify it exists
        doc = azurecosmos_store.get_document(clean_collection, doc_id)
        assert doc is not None

        # Delete the document
        azurecosmos_store.delete_document(clean_collection, doc_id)

        # Verify it's gone
        doc = azurecosmos_store.get_document(clean_collection, doc_id)
        assert doc is None

    def test_delete_nonexistent_document(self, azurecosmos_store, clean_collection):
        """Test deleting a document that doesn't exist."""

        with pytest.raises(DocumentNotFoundError):
            azurecosmos_store.delete_document(clean_collection, "nonexistent_id")

    def test_complex_document(self, azurecosmos_store, clean_collection):
        """Test storing and retrieving a complex document with nested structures."""
        complex_doc = {
            "user": {
                "name": "Complex User",
                "email": "complex@test.com",
                "profile": {
                    "bio": "Test bio",
                    "interests": ["coding", "testing", "cosmos"],
                },
            },
            "metadata": {
                "created": "2025-01-01",
                "tags": ["test", "integration"],
            },
            "stats": {
                "login_count": 5,
                "last_login": "2025-01-10",
            },
        }

        doc_id = azurecosmos_store.insert_document(clean_collection, complex_doc)
        assert doc_id is not None

        retrieved = azurecosmos_store.get_document(clean_collection, doc_id)
        assert retrieved is not None
        assert retrieved["user"]["name"] == "Complex User"
        assert "coding" in retrieved["user"]["profile"]["interests"]
        assert retrieved["stats"]["login_count"] == 5

    def test_document_with_special_characters(self, azurecosmos_store, clean_collection):
        """Test documents with special characters."""
        doc = {
            "name": "User with 特殊字符 and emojis 🎉",
            "email": "test@example.com",
            "description": "Line 1\nLine 2\tTabbed",
        }

        doc_id = azurecosmos_store.insert_document(clean_collection, doc)
        retrieved = azurecosmos_store.get_document(clean_collection, doc_id)

        assert retrieved["name"] == doc["name"]
        assert retrieved["description"] == doc["description"]

    def test_empty_document(self, azurecosmos_store, clean_collection):
        """Test inserting an empty document."""
        doc_id = azurecosmos_store.insert_document(clean_collection, {})
        assert doc_id is not None

        retrieved = azurecosmos_store.get_document(clean_collection, doc_id)
        # Retrieved document is sanitized (id is stripped as a system field)
        # For an empty document, the result is an empty dict
        assert retrieved is not None
        assert isinstance(retrieved, dict)


@pytest.mark.integration
class TestAzureCosmosEdgeCases:
    """Test edge cases and error handling."""

    def test_insert_without_connection(self):
        """Test that operations fail gracefully without connection."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")
        # Don't connect

        with pytest.raises(DocumentStoreNotConnectedError) as excinfo:
            store.insert_document("test", {"name": "test"})
        assert str(excinfo.value) == "Not connected to Cosmos DB"

    def test_invalid_document_id(self, azurecosmos_store, clean_collection):
        """Test getting a document with an invalid ID format."""
        # Cosmos DB should handle invalid ID gracefully
        result = azurecosmos_store.get_document(clean_collection, "invalid_id_format")
        assert result is None


@pytest.mark.integration
class TestAzureCosmosAggregate:
    """Integration tests for Azure Cosmos DB aggregation functionality."""

    def test_aggregate_simple_match(self, azurecosmos_store, clean_collection):
        """Test aggregation with a simple $match stage."""
        # Insert test documents
        azurecosmos_store.insert_document(clean_collection, {"status": "pending", "value": 10})
        azurecosmos_store.insert_document(clean_collection, {"status": "complete", "value": 20})
        azurecosmos_store.insert_document(clean_collection, {"status": "pending", "value": 30})

        # Wait for Cosmos DB indexing (eventual consistency model)
        time.sleep(1)

        # Aggregate with $match
        pipeline = [{"$match": {"status": "pending"}}]

        results = azurecosmos_store.aggregate_documents(clean_collection, pipeline)

        assert len(results) == 2
        assert all(doc["status"] == "pending" for doc in results)

    def test_aggregate_with_limit(self, azurecosmos_store, clean_collection):
        """Test aggregation with $limit stage."""
        # Insert multiple documents
        for i in range(10):
            azurecosmos_store.insert_document(clean_collection, {"index": i, "type": "test"})

        # Wait for Cosmos DB indexing (eventual consistency model)
        time.sleep(1)

        pipeline = [{"$match": {"type": "test"}}, {"$limit": 3}]

        results = azurecosmos_store.aggregate_documents(clean_collection, pipeline)

        assert len(results) == 3

    def test_aggregate_match_exists(self, azurecosmos_store, clean_collection):
        """Test aggregation with $exists operator."""
        # Insert test documents
        azurecosmos_store.insert_document(clean_collection, {"message_key": "msg1", "archive_id": 1})
        azurecosmos_store.insert_document(clean_collection, {"message_key": "msg2"})
        azurecosmos_store.insert_document(clean_collection, {"message_key": "msg3", "archive_id": 2})

        # Wait for Cosmos DB indexing (eventual consistency model)
        time.sleep(1)

        pipeline = [{"$match": {"message_key": {"$exists": True}}}]

        results = azurecosmos_store.aggregate_documents(clean_collection, pipeline)

        # All documents should have message_key
        assert len(results) == 3
