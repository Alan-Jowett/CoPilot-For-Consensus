# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Cosmos DB per-collection container routing."""

from unittest.mock import MagicMock, patch

import pytest
from copilot_config.generated.adapters.document_store import (
    DriverConfig_DocumentStore_AzureCosmosdb,
)
from copilot_storage.azure_cosmos_document_store import AzureCosmosDocumentStore


class TestContainerConfiguration:
    """Tests for container configuration."""

    def test_initialization(self):
        """Test basic initialization."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        assert store.database_name == "copilot"
        assert store.containers == {}  # Empty cache initially

    def test_from_config(self):
        """Test creating store from config."""
        config = DriverConfig_DocumentStore_AzureCosmosdb(
            endpoint="https://test.documents.azure.com:443/",
            key="test_key",
        )
        store = AzureCosmosDocumentStore.from_config(config)

        assert store.endpoint == "https://test.documents.azure.com:443/"
        assert store.key == "test_key"
        assert store.database_name == "copilot"

    def test_endpoint_required(self):
        """Test that endpoint is required."""
        with pytest.raises(ValueError, match="endpoint is required"):
            AzureCosmosDocumentStore(endpoint=None, key="testkey")


class TestContainerRoutingHelpers:
    """Tests for container routing helper methods."""

    def test_get_container_config_known_collections(self):
        """Test container config for known collections."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
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

    def test_get_container_config_unknown_collection(self):
        """Test container config for unknown collections uses collection name."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Unknown collections should use collection name as container name
        container_name, partition_key = store._get_container_config_for_collection("unknown_collection")
        assert container_name == "unknown_collection"
        assert partition_key == "/id"


class TestConnect:
    """Tests for connect() behavior."""

    @patch("azure.cosmos.CosmosClient")
    def test_connect_does_not_create_containers(self, mock_cosmos_client_class):
        """Test that connect only creates database, not containers."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database

        store.connect()

        # Verify database creation
        mock_client.create_database_if_not_exists.assert_called_once_with(id="copilot")

        # Verify no container creation at connect time (containers created on-demand)
        mock_database.create_container_if_not_exists.assert_not_called()


class TestContainerCreation:
    """Tests for on-demand container creation."""

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.cosmos.PartitionKey")
    def test_container_created_on_first_access(self, mock_partition_key_class, mock_cosmos_client_class):
        """Test that containers are created on first access."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store.connect()

        # First access to messages collection should create container
        store._get_container_for_collection("messages")

        mock_database.create_container_if_not_exists.assert_called_once()
        call_args = mock_database.create_container_if_not_exists.call_args
        assert call_args.kwargs["id"] == "messages"

        # Container should be cached
        assert "messages" in store.containers
        assert store.containers["messages"] == mock_container

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.cosmos.PartitionKey")
    def test_container_cached_after_creation(self, mock_partition_key_class, mock_cosmos_client_class):
        """Test that containers are cached after first creation."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store.connect()

        # Access container twice
        store._get_container_for_collection("messages")
        store._get_container_for_collection("messages")

        # Container should only be created once
        assert mock_database.create_container_if_not_exists.call_count == 1


class TestInsertDocument:
    """Tests for insert_document with per-collection routing."""

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.cosmos.PartitionKey")
    def test_insert_routes_to_correct_container(self, mock_partition_key_class, mock_cosmos_client_class):
        """Test that insert routes documents to collection-specific containers."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_messages_container = MagicMock()
        mock_chunks_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database

        # Return different containers for different collections
        def get_container(id, partition_key):
            if id == "messages":
                return mock_messages_container
            elif id == "chunks":
                return mock_chunks_container
            return MagicMock()

        mock_database.create_container_if_not_exists.side_effect = get_container

        store.connect()

        # Insert into messages
        store.insert_document("messages", {"id": "msg-123", "text": "Hello"})
        mock_messages_container.create_item.assert_called_once()

        # Insert into chunks
        store.insert_document("chunks", {"id": "chunk-456", "content": "Chunk data"})
        mock_chunks_container.create_item.assert_called_once()

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.cosmos.PartitionKey")
    def test_insert_does_not_add_collection_field(self, mock_partition_key_class, mock_cosmos_client_class):
        """Test that insert does not add collection field to documents."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container

        store.connect()

        store.insert_document("messages", {"id": "msg-123", "text": "Hello"})

        # Check the document passed to create_item
        call_args = mock_container.create_item.call_args
        doc_body = call_args.kwargs["body"]

        # Document should NOT have collection field
        assert "collection" not in doc_body


class TestGetDocument:
    """Tests for get_document with per-collection routing."""

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.cosmos.PartitionKey")
    def test_get_uses_id_as_partition_key(self, mock_partition_key_class, mock_cosmos_client_class):
        """Test that get uses document ID as partition key."""
        store = AzureCosmosDocumentStore(
            endpoint="https://test.documents.azure.com:443/",
            key="testkey",
        )

        # Mock Cosmos client
        mock_client = MagicMock()
        mock_database = MagicMock()
        mock_container = MagicMock()
        mock_cosmos_client_class.return_value = mock_client
        mock_client.create_database_if_not_exists.return_value = mock_database
        mock_database.create_container_if_not_exists.return_value = mock_container
        mock_container.read_item.return_value = {"id": "msg-123", "text": "Hello"}

        store.connect()

        store.get_document("messages", "msg-123")

        # Check partition key is document ID
        call_args = mock_container.read_item.call_args
        assert call_args.kwargs["partition_key"] == "msg-123"
