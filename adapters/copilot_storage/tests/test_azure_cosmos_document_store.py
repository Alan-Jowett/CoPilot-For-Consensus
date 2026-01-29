# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Cosmos DB document store."""

from unittest.mock import MagicMock, patch

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_AzureCosmosdb,
)
from copilot_storage import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
    create_document_store,
)
from copilot_storage.azure_cosmos_document_store import AzureCosmosDocumentStore
from copilot_storage.validating_document_store import ValidatingDocumentStore


class TestDocumentStoreFactoryAzureCosmos:
    """Tests for create_document_store factory function with Azure Cosmos."""

    def test_create_azurecosmos_store(self):
        """Test creating an Azure Cosmos DB document store."""
        config = AdapterConfig_DocumentStore(
            doc_store_type="azure_cosmosdb",
            driver=DriverConfig_DocumentStore_AzureCosmosdb(
                endpoint="https://test.documents.azure.com:443/",
                key="test_key",
                database="test_db",
            ),
        )
        store = create_document_store(
            config,
        )

        assert isinstance(store, ValidatingDocumentStore)
        assert isinstance(store, DocumentStore)
        assert isinstance(store._store, AzureCosmosDocumentStore)
        assert store._store.endpoint == "https://test.documents.azure.com:443/"
        assert store._store.key == "test_key"
        assert store._store.database_name == "test_db"


