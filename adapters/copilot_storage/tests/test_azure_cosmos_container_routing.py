# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Cosmos DB container routing functionality."""

from unittest.mock import MagicMock, patch

import pytest
from copilot_config.generated.adapters.document_store import (
    AdapterConfig_DocumentStore,
    DriverConfig_DocumentStore_AzureCosmosdb,
)
from copilot_storage import (
    DocumentAlreadyExistsError,
    DocumentNotFoundError,
    DocumentStoreConnectionError,
    DocumentStoreError,
    DocumentStoreNotConnectedError,
    create_document_store,
)
from copilot_storage.azure_cosmos_document_store import AzureCosmosDocumentStore


class TestContainerRoutingConfiguration:
    """Tests for container routing configuration."""

    def test_initialization_with_legacy_mode(self):
        """Test initialization with legacy routing mode."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        assert store.container_routing_mode == "legacy"
        assert store.database_name == "copilot"
        assert store.container_name == "documents"
        assert store.partition_key == "/collection"

    def test_initialization_with_per_type_mode(self):
        """Test initialization with per-type routing mode."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        assert store.container_routing_mode == "per_type"
        assert store.containers == {}  # Empty cache initially

    def test_default_routing_mode_is_legacy(self):
        """Test that default routing mode is legacy for backward compatibility."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        assert store.container_routing_mode == "legacy"

    def test_invalid_routing_mode_raises_error(self):
        """Test that invalid routing mode raises ValueError."""
        with pytest.raises(ValueError, match="Invalid container_routing_mode"):
            AzureCosmosDocumentStore(
                endpoint="https://test.documents.azure.com:443/",
                key="testkey",
                container_routing_mode="invalid_mode",
            )

    def test_from_config_with_routing_mode(self):
        """Test creating store from config with routing mode."""
        config = DriverConfig_DocumentStore_AzureCosmosdb(
            endpoint="https://test.documents.azure.com:443/",
            key="test_key",
            container_routing_mode="per_type",
        )
        store = AzureCosmosDocumentStore.from_config(config)

        assert store.container_routing_mode == "per_type"


class TestContainerRoutingHelpers:
    """Tests for container routing helper methods."""

    def test_get_container_config_legacy_mode(self):
        """Test container config in legacy mode."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # All collections should route to the same container in legacy mode
        for collection in ["messages", "chunks", "archives", "reports"]:
            container_name, partition_key = store._get_container_config_for_collection(collection)
            assert container_name == "documents"
            assert partition_key == "/collection"

    def test_get_container_config_per_type_mode_known_collections(self):
        """Test container config in per-type mode for known collections."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Test source collections
        container_name, partition_key = store._get_container_config_for_collection("messages")
        assert container_name == "messages"
        assert partition_key == "/id"

        container_name, partition_key = store._get_container_config_for_collection("archives")
        assert container_name == "archives"
        assert partition_key == "/id"

        # Test derived collections
        container_name, partition_key = store._get_container_config_for_collection("chunks")
        assert container_name == "chunks"
        assert partition_key == "/id"

        container_name, partition_key = store._get_container_config_for_collection("reports")
        assert container_name == "reports"
        assert partition_key == "/id"

        container_name, partition_key = store._get_container_config_for_collection("summaries")
        assert container_name == "summaries"
        assert partition_key == "/id"

    def test_get_container_config_per_type_mode_unknown_collection(self):
        """Test container config in per-type mode for unknown collections."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Unknown collections should use collection name as container name
        container_name, partition_key = store._get_container_config_for_collection("unknown_collection")
        assert container_name == "unknown_collection"
        assert partition_key == "/id"


class TestConnectWithContainerRouting:
    """Tests for connect() with container routing."""

    @patch("azure.cosmos.CosmosClient")
    def test_connect_legacy_mode_creates_single_container(self, mock_cosmos_client_class):
        """Test that legacy mode creates the single container on connect."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store.connect()

        # Verify database creation
        mock_client.create_database_if_not_exists.assert_called_once_with(id="copilot")

        # Verify container creation in legacy mode
        mock_database.create_container_if_not_exists.assert_called_once()
        call_args = mock_database.create_container_if_not_exists.call_args
        assert call_args.kwargs["id"] == "documents"

        # Verify container is set
        assert store.container is not None

    @patch("azure.cosmos.CosmosClient")
    def test_connect_per_type_mode_does_not_create_containers(self, mock_cosmos_client_class):
        """Test that per-type mode does not create containers upfront."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database

        store.connect()

        # Verify database creation
        mock_client.create_database_if_not_exists.assert_called_once_with(id="copilot")

        # Verify NO container creation in per-type mode
        mock_database.create_container_if_not_exists.assert_not_called()

        # Verify no legacy container is set
        assert store.container is None


