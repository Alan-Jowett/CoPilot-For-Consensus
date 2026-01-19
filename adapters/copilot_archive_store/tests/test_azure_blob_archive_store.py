# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for AzureBlobArchiveStore with mocked Azure SDK."""

from unittest.mock import MagicMock, patch

import pytest

# Test if azure-storage-blob is available
try:
    from azure.core.exceptions import AzureError, ResourceExistsError, ResourceNotFoundError
    from azure.storage.blob import BlobServiceClient  # noqa: F401 - availability check
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

if AZURE_AVAILABLE:
    from copilot_archive_store.azure_blob_archive_store import AzureBlobArchiveStore
    from copilot_archive_store.archive_store import ArchiveStoreConnectionError
    from copilot_config.generated.adapters.archive_store import (
        DriverConfig_ArchiveStore_Azureblob_AccountKey,
        DriverConfig_ArchiveStore_Azureblob_ConnectionString,
        DriverConfig_ArchiveStore_Azureblob_ManagedIdentity,
        DriverConfig_ArchiveStore_Azureblob_SasToken,
    )


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
        mock_metadata_props = MagicMock()
        mock_metadata_props.etag = "etag"
        mock_metadata_blob.get_blob_properties.return_value = mock_metadata_props
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

    def test_from_config_connection_string_maps_fields(self):
        """from_config should map the connection_string variant correctly."""
        cfg = DriverConfig_ArchiveStore_Azureblob_ConnectionString(
            azureblob_connection_string="UseDevelopmentStorage=true",
            azureblob_container_name="archives",
            azureblob_prefix="pfx",
        )

        with patch.object(AzureBlobArchiveStore, "__init__", return_value=None) as mock_init:
            AzureBlobArchiveStore.from_config(cfg)

        kwargs = mock_init.call_args.kwargs
        assert kwargs["connection_string"] == "UseDevelopmentStorage=true"
        assert kwargs["container_name"] == "archives"
        assert kwargs["prefix"] == "pfx"
        assert "account_name" not in kwargs
        assert "account_key" not in kwargs
        assert "sas_token" not in kwargs

    def test_from_config_account_key_maps_fields(self):
        """from_config should map the account_key variant correctly."""
        cfg = DriverConfig_ArchiveStore_Azureblob_AccountKey(
            azureblob_account_name="acct",
            azureblob_account_key="key==",
            azureblob_container_name="archives",
            azureblob_prefix="pfx",
        )

        with patch.object(AzureBlobArchiveStore, "__init__", return_value=None) as mock_init:
            AzureBlobArchiveStore.from_config(cfg)

        kwargs = mock_init.call_args.kwargs
        assert kwargs["account_name"] == "acct"
        assert kwargs["account_key"] == "key=="
        assert kwargs["container_name"] == "archives"
        assert kwargs["prefix"] == "pfx"
        assert "connection_string" not in kwargs
        assert "sas_token" not in kwargs

    def test_from_config_sas_token_maps_fields(self):
        """from_config should map the sas_token variant correctly."""
        cfg = DriverConfig_ArchiveStore_Azureblob_SasToken(
            azureblob_account_name="acct",
            azureblob_sas_token="?sv=2022-11-02&ss=b...",
            azureblob_container_name="archives",
            azureblob_prefix="pfx",
        )

        with patch.object(AzureBlobArchiveStore, "__init__", return_value=None) as mock_init:
            AzureBlobArchiveStore.from_config(cfg)

        kwargs = mock_init.call_args.kwargs
        assert kwargs["account_name"] == "acct"
        assert kwargs["sas_token"] == "?sv=2022-11-02&ss=b..."
        assert kwargs["container_name"] == "archives"
        assert kwargs["prefix"] == "pfx"
        assert "connection_string" not in kwargs
        assert "account_key" not in kwargs

    def test_from_config_managed_identity_maps_fields(self):
        """from_config should map the managed_identity variant correctly."""
        cfg = DriverConfig_ArchiveStore_Azureblob_ManagedIdentity(
            azureblob_account_name="acct",
            azureblob_container_name="archives",
            azureblob_prefix="pfx",
        )

        with patch.object(AzureBlobArchiveStore, "__init__", return_value=None) as mock_init:
            AzureBlobArchiveStore.from_config(cfg)

        kwargs = mock_init.call_args.kwargs
        assert kwargs["account_name"] == "acct"
        assert kwargs["container_name"] == "archives"
        assert kwargs["prefix"] == "pfx"
        assert "connection_string" not in kwargs
        assert "account_key" not in kwargs
        assert "sas_token" not in kwargs

    def test_initialization_missing_credentials(self):
        """Test managed identity behavior when explicit credentials are not provided.

        This test must not perform network I/O. It behaves as follows:
        - If `azure-identity` is not installed, initialization should fail with a clear message.
        - If `azure-identity` is installed, initialization should succeed when the Azure SDK is mocked.
        """
        try:
            import azure.identity  # noqa: F401
            has_identity = True
        except ImportError:
            has_identity = False

        if not has_identity:
            with pytest.raises(ArchiveStoreConnectionError, match="azure-identity is required"):
                AzureBlobArchiveStore(
                    account_name="testaccount",
                    container_name="archives",
                )
            return

        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            mock_service = MagicMock()
            mock_bsc.return_value = mock_service

            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container
            mock_container.create_container.return_value = None

            mock_metadata_blob = MagicMock()
            mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
            mock_container.get_blob_client.return_value = mock_metadata_blob

            store = AzureBlobArchiveStore(
                account_name="testaccount",
                container_name="archives",
            )
            assert store.account_name == "testaccount"

    def test_initialization_missing_account_name(self):
        """Test that initialization fails without account name."""
        with pytest.raises(ValueError, match="Authentication configuration required"):
            AzureBlobArchiveStore(
                account_key="testkey123==",
                container_name="archives"
            )

    def test_get_archive_reload_metadata_on_cache_miss(self, store):
        """get_archive should reload metadata index when cache is stale.

        Long-lived services may start with an empty metadata cache and later
        receive events for archives stored by another instance. The store should
        reload metadata on miss so archives become visible without restart.
        """
        archive_id = "9b548dcbf26aec88"
        content = b"hello-archive"

        # Ensure cache is empty to simulate a long-lived process started before ingest.
        store._metadata = {}
        store._hash_index = {}

        # Mock metadata index blob download to return updated metadata containing the archive.
        metadata_json = (
            '{'
            '  "9b548dcbf26aec88": {'
            '    "archive_id": "9b548dcbf26aec88",'
            '    "source_name": "test",'
            '    "blob_name": "test/test-archive.mbox",'
            '    "original_path": "/data/raw_archives/test/test-archive.mbox",'
            '    "content_hash": "9b548dcbf26aec88e7c66961410ccc204c549eec9bb4bea86fed03ecbe2bb25d",'
            '    "size_bytes": 11,'
            '    "stored_at": "2026-01-19T16:57:18.547683Z"'
            '  }'
            '}'
        ).encode("utf-8")

        mock_metadata_download = MagicMock()
        mock_metadata_download.readall.return_value = metadata_json
        mock_metadata_download.properties.etag = "etag-1"

        mock_metadata_blob = MagicMock()
        mock_metadata_blob.download_blob.return_value = mock_metadata_download

        # Mock archive blob download.
        mock_archive_download = MagicMock()
        mock_archive_download.readall.return_value = content

        mock_archive_blob = MagicMock()
        mock_archive_blob.download_blob.return_value = mock_archive_download

        def _blob_client_for(name: str):
            if name == store.metadata_blob_name:
                return mock_metadata_blob
            if name == "test/test-archive.mbox":
                return mock_archive_blob
            return MagicMock()

        store.container_client.get_blob_client.side_effect = _blob_client_for

        assert store.get_archive(archive_id) == content

    def test_initialization_container_already_exists(self):
        """Test successful initialization when container already exists."""
        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            mock_service = MagicMock()
            mock_bsc.return_value = mock_service

            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container

            # Container creation raises ResourceExistsError (already exists)
            from azure.core.exceptions import ResourceExistsError
            mock_container.create_container.side_effect = ResourceExistsError("Container exists")

            # Mock metadata blob (not found initially)
            mock_metadata_blob = MagicMock()
            mock_metadata_blob.download_blob.side_effect = ResourceNotFoundError()
            mock_container.get_blob_client.return_value = mock_metadata_blob

            # Should succeed even when ResourceExistsError is raised
            store = AzureBlobArchiveStore(
                account_name="testaccount",
                account_key="testkey123==",
                container_name="test-archives"
            )

            assert store.container_name == "test-archives"
            # Verify container creation was attempted
            mock_container.create_container.assert_called_once()

    def test_initialization_azure_error_during_container_creation(self):
        """Test that unexpected Azure errors during container creation are surfaced."""
        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            mock_service = MagicMock()
            mock_bsc.return_value = mock_service

            mock_container = MagicMock()
            mock_service.get_container_client.return_value = mock_container

            # Container creation raises an unexpected AzureError
            mock_container.create_container.side_effect = AzureError("Network error")

            # Should raise ArchiveStoreConnectionError with preserved cause
            with pytest.raises(ArchiveStoreConnectionError, match="Unexpected Azure error while creating container"):
                AzureBlobArchiveStore(
                    account_name="testaccount",
                    account_key="testkey123==",
                    container_name="test-archives"
                )

    def test_initialization_blob_service_client_failure(self):
        """Test that BlobServiceClient initialization failures are wrapped properly."""
        with patch('copilot_archive_store.azure_blob_archive_store.BlobServiceClient') as mock_bsc:
            # BlobServiceClient constructor raises an exception
            mock_bsc.side_effect = ValueError("Invalid connection string")

            # Should raise ArchiveStoreConnectionError with wrapped cause
            with pytest.raises(ArchiveStoreConnectionError, match="Failed to initialize Azure Blob Archive Store"):
                AzureBlobArchiveStore(
                    account_name="testaccount",
                    account_key="testkey123==",
                    container_name="test-archives"
                )

    def test_store_archive(self, store, mock_blob_service_client):
        """Test storing an archive with ETag fallback to get_blob_properties."""
        _, _, mock_container = mock_blob_service_client

        content = b"This is test archive content"

        # Mock blob client for archive
        mock_archive_blob = MagicMock()
        mock_archive_blob.upload_blob.return_value = None

        # Mock blob client for metadata with None result (triggers get_blob_properties fallback)
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.upload_blob.return_value = None
        mock_metadata_props = MagicMock()
        mock_metadata_props.etag = "etag"
        mock_metadata_blob.get_blob_properties.return_value = mock_metadata_props

        # Return different mocks based on blob name
        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Store archive
        store.store_archive(
            source_name="test-source",
            file_path="/path/to/archive.mbox",
            content=content
        )

        # Verify archive blob was uploaded
        mock_archive_blob.upload_blob.assert_called_once()
        upload_call = mock_archive_blob.upload_blob.call_args
        assert upload_call[0][0] == content
        assert upload_call[1]["overwrite"] is True

        # Verify metadata was uploaded
        mock_metadata_blob.upload_blob.assert_called_once()

        # Verify get_blob_properties WAS called (result was None)
        mock_metadata_blob.get_blob_properties.assert_called_once()

    def test_store_archive_etag_from_result_object(self, store, mock_blob_service_client):
        """Test that ETag is extracted from upload_blob result when it has etag attribute."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Mock result object with etag attribute
        mock_result = MagicMock()
        mock_result.etag = "result-etag"

        # Mock blob client for archive
        mock_archive_blob = MagicMock()
        mock_archive_blob.upload_blob.return_value = None

        # Mock blob client for metadata with result object
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.upload_blob.return_value = mock_result
        mock_metadata_blob.get_blob_properties.return_value = MagicMock(etag="properties-etag")

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Verify get_blob_properties was NOT called (result had etag attribute)
        mock_metadata_blob.get_blob_properties.assert_not_called()

    def test_store_archive_etag_from_dict_result(self, store, mock_blob_service_client):
        """Test that ETag is extracted from upload_blob result when it's a dict with etag key."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Mock dict result with etag key
        mock_result = {"etag": "dict-etag"}

        # Mock blob client for archive
        mock_archive_blob = MagicMock()
        mock_archive_blob.upload_blob.return_value = None

        # Mock blob client for metadata with dict result
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.upload_blob.return_value = mock_result
        mock_metadata_blob.get_blob_properties.return_value = MagicMock(etag="properties-etag")

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Verify get_blob_properties was NOT called (result was dict with etag)
        mock_metadata_blob.get_blob_properties.assert_not_called()

    def test_store_archive_etag_refresh_failure(self, store, mock_blob_service_client):
        """Test that ETag refresh failure doesn't fail the save operation."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test content"

        # Mock blob client for archive
        mock_archive_blob = MagicMock()
        mock_archive_blob.upload_blob.return_value = None

        # Mock blob client for metadata: upload returns None, get_blob_properties raises AzureError
        mock_metadata_blob = MagicMock()
        mock_metadata_blob.upload_blob.return_value = None
        mock_metadata_blob.get_blob_properties.side_effect = AzureError("Network error during refresh")

        def get_blob_client_side_effect(blob_name):
            if "metadata" in blob_name:
                return mock_metadata_blob
            else:
                return mock_archive_blob

        mock_container.get_blob_client.side_effect = get_blob_client_side_effect

        # Should NOT raise an exception despite ETag refresh failure
        store.store_archive(
            source_name="test-source",
            file_path="test.mbox",
            content=content
        )

        # Verify get_blob_properties was called (and failed)
        mock_metadata_blob.get_blob_properties.assert_called_once()

    def test_get_archive(self, store, mock_blob_service_client):
        """Test retrieving an archive."""
        _, _, mock_container = mock_blob_service_client

        content = b"Test archive content"

        # First store an archive
        mock_archive_blob = MagicMock()
        mock_metadata_blob = MagicMock()
        mock_metadata_props = MagicMock()
        mock_metadata_props.etag = "etag"
        mock_metadata_blob.get_blob_properties.return_value = mock_metadata_props

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
        mock_metadata_props = MagicMock()
        mock_metadata_props.etag = "etag"
        mock_metadata_blob.get_blob_properties.return_value = mock_metadata_props

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

        with pytest.raises(ValueError, match="Authentication configuration required"):
            AzureBlobArchiveStore()
