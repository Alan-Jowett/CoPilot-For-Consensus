# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for AzureBlobArchiveStore with mocked Azure SDK."""

from unittest.mock import MagicMock, patch

import pytest

# Test if azure-storage-blob is available
try:
    from azure.core.exceptions import ResourceNotFoundError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

if AZURE_AVAILABLE:
    from copilot_archive_store import AzureBlobArchiveStore


@pytest.mark.skipif(not AZURE_AVAILABLE, reason="azure-storage-blob not installed")
class TestAzureBlobArchiveStore:
    """Test suite for AzureBlobArchiveStore."""

    @pytest.fixture
    def mock_blob_service_client(self):
        """Create a mock BlobServiceClient."""
        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            mock_service = MagicMock()
            mock_bsc.return_value = mock_service

            # Mock container client
            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container

            # Mock container creation (success or already exists)
            mock_container.create_container.return_value = None

            yield mock_bsc, mock_service, mock_container

    @pytest.fixture
    def store(self, mock_blob_service_client):
        """Create an AzureBlobArchiveStore instance with mocked Azure SDK."""
        _, mock_service, mock_container = mock_blob_service_client

        # Mock metadata blob (initially not found)
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError("Not found")
        mock_container.get_blob_client.return_value = mock_metadata_blob

        store = AzureBlobArchiveStore(
            account_name="testaccount",
            account_key="testkey123==",
            container_name="test-archives",
            prefix="test-prefix"
        )

        # Reset mock for test usage
        mock_container.get_blob_client.reset_mock()

        return store

    def test_initialization_with_account_key(self, mock_blob_service_client):
        """Test initialization with account name and key."""
        mock_bsc, mock_service, mock_container = mock_blob_service_client

        # Mock metadata blob (not found initially)
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
        mock_container.get_blob_client.return_value = mock_metadata_blob

        store = AzureBlobArchiveStore(
            account_name="testaccount",
            account_key="testkey123==",
            container_name="archives"
        )

        assert store.account_name == "testaccount"
        assert store.account_key == "testkey123=="
        assert store.container_name == "archives"
        assert store.prefix == ""

        # Verify BlobServiceClient was called correctly
        mock_bsc.assert_called_once()

    def test_initialization_with_sas_token(self, mock_blob_service_client):
        """Test initialization with SAS token."""
        mock_bsc, mock_service, mock_container = mock_blob_service_client

        # Mock metadata blob
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
        mock_container.get_blob_client.return_value = mock_metadata_blob

        store = AzureBlobArchiveStore(
            account_name="testaccount",
            sas_token="?sv=2022-11-02&ss=b...",
            container_name="archives"
        )

        assert store.sas_token == "?sv=2022-11-02&ss=b..."
        mock_bsc.assert_called_once()

    def test_initialization_with_connection_string(self):
        """Test initialization with connection string."""
        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            mock_service = MagicMock()
            mock_bsc.from_connection_string.return_value = mock_service

            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container

            # Mock metadata blob
            mock_metadata_blob = MagicMock()
            mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
            mock_container.get_blob_client.return_value = mock_metadata_blob

            conn_str = "DefaultEndpointsProtocol=https;AccountName=test;AccountKey=key==;EndpointSuffix=core.windows.net"
            store = AzureBlobArchiveStore(
                connection_string=conn_str,
                container_name="archives"
            )

            assert store.connection_string == conn_str
            mock_bsc.from_connection_string.assert_called_once_with(conn_str)

    def test_initialization_missing_credentials(self):
        """Test that initialization fails without credentials."""
        with pytest.raises(ValueError, match="credentials must be provided"):
            AzureBlobArchiveStore(
                account_name="testaccount",
                container_name="archives"
            )

    def test_initialization_missing_account_name(self):
        """Test that initialization fails without account name."""
        with pytest.raises(ValueError, match="account name must be provided"):
            AzureBlobArchiveStore(
                account_key="testkey123==",
                container_name="archives"
            )

    def test_store_archive(self, store, mock_blob_service_client):
        """Test storing an archive."""
        _, _, mock_container = mock_blob_service_client

        content = b"This is test archive content"

        # Mock blob client for archive
        mock_archive_blob = MagicMock()
        mock_archive_blob.upload_blob.return_value = None

        # Mock blob client for metadata
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.upload_blob.return_value = None

        # Return different mocks based on blob name
        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store archive
        archive_id = store.store_archive(
            source_name="test-source",
            file_path="/path/to/archive.mbox",
            content=content
        )

        # Verify archive ID
        assert archive_id is not None
        assert len(archive_id) == 16

        # Verify blob was uploaded
        mock_archive_blob.upload_blob.assert_called_once()
        upload_call = mock_archive_blob.upload_blob.call_args
        assert upload_call[0][0] == content
        assert upload_call[1]["overwrite"] is True

        # Verify metadata was uploaded
        mock_metadata_blob.upload_blob.assert_called_once()

    def test_get_archive(self, store, mock_blob_service_client):
        """Test retrieving an archive."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test archive content"

        # First store an archive
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        archive_id = store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Mock download
        mock_download_stream = MagicMock()
        mock_download_stream.readall.return_value = content
        mock_archive_blob.download_blob.return_value = mock_download_stream

        # Retrieve the archive
        retrieved = store.get_archive(archive_id)
        assert retrieved == content

    def test_get_archive_not_found(self, store):
        """Test retrieving non-existent archive returns None."""
        result = store.get_archive("nonexistent_id")
        assert result is None

    def test_get_archive_blob_missing(self, store, mock_blob_service_client):
        """Test retrieving archive when blob is missing but metadata exists."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Store archive (mock successful store)
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        archive_id = store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Mock blob not found during retrieval
        mock_archive_blob.download_blob.side_effect = ResourceNotFoundError()

        # Should return None when blob is missing
        result = store.get_archive(archive_id)
        assert result is None

    def test_get_archive_by_hash(self, store, mock_blob_service_client):
        """Test retrieving archive ID by content hash."""
        import hashlib
        _, _, mock_container = mock_blob_service_client

        content = b"Test content for hash lookup"
        content_hash = hashlib.sha256(content).hexdigest()

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store the archive
        archive_id = store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Look up by hash
        found_id = store.get_archive_by_hash(content_hash)
        assert found_id == archive_id

    def test_get_archive_by_hash_not_found(self, store):
        """Test hash lookup for non-existent content."""
        result = store.get_archive_by_hash("0" * 64)
        assert result is None

    def test_archive_exists(self, store, mock_blob_service_client):
        """Test checking if archive exists."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store archive
        archive_id = store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Mock exists check
        mock_archive_blob.exists.return_value = True

        # Should exist
        assert store.archive_exists(archive_id) is True

        # Non-existent should not exist
        assert store.archive_exists("nonexistent") is False

    def test_delete_archive(self, store, mock_blob_service_client):
        """Test deleting an archive."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content to delete"

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store archive
        archive_id = store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Mock exists and delete
        mock_archive_blob.exists.return_value = True
        mock_archive_blob.delete_blob.return_value = None

        # Verify it exists
        assert store.archive_exists(archive_id) is True

        # Delete it
        deleted = store.delete_archive(archive_id)
        assert deleted is True

        # Verify delete was called
        mock_archive_blob.delete_blob.assert_called_once()

        # Should no longer exist using public API
        assert store.archive_exists(archive_id) is False

    def test_delete_archive_not_found(self, store):
        """Test deleting non-existent archive returns False."""
        result = store.delete_archive("nonexistent")
        assert result is False

    def test_list_archives(self, store, mock_blob_service_client):
        """Test listing archives for a source."""
        _, _, mock_container = mock_blob_service_client

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store multiple archives
        content1 = b"Archive 1"
        content2 = b"Archive 2"
        content3 = b"Archive 3"

        id1 = store.store_archive("source-a", "archive1.mbox", content1)
        id2 = store.store_archive("source-a", "archive2.mbox", content2)
        id3 = store.store_archive("source-b", "archive3.mbox", content3)

        # List archives for source-a
        archives_a = store.list_archives("source-a")
        assert len(archives_a) == 2
        archive_ids_a = {a["archive_id"] for a in archives_a}
        assert id1 in archive_ids_a
        assert id2 in archive_ids_a

        # List archives for source-b
        archives_b = store.list_archives("source-b")
        assert len(archives_b) == 1
        assert archives_b[0]["archive_id"] == id3

    def test_list_archives_empty(self, store):
        """Test listing archives when none exist for a source."""
        archives = store.list_archives("nonexistent-source")
        assert archives == []

    def test_deduplication(self, store, mock_blob_service_client):
        """Test that storing the same content twice returns same archive_id."""
        _, _, mock_container = mock_blob_service_client

        content = b"Duplicate content"

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        id1 = store.store_archive("source-a", "file1.mbox", content)
        id2 = store.store_archive("source-b", "file2.mbox", content)

        # Same content should produce same ID (deduplication)
        assert id1 == id2

    def test_archive_metadata_structure(self, store, mock_blob_service_client):
        """Test that archive metadata has correct structure."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Mock blobs
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        archive_id = store.store_archive("test-source", "test.mbox", content)

        archives = store.list_archives("test-source")
        assert len(archives) == 1

        metadata = archives[0]
        assert "archive_id" in metadata
        assert "source_name" in metadata
        assert "file_path" in metadata
        assert "content_hash" in metadata
        assert "size_bytes" in metadata
        assert "stored_at" in metadata

        assert metadata["archive_id"] == archive_id
        assert metadata["source_name"] == "test-source"
        assert metadata["size_bytes"] == len(content)

    def test_prefix_handling(self, mock_blob_service_client):
        """Test that prefix is correctly applied to blob names."""
        _, mock_service, mock_container = mock_blob_service_client

        # Mock metadata blob
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
        mock_container.get_blob_client.return_value = mock_metadata_blob

        store = AzureBlobArchiveStore(
            account_name="testaccount",
            account_key="testkey==",
            container_name="archives",
            prefix="my/prefix"
        )

        # Prefix should be normalized with trailing slash
        assert store.prefix == "my/prefix/"

        # Test blob name generation
        blob_name = store._get_blob_name("test-source", "file.mbox")
        assert blob_name == "my/prefix/test-source/file.mbox"

    @patch.dict('os.environ', {
        'AZURE_STORAGE_ACCOUNT': 'envaccount',
        'AZURE_STORAGE_KEY': 'envkey==',
        'AZURE_STORAGE_CONTAINER': 'envcontainer',
        'AZURE_STORAGE_PREFIX': 'env/prefix'
    })
    def test_environment_variable_configuration(self, mock_blob_service_client):
        """Test configuration from environment variables."""
        _, mock_service, mock_container = mock_blob_service_client

        # Mock metadata blob
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
        mock_container.get_blob_client.return_value = mock_metadata_blob

        store = AzureBlobArchiveStore()

        assert store.account_name == "envaccount"
        assert store.account_key == "envkey=="
        assert store.container_name == "envcontainer"
        assert store.prefix == "env/prefix/"