class TestAzureCosmosDocumentStore:
    """Tests for AzureCosmosDocumentStore."""

    def test_initialization(self):
        """Test Azure Cosmos store initialization."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            database="testdb",
        )

        assert store.endpoint == "https://test.documents.azure.com:443/"
        assert store.key == "testkey"
        assert store.database_name == "testdb"

    def test_default_values(self):
        """Test default initialization values."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert store.database_name == "copilot"

    def test_connect_azure_cosmos_not_installed(self, monkeypatch):
        """Test that connect() raises DocumentStoreConnectionError when azure-cosmos is not installed."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock the azure.cosmos import to raise ImportError
        import builtins

        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "azure.cosmos" or name.startswith("azure.cosmos."):
                raise ImportError("No module named 'azure.cosmos'")
            return original_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        with pytest.raises(DocumentStoreConnectionError, match="azure-cosmos not installed"):
            store.connect()

    def test_connect_missing_endpoint(self):
        """Test that connect() raises error when endpoint is missing."""
        # Attempting to create store with endpoint=None should raise ValueError in __init__
        with pytest.raises(ValueError, match="endpoint is required"):
            AzureCosmosDocumentStore(endpoint=None, key="testkey")

    @patch("azure.identity.DefaultAzureCredential")
    @patch("azure.cosmos.CosmosClient")
    def test_connect_missing_key_uses_managed_identity(self, mock_cosmos_client, mock_credential):
        """Test that connect() uses managed identity when key is missing."""
        mock_cred_instance = MagicMock()
        mock_credential.return_value = mock_cred_instance

        mock_client_instance = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()

        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key=None)

        store.connect()

        # Verify DefaultAzureCredential was used
        mock_credential.assert_called_once()
        mock_cosmos_client.assert_called_once_with(
            "https://test.documents.azure.com:443/", credential=mock_cred_instance
        )

    @patch("azure.cosmos.CosmosClient")
    def test_connect_success(self, mock_cosmos_client):
        """Test successful connection to Cosmos DB."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            database="testdb",
        )

        # Mock the client and database operations
        mock_client_instance = MagicMock()
        mock_database = MagicMock()

        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.create_database_if_not_exists.return_value = mock_database

        store.connect()

        assert store.client is not None
        assert store.database is not None
        mock_cosmos_client.assert_called_once_with("https://test.documents.azure.com:443/", "testkey")

    @patch("azure.cosmos.CosmosClient")
    def test_connect_database_creation_fails(self, mock_cosmos_client):
        """Test that connect() raises error when database creation fails."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock client but make database creation fail
        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.create_database_if_not_exists.side_effect = exceptions.CosmosHttpResponseError(
            status_code=403, message="Forbidden"
        )

        with pytest.raises(DocumentStoreConnectionError, match="Failed to create/access database"):
            store.connect()

    def test_disconnect(self):
        """Test disconnecting from Cosmos DB."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Simulate connected state
        store.client = MagicMock()
        store.database = MagicMock()
        store.containers = {"users": MagicMock()}

        store.disconnect()

        assert store.client is None
        assert store.database is None
        assert store.containers == {}

    def test_insert_document_not_connected(self):
        """Test that insert fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.insert_document("users", {"name": "test"})

    @patch("uuid.uuid4")
    def test_insert_document_success(self, mock_uuid):
        """Test successful document insertion."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock UUID generation
        mock_uuid.return_value = "test-uuid-123"

        # Mock successful insert
        mock_container.create_item.return_value = {"id": "test-uuid-123", "collection": "users", "name": "Alice"}

        doc_id = store.insert_document("users", {"name": "Alice"})

        assert doc_id == "test-uuid-123"
        mock_container.create_item.assert_called_once()

        # Check that the document was modified correctly
        call_args = mock_container.create_item.call_args
        inserted_doc = call_args.kwargs["body"]
        assert inserted_doc["id"] == "test-uuid-123"
        assert inserted_doc["name"] == "Alice"
        # collection field is NOT added in per-collection container mode
        assert "collection" not in inserted_doc

    def test_insert_document_with_existing_id(self):
        """Test inserting document with pre-existing ID."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock successful insert
        mock_container.create_item.return_value = {"id": "user-123", "collection": "users", "name": "Bob"}

        doc_id = store.insert_document("users", {"id": "user-123", "name": "Bob"})

        assert doc_id == "user-123"

    def test_insert_document_uses__id_as_native_id_when_id_missing(self):
        """If caller provides only canonical _id, use it as Cosmos native id."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["archives"] = mock_container

        mock_container.create_item.return_value = {
            "id": "deadbeefdeadbeef",
            "_id": "deadbeefdeadbeef",
            "status": "pending",
        }

        doc_id = store.insert_document("archives", {"_id": "deadbeefdeadbeef", "status": "pending"})

        assert doc_id == "deadbeefdeadbeef"

        inserted_doc = mock_container.create_item.call_args.kwargs["body"]
        assert inserted_doc["id"] == "deadbeefdeadbeef"
        assert inserted_doc["_id"] == "deadbeefdeadbeef"
        # collection field is NOT added in per-collection container mode
        assert "collection" not in inserted_doc

    def test_insert_document_resource_exists(self):
        """Test that insert raises DocumentAlreadyExistsError when document already exists."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock resource exists error
        mock_container.create_item.side_effect = exceptions.CosmosResourceExistsError(
            status_code=409, message="Document already exists"
        )

        with pytest.raises(DocumentAlreadyExistsError, match="already exists"):
            store.insert_document("users", {"id": "user-123", "name": "test"})

    def test_insert_document_throttled(self):
        """Test that insert handles throttling errors."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock throttling error
        mock_container.create_item.side_effect = exceptions.CosmosHttpResponseError(
            status_code=429, message="Too many requests"
        )

        with pytest.raises(DocumentStoreError, match="Throttled"):
            store.insert_document("users", {"name": "test"})

    def test_get_document_not_connected(self):
        """Test that get fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.get_document("users", "test-id")

    def test_get_document_success(self):
        """Test successful document retrieval.

        Note: System fields (id, collection) are removed by sanitization.
        """
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock successful read
        mock_container.read_item.return_value = {"id": "user-123", "collection": "users", "name": "Alice"}

        doc = store.get_document("users", "user-123")

        assert doc is not None
        # System fields (id) are removed by sanitization
        assert "id" not in doc
        assert doc["name"] == "Alice"
        # Partition key is now the document ID
        mock_container.read_item.assert_called_once_with(item="user-123", partition_key="user-123")

    def test_get_document_not_found(self):
        """Test retrieving non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock not found error
        mock_container.read_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )

        doc = store.get_document("users", "nonexistent")

        assert doc is None

    def test_query_documents_not_connected(self):
        """Test that query fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.query_documents("users", {"age": 30})

    def test_query_documents_success(self):
        """Test successful document query."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        mock_container.query_items.return_value = [
            {"id": "user-1", "collection": "users", "age": 30},
            {"id": "user-2", "collection": "users", "age": 30},
        ]

        results = store.query_documents("users", {"age": 30}, limit=100)

        assert len(results) == 2
        assert all(doc["age"] == 30 for doc in results)

    def test_query_documents_with_multiple_filters(self):
        """Test querying with multiple filters."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        mock_container.query_items.return_value = [{"id": "user-1", "collection": "users", "age": 30, "city": "NYC"}]

        results = store.query_documents("users", {"age": 30, "city": "NYC"})

        assert len(results) == 1

        # Verify the SQL query was constructed correctly
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.age = @param0" in query
        assert "c.city = @param1" in query

    def test_query_documents_invalid_limit(self):
        """Test that query with invalid limit raises error without wrapping."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Test with non-integer limit
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.query_documents("users", {"age": 30}, limit="invalid")

        # Test with negative limit
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.query_documents("users", {"age": 30}, limit=-1)

        # Test with zero limit
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.query_documents("users", {"age": 30}, limit=0)

    def test_update_document_not_connected(self):
        """Test that update fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.update_document("users", "test-id", {"age": 31})

    def test_update_document_success(self):
        """Test successful document update."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock read and replace
        mock_container.read_item.return_value = {"id": "user-123", "collection": "users", "name": "Alice", "age": 30}

        store.update_document("users", "user-123", {"age": 31})

        # Verify replace was called with correct partition key
        mock_container.replace_item.assert_called_once()

        # Check the updated document
        call_args = mock_container.replace_item.call_args
        assert call_args.kwargs["item"] == "user-123"
        assert call_args.kwargs["partition_key"] == "user-123"  # Partition key is doc_id
        updated_doc = call_args.kwargs["body"]
        assert updated_doc["id"] == "user-123"  # ID remains unchanged
        assert updated_doc["age"] == 31
        assert updated_doc["name"] == "Alice"
        # collection field is NOT added in per-collection container mode
        assert "collection" not in updated_doc or updated_doc.get("collection") == "users"

    def test_update_document_not_found(self):
        """Test updating non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock not found error
        mock_container.read_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )

        with pytest.raises(DocumentNotFoundError):
            store.update_document("users", "nonexistent", {"age": 31})

    def test_update_document_partition_key_parameter_compatibility(self):
        """Regression test: Verify replace_item partition_key parameter doesn't cause TypeError.

        This test ensures that the azure-cosmos SDK version is compatible and doesn't
        raise 'Session.request() got an unexpected keyword argument partition_key'.
        """
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["threads"] = mock_container

        # Mock read and replace - simulate the SummaryComplete scenario
        mock_container.read_item.return_value = {
            "id": "thread-456",
            "collection": "threads",
            "summary_id": None,
            "subject": "Test Thread",
        }

        # This should NOT raise TypeError about Session.request() and partition_key
        store.update_document("threads", "thread-456", {"summary_id": "summary-789"})

        # Verify replace_item was called with partition_key parameter
        mock_container.replace_item.assert_called_once()
        call_args = mock_container.replace_item.call_args

        # Ensure partition_key was explicitly passed (regression test for the bug)
        assert "partition_key" in call_args.kwargs
        assert call_args.kwargs["partition_key"] == "thread-456"

        # Verify the document was updated correctly
        updated_doc = call_args.kwargs["body"]
        assert updated_doc["id"] == "thread-456"
        assert updated_doc["summary_id"] == "summary-789"
        assert updated_doc["subject"] == "Test Thread"

    def test_delete_document_not_connected(self):
        """Test that delete fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.delete_document("users", "test-id")

    def test_delete_document_success(self):
        """Test successful document deletion."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        store.delete_document("users", "user-123")

        # Partition key is now the document ID
        mock_container.delete_item.assert_called_once_with(item="user-123", partition_key="user-123")

    def test_delete_document_not_found(self):
        """Test deleting non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock not found error
        mock_container.delete_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404, message="Not found"
        )

        with pytest.raises(DocumentNotFoundError):
            store.delete_document("users", "nonexistent")

    def test_aggregate_documents_not_connected(self):
        """Test that aggregation fails when not connected."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        with pytest.raises(DocumentStoreNotConnectedError):
            store.aggregate_documents("users", [{"$match": {"age": 30}}])

    def test_aggregate_documents_simple_match(self):
        """Test aggregation with simple $match."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        mock_container.query_items.return_value = [{"id": "msg-1", "collection": "messages", "status": "pending"}]

        pipeline = [{"$match": {"status": "pending"}}]
        results = store.aggregate_documents("messages", pipeline)

        assert len(results) == 1

        # Verify SQL query was constructed
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.status = @param0" in query

    def test_aggregate_documents_with_exists(self):
        """Test aggregation with $exists operator."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        mock_container.query_items.return_value = []

        pipeline = [{"$match": {"message_key": {"$exists": True}}}]
        store.aggregate_documents("messages", pipeline)

        # Verify SQL query includes IS_DEFINED
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "IS_DEFINED(c.message_key)" in query

    def test_aggregate_documents_with_limit(self):
        """Test aggregation with $limit stage."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        mock_container.query_items.return_value = []

        pipeline = [{"$match": {"status": "pending"}}, {"$limit": 10}]
        store.aggregate_documents("messages", pipeline)

        # Verify SQL query includes OFFSET 0 LIMIT (Cosmos DB syntax)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "OFFSET 0 LIMIT 10" in query

    def test_aggregate_documents_with_lookup(self):
        """Test that $lookup stage performs client-side join."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock query results for messages and chunks
        # First call: messages collection
        # Second call: chunks collection (for $lookup)
        messages = [
            {"id": "msg1", "collection": "messages", "message_key": "key1", "text": "Hello"},
            {"id": "msg2", "collection": "messages", "message_key": "key2", "text": "World"},
        ]
        chunks = [{"id": "chunk1", "collection": "chunks", "message_key": "key1", "chunk_id": "c1"}]

        mock_container.query_items.side_effect = [messages, chunks]

        pipeline = [
            {"$lookup": {"from": "chunks", "localField": "message_key", "foreignField": "message_key", "as": "chunks"}}
        ]

        # Should perform client-side join
        results = store.aggregate_documents("messages", pipeline)
        assert isinstance(results, list)
        assert len(results) == 2

        # msg1 should have one chunk, msg2 should have empty chunks array
        msg1_result = [r for r in results if r["message_key"] == "key1"][0]
        msg2_result = [r for r in results if r["message_key"] == "key2"][0]

        assert len(msg1_result["chunks"]) == 1
        assert msg1_result["chunks"][0]["chunk_id"] == "c1"
        assert len(msg2_result["chunks"]) == 0

    def test_aggregate_documents_lookup_with_match(self):
        """Test $lookup followed by $match to find messages without chunks (chunking service use case)."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock query results
        # First call: messages collection with $match on _id
        # Second call: chunks collection (for $lookup)
        messages = [
            {"id": "msg1", "collection": "messages", "_id": "msg1", "archive_id": 1},
            {"id": "msg2", "collection": "messages", "_id": "msg2", "archive_id": 1},
            {"id": "msg3", "collection": "messages", "_id": "msg3", "archive_id": 1},
        ]
        chunks = [
            {"id": "chunk1", "collection": "chunks", "message_doc_id": "msg1"},
            {"id": "chunk2", "collection": "chunks", "message_doc_id": "msg1"},
        ]

        mock_container.query_items.side_effect = [messages, chunks]

        # Pipeline that matches chunking service requeue logic
        pipeline = [
            {"$match": {"_id": {"$exists": True}}},
            {"$lookup": {"from": "chunks", "localField": "_id", "foreignField": "message_doc_id", "as": "chunks"}},
            {"$match": {"chunks": {"$eq": []}}},
            {"$limit": 1000},
        ]

        results = store.aggregate_documents("messages", pipeline)

        # Should find msg2 and msg3 (messages without chunks)
        assert len(results) == 2
        message_ids = [r["_id"] for r in results]
        assert "msg1" not in message_ids  # msg1 has chunks
        assert "msg2" in message_ids
        assert "msg3" in message_ids

    def test_aggregate_documents_invalid_limit(self):
        """Test that aggregation with invalid limit raises error."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Test with non-integer limit
        pipeline = [{"$match": {"status": "pending"}}, {"$limit": "invalid"}]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)

        # Test with negative limit
        pipeline = [{"$match": {"status": "pending"}}, {"$limit": -1}]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)

        # Test with zero limit
        pipeline = [{"$match": {"status": "pending"}}, {"$limit": 0}]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)

    def test_aggregate_documents_match_with_nested_fields(self):
        """Test $match stage with nested field paths using dot notation."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock query results with nested fields
        messages = [
            {"id": "msg1", "collection": "messages", "user": {"name": "Alice", "email": "alice@example.com"}},
            {"id": "msg2", "collection": "messages", "user": {"name": "Bob", "email": "bob@example.com"}},
            {"id": "msg3", "collection": "messages", "user": {"name": "Alice", "email": "alice2@example.com"}},
        ]

        # Pipeline with nested field match after $lookup
        pipeline = [
            {"$lookup": {"from": "chunks", "localField": "id", "foreignField": "message_id", "as": "chunks"}},
            {"$match": {"user.name": "Alice"}},
        ]

        # Mock query results: first query returns messages, second query for $lookup returns chunks
        mock_container.query_items.side_effect = [messages, []]

        results = store.aggregate_documents("messages", pipeline)

        # Should find only messages where user.name = "Alice"
        assert len(results) == 2
        for result in results:
            assert result["user"]["name"] == "Alice"

    def test_aggregate_documents_lookup_validation_missing_fields(self):
        """Test that $lookup with missing required fields raises error."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Test with missing 'from' field
        pipeline = [{"$lookup": {"localField": "_id", "foreignField": "message_id", "as": "chunks"}}]
        with pytest.raises(DocumentStoreError, match=r"\$lookup requires string values"):
            store.aggregate_documents("messages", pipeline)

        # Test with missing 'as' field
        pipeline = [{"$lookup": {"from": "chunks", "localField": "_id", "foreignField": "message_id"}}]
        with pytest.raises(DocumentStoreError, match=r"\$lookup requires string values"):
            store.aggregate_documents("messages", pipeline)

    def test_aggregate_documents_lookup_validation_empty_strings(self):
        """Test that $lookup with empty string values raises error."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Test with empty 'from' field
        pipeline = [{"$lookup": {"from": "", "localField": "_id", "foreignField": "message_id", "as": "chunks"}}]
        with pytest.raises(DocumentStoreError, match=r"\$lookup requires non-empty values"):
            store.aggregate_documents("messages", pipeline)

        # Test with empty 'localField'
        pipeline = [{"$lookup": {"from": "chunks", "localField": "", "foreignField": "message_id", "as": "chunks"}}]
        with pytest.raises(DocumentStoreError, match=r"\$lookup requires non-empty values"):
            store.aggregate_documents("messages", pipeline)

    def test_aggregate_documents_lookup_validation_invalid_field_names(self):
        """Test that $lookup with invalid field names raises error."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Test with invalid localField (contains special characters)
        pipeline = [
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "id; DROP TABLE",
                    "foreignField": "message_id",
                    "as": "chunks",
                }
            }
        ]
        with pytest.raises(DocumentStoreError, match=r"Invalid localField.*in \$lookup"):
            store.aggregate_documents("messages", pipeline)

        # Test with invalid foreignField
        pipeline = [{"$lookup": {"from": "chunks", "localField": "_id", "foreignField": "message$id", "as": "chunks"}}]
        with pytest.raises(DocumentStoreError, match=r"Invalid foreignField.*in \$lookup"):
            store.aggregate_documents("messages", pipeline)

    def test_aggregate_documents_lookup_foreign_collection_query_failure(self):
        """Test that $lookup raises error when foreign collection query fails."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock connected state
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["messages"] = mock_container
        store.containers["users"] = mock_container

        # Mock the first query (main collection) to succeed
        mock_container.query_items.return_value = [{"id": "msg1", "collection": "messages", "_id": "msg1"}]

        # Create a side effect that succeeds for first call, fails for second
        from azure.cosmos import exceptions as cosmos_exceptions

        def query_side_effect(*args, **kwargs):
            if query_side_effect.call_count == 0:
                query_side_effect.call_count += 1
                return [{"id": "msg1", "collection": "messages", "_id": "msg1"}]
            else:
                raise cosmos_exceptions.CosmosHttpResponseError(status_code=500, message="Internal server error")

        query_side_effect.call_count = 0
        mock_container.query_items.side_effect = query_side_effect

        pipeline = [{"$lookup": {"from": "chunks", "localField": "_id", "foreignField": "message_id", "as": "chunks"}}]

        with pytest.raises(DocumentStoreError, match=r"Failed to query foreign collection.*during \$lookup"):
            store.aggregate_documents("messages", pipeline)


