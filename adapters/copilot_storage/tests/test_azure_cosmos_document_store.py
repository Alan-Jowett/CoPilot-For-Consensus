# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Cosmos DB document store."""

from unittest.mock import MagicMock, patch

import pytest
from copilot_storage import (
    AzureCosmosDocumentStore,
    DocumentNotFoundError,
    DocumentStore,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
    create_document_store,
)


class TestDocumentStoreFactoryAzureCosmos:
    """Tests for create_document_store factory function with Azure Cosmos."""

    def test_create_azurecosmos_store(self):
        """Test creating an Azure Cosmos DB document store."""
        store = create_document_store(
            store_type="azurecosmos",
            endpoint="https://test.documents.azure.com:443/",
            key="test_key",
            database="test_db",
            container="test_container"
        )

        assert isinstance(store, AzureCosmosDocumentStore)
        assert isinstance(store, DocumentStore)
        assert store.endpoint == "https://test.documents.azure.com:443/"
        assert store.key == "test_key"
        assert store.database_name == "test_db"
        assert store.container_name == "test_container"


class TestAzureCosmosDocumentStore:
    """Tests for AzureCosmosDocumentStore."""

    def test_initialization(self):
        """Test Azure Cosmos store initialization."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            database="testdb",
            container="testcontainer",
            partition_key="/collection"
        )

        assert store.endpoint == "https://test.documents.azure.com:443/"
        assert store.key == "testkey"
        assert store.database_name == "testdb"
        assert store.container_name == "testcontainer"
        assert store.partition_key == "/collection"

    def test_default_values(self):
        """Test default initialization values."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert store.database_name == "copilot"
        assert store.container_name == "documents"
        assert store.partition_key == "/collection"

    def test_connect_azure_cosmos_not_installed(self, monkeypatch):
        """Test that connect() raises DocumentStoreConnectionError when azure-cosmos is not installed."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

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
        store = AzureCosmosDocumentStore(endpoint=None, key="testkey")

        with pytest.raises(DocumentStoreConnectionError, match="endpoint is required"):
            store.connect()

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
        
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key=None
        )
        
        store.connect()
        
        # Verify DefaultAzureCredential was used
        mock_credential.assert_called_once()
        mock_cosmos_client.assert_called_once_with(
            "https://test.documents.azure.com:443/",
            credential=mock_cred_instance
        )

    @patch("azure.cosmos.CosmosClient")
    def test_connect_success(self, mock_cosmos_client):
        """Test successful connection to Cosmos DB."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            database="testdb",
            container="testcontainer"
        )

        # Mock the client and database/container operations
        mock_client_instance = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()

        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store.connect()

        assert store.client is not None
        assert store.database is not None
        assert store.container is not None
        mock_cosmos_client.assert_called_once_with(
            "https://test.documents.azure.com:443/",
            "testkey"
        )

    @patch("azure.cosmos.CosmosClient")
    def test_connect_database_creation_fails(self, mock_cosmos_client):
        """Test that connect() raises error when database creation fails."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock client but make database creation fail
        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.create_database_if_not_exists.side_effect = \
            exceptions.CosmosHttpResponseError(status_code=403, message="Forbidden")

        with pytest.raises(DocumentStoreConnectionError, match="Failed to create/access database"):
            store.connect()

    def test_disconnect(self):
        """Test disconnecting from Cosmos DB."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Simulate connected state
        store.client = MagicMock()
        store.database = MagicMock()
        store.container = MagicMock()

        store.disconnect()

        assert store.client is None
        assert store.database is None
        assert store.container is None

    def test_insert_document_not_connected(self):
        """Test that insert fails when not connected."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.insert_document("users", {"name": "test"})

    @patch("uuid.uuid4")
    def test_insert_document_success(self, mock_uuid):
        """Test successful document insertion."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock UUID generation
        mock_uuid.return_value = "test-uuid-123"

        # Mock successful insert
        mock_container.create_item.return_value = {
            "id": "test-uuid-123",
            "collection": "users",
            "name": "Alice"
        }

        doc_id = store.insert_document("users", {"name": "Alice"})

        assert doc_id == "test-uuid-123"
        mock_container.create_item.assert_called_once()

        # Check that the document was modified correctly
        call_args = mock_container.create_item.call_args
        inserted_doc = call_args.kwargs["body"]
        assert inserted_doc["id"] == "test-uuid-123"
        assert inserted_doc["collection"] == "users"
        assert inserted_doc["name"] == "Alice"

    def test_insert_document_with_existing_id(self):
        """Test inserting document with pre-existing ID."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock successful insert
        mock_container.create_item.return_value = {
            "id": "user-123",
            "collection": "users",
            "name": "Bob"
        }

        doc_id = store.insert_document("users", {"id": "user-123", "name": "Bob"})

        assert doc_id == "user-123"

    def test_insert_document_resource_exists(self):
        """Test that insert fails when document already exists."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock resource exists error
        mock_container.create_item.side_effect = exceptions.CosmosResourceExistsError(
            status_code=409,
            message="Document already exists"
        )

        with pytest.raises(DocumentStoreError, match="already exists"):
            store.insert_document("users", {"id": "user-123", "name": "test"})

    def test_insert_document_throttled(self):
        """Test that insert handles throttling errors."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock throttling error
        mock_container.create_item.side_effect = exceptions.CosmosHttpResponseError(
            status_code=429,
            message="Too many requests"
        )

        with pytest.raises(DocumentStoreError, match="Throttled"):
            store.insert_document("users", {"name": "test"})

    def test_get_document_not_connected(self):
        """Test that get fails when not connected."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.get_document("users", "test-id")

    def test_get_document_success(self):
        """Test successful document retrieval."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock successful read
        mock_container.read_item.return_value = {
            "id": "user-123",
            "collection": "users",
            "name": "Alice"
        }

        doc = store.get_document("users", "user-123")

        assert doc is not None
        assert doc["id"] == "user-123"
        assert doc["name"] == "Alice"
        mock_container.read_item.assert_called_once_with(
            item="user-123",
            partition_key="users"
        )

    def test_get_document_not_found(self):
        """Test retrieving non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock not found error
        mock_container.read_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404,
            message="Not found"
        )

        doc = store.get_document("users", "nonexistent")

        assert doc is None

    def test_query_documents_not_connected(self):
        """Test that query fails when not connected."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.query_documents("users", {"age": 30})

    def test_query_documents_success(self):
        """Test successful document query."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock query results
        mock_container.query_items.return_value = [
            {"id": "user-1", "collection": "users", "age": 30},
            {"id": "user-2", "collection": "users", "age": 30}
        ]

        results = store.query_documents("users", {"age": 30}, limit=100)

        assert len(results) == 2
        assert all(doc["age"] == 30 for doc in results)

    def test_query_documents_with_multiple_filters(self):
        """Test querying with multiple filters."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock query results
        mock_container.query_items.return_value = [
            {"id": "user-1", "collection": "users", "age": 30, "city": "NYC"}
        ]

        results = store.query_documents("users", {"age": 30, "city": "NYC"})

        assert len(results) == 1

        # Verify the SQL query was constructed correctly
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.age = @param0" in query
        assert "c.city = @param1" in query

    def test_query_documents_invalid_limit(self):
        """Test that query with invalid limit raises error without wrapping."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

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
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.update_document("users", "test-id", {"age": 31})

    def test_update_document_success(self):
        """Test successful document update."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock read and replace
        mock_container.read_item.return_value = {
            "id": "user-123",
            "collection": "users",
            "name": "Alice",
            "age": 30
        }

        store.update_document("users", "user-123", {"age": 31})

        # Verify replace was called
        mock_container.replace_item.assert_called_once()

        # Check the updated document
        call_args = mock_container.replace_item.call_args
        updated_doc = call_args.kwargs["body"]
        assert updated_doc["age"] == 31
        assert updated_doc["name"] == "Alice"
        assert updated_doc["collection"] == "users"

    def test_update_document_not_found(self):
        """Test updating non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock not found error
        mock_container.read_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404,
            message="Not found"
        )

        with pytest.raises(DocumentNotFoundError):
            store.update_document("users", "nonexistent", {"age": 31})

    def test_delete_document_not_connected(self):
        """Test that delete fails when not connected."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.delete_document("users", "test-id")

    def test_delete_document_success(self):
        """Test successful document deletion."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        store.delete_document("users", "user-123")

        mock_container.delete_item.assert_called_once_with(
            item="user-123",
            partition_key="users"
        )

    def test_delete_document_not_found(self):
        """Test deleting non-existent document."""
        from azure.cosmos import exceptions

        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock not found error
        mock_container.delete_item.side_effect = exceptions.CosmosResourceNotFoundError(
            status_code=404,
            message="Not found"
        )

        with pytest.raises(DocumentNotFoundError):
            store.delete_document("users", "nonexistent")

    def test_aggregate_documents_not_connected(self):
        """Test that aggregation fails when not connected."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        with pytest.raises(DocumentStoreNotConnectedError):
            store.aggregate_documents("users", [{"$match": {"age": 30}}])

    def test_aggregate_documents_simple_match(self):
        """Test aggregation with simple $match."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock query results
        mock_container.query_items.return_value = [
            {"id": "msg-1", "collection": "messages", "status": "pending"}
        ]

        pipeline = [{"$match": {"status": "pending"}}]
        results = store.aggregate_documents("messages", pipeline)

        assert len(results) == 1

        # Verify SQL query was constructed
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.status = @param0" in query

    def test_aggregate_documents_with_exists(self):
        """Test aggregation with $exists operator."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

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
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock query results
        mock_container.query_items.return_value = []

        pipeline = [
            {"$match": {"status": "pending"}},
            {"$limit": 10}
        ]
        store.aggregate_documents("messages", pipeline)

        # Verify SQL query includes OFFSET 0 LIMIT (Cosmos DB syntax)
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "OFFSET 0 LIMIT 10" in query

    def test_aggregate_documents_unsupported_lookup(self):
        """Test that $lookup stage is logged as unsupported."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Mock query results
        mock_container.query_items.return_value = []

        pipeline = [
            {
                "$lookup": {
                    "from": "chunks",
                    "localField": "message_key",
                    "foreignField": "message_key",
                    "as": "chunks"
                }
            }
        ]

        # Should not raise an error, just log warning
        results = store.aggregate_documents("messages", pipeline)
        assert isinstance(results, list)

    def test_aggregate_documents_invalid_limit(self):
        """Test that aggregation with invalid limit raises error."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container

        # Test with non-integer limit
        pipeline = [
            {"$match": {"status": "pending"}},
            {"$limit": "invalid"}
        ]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)

        # Test with negative limit
        pipeline = [
            {"$match": {"status": "pending"}},
            {"$limit": -1}
        ]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)

        # Test with zero limit
        pipeline = [
            {"$match": {"status": "pending"}},
            {"$limit": 0}
        ]
        with pytest.raises(DocumentStoreError, match="Invalid limit value"):
            store.aggregate_documents("messages", pipeline)


class TestAzureCosmosDocumentStoreValidation:
    """Tests for AzureCosmosDocumentStore validation methods."""

    def test_is_valid_field_name_valid_simple(self):
        """Test field name validation with valid simple names."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert store._is_valid_field_name("name")
        assert store._is_valid_field_name("age")
        assert store._is_valid_field_name("user_id")
        assert store._is_valid_field_name("firstName")
        assert store._is_valid_field_name("id123")

    def test_is_valid_field_name_valid_nested(self):
        """Test field name validation with valid nested names."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert store._is_valid_field_name("user.email")
        assert store._is_valid_field_name("address.city")
        assert store._is_valid_field_name("profile.settings.theme")

    def test_is_valid_field_name_invalid_empty(self):
        """Test field name validation rejects empty strings."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_field_name("")

    def test_is_valid_field_name_invalid_special_chars(self):
        """Test field name validation rejects special characters."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_field_name("name; DROP TABLE")
        assert not store._is_valid_field_name("user@email")
        assert not store._is_valid_field_name("name-with-dash")
        assert not store._is_valid_field_name("field with space")
        assert not store._is_valid_field_name("field'with'quotes")

    def test_is_valid_field_name_invalid_empty_components(self):
        """Test field name validation rejects empty components in nested paths."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_field_name("user..email")
        assert not store._is_valid_field_name(".email")
        assert not store._is_valid_field_name("user.")

    def test_is_valid_field_name_sql_injection_attempts(self):
        """Test field name validation rejects SQL injection attempts."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_field_name("'; DROP TABLE users; --")
        assert not store._is_valid_field_name("1=1 OR name")
        assert not store._is_valid_field_name("field; SELECT *")

    def test_is_valid_document_id_valid(self):
        """Test document ID validation with valid IDs."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert store._is_valid_document_id("abc123")
        assert store._is_valid_document_id("user-001")
        assert store._is_valid_document_id("doc_id_123")
        assert store._is_valid_document_id("simple")

    def test_is_valid_document_id_invalid_chars(self):
        """Test document ID validation rejects invalid characters."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_document_id("doc/id")
        assert not store._is_valid_document_id("doc\\id")
        assert not store._is_valid_document_id("doc#id")
        assert not store._is_valid_document_id("doc?id")

    def test_is_valid_document_id_invalid_empty(self):
        """Test document ID validation rejects empty or None."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_document_id("")
        assert not store._is_valid_document_id(None)

    def test_is_valid_document_id_control_chars(self):
        """Test document ID validation rejects control characters."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey"
        )

        assert not store._is_valid_document_id("doc\x00id")
        assert not store._is_valid_document_id("doc\nid")
        assert not store._is_valid_document_id("doc\tid")