class TestInsertWithContainerRouting:
    """Tests for insert_document() with container routing."""

    def test_insert_legacy_mode_adds_collection_field(self):
        """Test that legacy mode adds collection field to documents."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container
        store.database = MagicMock()

        doc_id = store.insert_document("messages", {"id": "msg-123", "text": "Hello"})

        # Verify collection field was added
        call_args = mock_container.create_item.call_args
        inserted_doc = call_args.kwargs["body"]
        assert inserted_doc["collection"] == "messages"
        assert inserted_doc["id"] == "msg-123"
        assert inserted_doc["text"] == "Hello"

    @patch("azure.cosmos.PartitionKey")
    def test_insert_per_type_mode_does_not_add_collection_field(self, mock_partition_key):
        """Test that per-type mode does not add collection field."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        doc_id = store.insert_document("messages", {"id": "msg-123", "text": "Hello"})

        # Verify container was created for messages collection
        mock_database.create_container_if_not_exists.assert_called_once()
        call_args = mock_database.create_container_if_not_exists.call_args
        assert call_args.kwargs["id"] == "messages"

        # Verify collection field was NOT added
        call_args = mock_container.create_item.call_args
        inserted_doc = call_args.kwargs["body"]
        assert "collection" not in inserted_doc
        assert inserted_doc["id"] == "msg-123"
        assert inserted_doc["text"] == "Hello"

    @patch("azure.cosmos.PartitionKey")
    def test_insert_per_type_mode_caches_containers(self, mock_partition_key):
        """Test that per-type mode caches containers after first access."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        # Insert first document
        store.insert_document("messages", {"id": "msg-1", "text": "First"})

        # Insert second document to same collection
        store.insert_document("messages", {"id": "msg-2", "text": "Second"})

        # Verify container was only created once (cached)
        assert mock_database.create_container_if_not_exists.call_count == 1

        # Verify both documents were inserted to the same container
        assert mock_container.create_item.call_count == 2


class TestQueryWithContainerRouting:
    """Tests for query_documents() with container routing."""

    def test_query_legacy_mode_filters_by_collection(self):
        """Test that legacy mode filters by collection field."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock connected state
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.container = mock_container
        store.database = MagicMock()

        store.query_documents("messages", {"status": "pending"}, limit=10)

        # Verify query includes collection filter
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.collection = @collection" in query
        assert call_args.kwargs["partition_key"] == "messages"
        assert call_args.kwargs["enable_cross_partition_query"] is False

    @patch("azure.cosmos.PartitionKey")
    def test_query_per_type_mode_no_collection_filter(self, mock_partition_key):
        """Test that per-type mode does not filter by collection field."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        store.query_documents("messages", {"status": "pending"}, limit=10)

        # Verify query does not include collection filter
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.collection" not in query
        assert "WHERE 1=1" in query
        assert call_args.kwargs["enable_cross_partition_query"] is True


class TestUpdateAndDeleteWithContainerRouting:
    """Tests for update_document() and delete_document() with container routing."""

    def test_update_legacy_mode_uses_collection_as_partition_key(self):
        """Test that legacy mode uses collection as partition key for update."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock connected state
        mock_container = MagicMock()
        mock_container.read_item.return_value = {"id": "msg-1", "collection": "messages", "text": "Old"}
        store.container = mock_container
        store.database = MagicMock()

        store.update_document("messages", "msg-1", {"text": "New"})

        # Verify read used collection as partition key
        read_call_args = mock_container.read_item.call_args
        assert read_call_args.kwargs["partition_key"] == "messages"

        # Verify collection field preserved in update
        replace_call_args = mock_container.replace_item.call_args
        updated_doc = replace_call_args.kwargs["body"]
        assert updated_doc["collection"] == "messages"

    @patch("azure.cosmos.PartitionKey")
    def test_update_per_type_mode_uses_id_as_partition_key(self, mock_partition_key):
        """Test that per-type mode uses document ID as partition key for update."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_container.read_item.return_value = {"id": "msg-1", "text": "Old"}
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        store.update_document("messages", "msg-1", {"text": "New"})

        # Verify read used document ID as partition key
        read_call_args = mock_container.read_item.call_args
        assert read_call_args.kwargs["partition_key"] == "msg-1"

        # Verify collection field NOT added in update
        replace_call_args = mock_container.replace_item.call_args
        updated_doc = replace_call_args.kwargs["body"]
        assert "collection" not in updated_doc

    def test_delete_legacy_mode_uses_collection_as_partition_key(self):
        """Test that legacy mode uses collection as partition key for delete."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock connected state
        mock_container = MagicMock()
        store.container = mock_container
        store.database = MagicMock()

        store.delete_document("messages", "msg-1")

        # Verify delete used collection as partition key
        call_args = mock_container.delete_item.call_args
        assert call_args.kwargs["partition_key"] == "messages"

    @patch("azure.cosmos.PartitionKey")
    def test_delete_per_type_mode_uses_id_as_partition_key(self, mock_partition_key):
        """Test that per-type mode uses document ID as partition key for delete."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        store.delete_document("messages", "msg-1")

        # Verify delete used document ID as partition key
        call_args = mock_container.delete_item.call_args
        assert call_args.kwargs["partition_key"] == "msg-1"


class TestAggregateWithContainerRouting:
    """Tests for aggregate_documents() with container routing."""

    def test_aggregate_legacy_mode_filters_by_collection(self):
        """Test that legacy mode filters by collection in aggregation."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="legacy",
        )

        # Mock connected state
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        store.container = mock_container
        store.database = MagicMock()

        store.aggregate_documents("messages", [{"$match": {"status": "pending"}}, {"$limit": 10}])

        # Verify query includes collection filter
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.collection = @collection" in query
        assert call_args.kwargs["partition_key"] == "messages"

    @patch("azure.cosmos.PartitionKey")
    def test_aggregate_per_type_mode_no_collection_filter(self, mock_partition_key):
        """Test that per-type mode does not filter by collection in aggregation."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
            container_routing_mode="per_type",
        )

        # Mock connected state
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_container.query_items.return_value = []
        mock_database.create_container_if_not_exists.return_value = mock_container
        store.database = mock_database

        store.aggregate_documents("messages", [{"$match": {"status": "pending"}}, {"$limit": 10}])

        # Verify query does not include collection filter
        call_args = mock_container.query_items.call_args
        query = call_args.kwargs["query"]
        assert "c.collection" not in query
        assert "WHERE 1=1" in query
        assert call_args.kwargs["enable_cross_partition_query"] is True