class TestAzureCosmosDocumentStoreValidation:
    """Tests for AzureCosmosDocumentStore validation methods."""

    def test_is_valid_field_name_valid_simple(self):
        """Test field name validation with valid simple names."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert store._is_valid_field_name("name")
        assert store._is_valid_field_name("age")
        assert store._is_valid_field_name("user_id")
        assert store._is_valid_field_name("firstName")
        assert store._is_valid_field_name("id123")

    def test_is_valid_field_name_valid_nested(self):
        """Test field name validation with valid nested names."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert store._is_valid_field_name("user.email")
        assert store._is_valid_field_name("address.city")
        assert store._is_valid_field_name("profile.settings.theme")

    def test_is_valid_field_name_invalid_empty(self):
        """Test field name validation rejects empty strings."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_field_name("")

    def test_is_valid_field_name_invalid_special_chars(self):
        """Test field name validation rejects special characters."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_field_name("name; DROP TABLE")
        assert not store._is_valid_field_name("user@email")
        assert not store._is_valid_field_name("name-with-dash")
        assert not store._is_valid_field_name("field with space")
        assert not store._is_valid_field_name("field'with'quotes")

    def test_is_valid_field_name_invalid_empty_components(self):
        """Test field name validation rejects empty components in nested paths."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_field_name("user..email")
        assert not store._is_valid_field_name(".email")
        assert not store._is_valid_field_name("user.")

    def test_is_valid_field_name_sql_injection_attempts(self):
        """Test field name validation rejects SQL injection attempts."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_field_name("'; DROP TABLE users; --")
        assert not store._is_valid_field_name("1=1 OR name")
        assert not store._is_valid_field_name("field; SELECT *")

    def test_is_valid_document_id_valid(self):
        """Test document ID validation with valid IDs."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert store._is_valid_document_id("abc123")
        assert store._is_valid_document_id("user-001")
        assert store._is_valid_document_id("doc_id_123")
        assert store._is_valid_document_id("simple")

    def test_is_valid_document_id_invalid_chars(self):
        """Test document ID validation rejects invalid characters."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_document_id("doc/id")
        assert not store._is_valid_document_id("doc\\id")
        assert not store._is_valid_document_id("doc#id")
        assert not store._is_valid_document_id("doc?id")

    def test_is_valid_document_id_invalid_empty(self):
        """Test document ID validation rejects empty or None."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_document_id("")
        assert not store._is_valid_document_id(None)

    def test_is_valid_document_id_control_chars(self):
        """Test document ID validation rejects control characters."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        assert not store._is_valid_document_id("doc\x00id")
        assert not store._is_valid_document_id("doc\nid")
        assert not store._is_valid_document_id("doc\tid")


class TestAzureCosmosDocumentStoreQueryOperators:
    """Tests for MongoDB-style query operators in Azure Cosmos DB document store."""

    def test_query_documents_with_in_operator(self):
        """Test query_documents with $in operator translates to Cosmos SQL IN."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container directly without patching azure.cosmos import
        mock_container = MagicMock()
        mock_container.query_items.return_value = [
            {"id": "1", "collection": "archives", "status": "pending"},
            {"id": "2", "collection": "archives", "status": "processing"},
        ]
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with $in operator
        result = store.query_documents(
            collection="archives", filter_dict={"status": {"$in": ["pending", "processing"]}}, limit=100
        )

        # Verify query was built correctly
        mock_container.query_items.assert_called_once()
        call_args = mock_container.query_items.call_args

        # Check the SQL query contains IN clause
        query = call_args.kwargs["query"]
        assert "c.status IN" in query
        assert "@param0" in query
        assert "@param1" in query

        # Check parameters include both values
        parameters = call_args.kwargs["parameters"]
        param_values = [p["value"] for p in parameters if p["name"].startswith("@param")]
        assert "pending" in param_values
        assert "processing" in param_values

        # Verify result
        assert len(result) == 2
        assert result[0]["status"] == "pending"
        assert result[1]["status"] == "processing"

    def test_query_documents_with_in_operator_empty_list(self):
        """Test query_documents with $in operator and empty list returns empty result."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container (should not be called)
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with empty $in list
        result = store.query_documents(collection="archives", filter_dict={"status": {"$in": []}}, limit=100)

        # Should return empty result without querying
        assert result == []
        mock_container.query_items.assert_not_called()

    def test_query_documents_with_in_operator_single_value(self):
        """Test query_documents with $in operator with single value."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = [{"id": "1", "collection": "archives", "status": "pending"}]
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with $in operator with single value
        result = store.query_documents(collection="archives", filter_dict={"status": {"$in": ["pending"]}}, limit=100)

        # Verify query was built correctly
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.status IN" in query
        assert "@param0" in query

        # Verify result
        assert len(result) == 1

    def test_query_documents_with_eq_operator(self):
        """Test query_documents with explicit $eq operator."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = [{"id": "1", "collection": "archives", "status": "completed"}]
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with $eq operator
        result = store.query_documents(collection="archives", filter_dict={"status": {"$eq": "completed"}}, limit=100)

        # Verify query was built correctly
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.status = @param0" in query

        # Verify result
        assert len(result) == 1

    def test_query_documents_mixed_operators(self):
        """Test query_documents with mixed simple and operator filters."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = [
            {"id": "1", "collection": "archives", "status": "pending", "source": "ietf-announce"}
        ]
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with both simple equality and $in operator
        result = store.query_documents(
            collection="archives",
            filter_dict={"source": "ietf-announce", "status": {"$in": ["pending", "processing"]}},
            limit=50,
        )

        # Verify query was built
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.source = @param0" in query
        assert "c.status IN" in query
        assert "LIMIT 50" in query

        # Verify result
        assert len(result) == 1

    def test_aggregate_documents_with_in_operator(self):
        """Test aggregate_documents with $in operator in $match stage."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = [
            {"id": "1", "collection": "archives", "status": "pending"},
            {"id": "2", "collection": "archives", "status": "processing"},
        ]
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Aggregate with $in in $match
        result = store.aggregate_documents(
            collection="archives",
            pipeline=[{"$match": {"status": {"$in": ["pending", "processing"]}}}, {"$limit": 100}],
        )

        # Verify query was built correctly
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.status IN" in query
        assert "LIMIT 100" in query

        # Verify result
        assert len(result) == 2

    def test_query_documents_with_in_operator_non_list_value(self):
        """Test query_documents with $in operator given non-list value logs warning and skips field."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with $in operator with non-list value (should be skipped)
        result = store.query_documents(collection="archives", filter_dict={"status": {"$in": "pending"}}, limit=100)

        # Verify query was built without the $in clause (field skipped)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain IN clause since field was skipped
        assert "c.status IN" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []

    def test_query_documents_with_non_operator_keys(self):
        """Test query_documents with mixed operator and non-operator keys logs warning and skips field."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with mixed operator and non-operator keys (should be skipped)
        result = store.query_documents(
            collection="archives", filter_dict={"status": {"$in": ["pending"], "invalid_key": "value"}}, limit=100
        )

        # Verify query was built without the status clause (field skipped)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain status filter since field was skipped
        assert "c.status" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []

    def test_query_documents_with_unsupported_operator(self):
        """Test query_documents with unsupported operator logs warning and skips operator."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Query with unsupported operator like $gt
        result = store.query_documents(collection="archives", filter_dict={"age": {"$gt": 30}}, limit=100)

        # Verify query was built without the unsupported operator
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain age filter since operator was unsupported
        assert "c.age" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []

    def test_aggregate_documents_with_in_operator_empty_list(self):
        """Test aggregate_documents with $in operator and empty list returns empty result."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container (should not be called)
        mock_container = MagicMock()
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Aggregate with empty $in list
        result = store.aggregate_documents(
            collection="archives", pipeline=[{"$match": {"status": {"$in": []}}}, {"$limit": 100}]
        )

        # Should return empty result without querying
        assert result == []
        mock_container.query_items.assert_not_called()

    def test_aggregate_documents_with_in_operator_non_list_value(self):
        """Test aggregate_documents with $in operator given non-list value logs warning and skips field."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Aggregate with $in operator with non-list value (should be skipped)
        result = store.aggregate_documents(
            collection="archives", pipeline=[{"$match": {"status": {"$in": "pending"}}}, {"$limit": 100}]
        )

        # Verify query was built without the $in clause (field skipped)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain IN clause since field was skipped
        assert "c.status IN" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []

    def test_aggregate_documents_with_non_operator_keys(self):
        """Test aggregate_documents with mixed operator and non-operator keys logs warning and skips field."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Aggregate with mixed operator and non-operator keys (should be skipped)
        result = store.aggregate_documents(
            collection="archives",
            pipeline=[{"$match": {"status": {"$in": ["pending"], "invalid_key": "value"}}}, {"$limit": 100}],
        )

        # Verify query was built without the status clause (field skipped)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain status filter since field was skipped
        assert "c.status" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []

    def test_aggregate_documents_with_unsupported_operator(self):
        """Test aggregate_documents with unsupported operator logs warning and skips operator."""
        store = AzureCosmosDocumentStore(endpoint="https://test.documents.azure.com:443/", key="testkey")

        # Mock container
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.database = MagicMock()

        store.database.create_container_if_not_exists.return_value = mock_container
        store.containers["users"] = mock_container

        # Aggregate with unsupported operator like $regex
        result = store.aggregate_documents(
            collection="archives", pipeline=[{"$match": {"name": {"$regex": "pattern"}}}, {"$limit": 100}]
        )

        # Verify query was built without the unsupported operator
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        # Should not contain name filter since operator was unsupported
        assert "c.name" not in query
        # Should only have the collection filter
        assert "SELECT * FROM c WHERE 1=1" in query  # No collection filter in per-collection container mode

        # Verify result
        assert result == []
