# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Integration tests for AzureBlobArchiveStore.

These tests require actual Azure Blob Storage credentials and are skipped
in CI if credentials are not present.

To run these tests locally, set the following environment variables:
- AZURE_STORAGE_ACCOUNT: Your Azure storage account name
- AZURE_STORAGE_KEY or AZURE_STORAGE_SAS_TOKEN: Authentication credentials
- AZURE_STORAGE_CONTAINER: Container name for testing (will be created if needed)
- AZURE_STORAGE_PREFIX (optional): Prefix for test blobs

Or use a connection string:
- AZURE_STORAGE_CONNECTION_STRING: Full Azure Storage connection string
"""

import hashlib
import os

import pytest

# Mark all tests in this module as integration so they can be excluded via -m "not integration"
pytestmark = pytest.mark.integration

# Test if azure-storage-blob is available
try:
    import importlib
    importlib.import_module("azure.storage.blob")
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False

if AZURE_AVAILABLE:
    from copilot_archive_store.azure_blob_archive_store import AzureBlobArchiveStore


def has_azure_credentials() -> bool:
    """Check if Azure credentials are available in environment."""
    has_connection_string = bool(os.getenv("AZURE_STORAGE_CONNECTION_STRING"))
    has_account = bool(os.getenv("AZURE_STORAGE_ACCOUNT"))
    has_key = bool(os.getenv("AZURE_STORAGE_KEY"))
    has_sas = bool(os.getenv("AZURE_STORAGE_SAS_TOKEN"))

    return has_connection_string or (has_account and (has_key or has_sas))


@pytest.mark.skipif(
    not AZURE_AVAILABLE or not has_azure_credentials(),
    reason="Azure credentials not available or azure-storage-blob not installed"
)
class TestAzureBlobArchiveStoreIntegration:
    """Integration tests using actual Azure Blob Storage."""

    @pytest.fixture
    def store(self):
        """Create an AzureBlobArchiveStore instance using environment credentials."""
        # Use a test-specific prefix to isolate test data
        prefix = os.getenv("AZURE_STORAGE_PREFIX", "")
        test_prefix = f"{prefix}integration-tests/" if prefix else "integration-tests/"

        store = AzureBlobArchiveStore(prefix=test_prefix)
        yield store

        # Cleanup: Delete all test blobs created under the test prefix
        # This avoids relying on a hardcoded list of source names
        try:
            from azure.storage.blob import BlobServiceClient

            # Recreate connection to avoid using the store's potentially stale state
            if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
                service_client = BlobServiceClient.from_connection_string(
                    os.environ["AZURE_STORAGE_CONNECTION_STRING"]
                )
            else:
                account_name = os.environ["AZURE_STORAGE_ACCOUNT"]
                if os.getenv("AZURE_STORAGE_KEY"):
                    credential = os.environ["AZURE_STORAGE_KEY"]
                else:
                    credential = os.environ["AZURE_STORAGE_SAS_TOKEN"]
                service_client = BlobServiceClient(
                    account_url=f"https://{account_name}.blob.core.windows.net",
                    credential=credential,
                )

            container_name = os.getenv("AZURE_STORAGE_CONTAINER", "archives")
            container_client = service_client.get_container_client(container_name)

            # Delete all blobs that start with the test prefix
            blobs_to_delete = list(container_client.list_blobs(name_starts_with=test_prefix))
            for blob in blobs_to_delete:
                container_client.delete_blob(blob.name)
            if blobs_to_delete:
                print(f"Cleaned up {len(blobs_to_delete)} test blobs")
        except Exception as e:
            print(f"Cleanup warning: {e}")

    def test_store_and_retrieve_archive(self, store):
        """Test storing and retrieving an archive in Azure."""
        content = b"Integration test archive content"

        # Store archive
        archive_id = store.store_archive(
            source_name="integration-test-source",
            file_path="test-archive.mbox",
            content=content
        )

        assert archive_id is not None
        assert len(archive_id) == 16

        # Retrieve archive
        retrieved = store.get_archive(archive_id)
        assert retrieved == content

    def test_archive_lifecycle(self, store):
        """Test complete lifecycle: store, check, list, delete."""
        content = b"Lifecycle test content"

        # Store
        archive_id = store.store_archive(
            source_name="lifecycle-test",
            file_path="lifecycle.mbox",
            content=content
        )

        # Check exists
        assert store.archive_exists(archive_id) is True

        # List
        archives = store.list_archives("lifecycle-test")
        assert len(archives) == 1
        assert archives[0]["archive_id"] == archive_id

        # Delete
        deleted = store.delete_archive(archive_id)
        assert deleted is True

        # Verify deleted
        assert store.archive_exists(archive_id) is False
        assert store.get_archive(archive_id) is None

    def test_deduplication_in_azure(self, store):
        """Test content deduplication in Azure."""
        content = b"Duplicate content test"

        # Store same content twice with different metadata
        id1 = store.store_archive(
            source_name="dedup-source-1",
            file_path="file1.mbox",
            content=content
        )

        id2 = store.store_archive(
            source_name="dedup-source-2",
            file_path="file2.mbox",
            content=content
        )

        # Should have same ID due to content-addressable storage
        assert id1 == id2

        # Both sources should list the archive
        archives1 = store.list_archives("dedup-source-1")
        archives2 = store.list_archives("dedup-source-2")

        assert len(archives1) == 1
        assert len(archives2) == 1

    def test_hash_lookup_in_azure(self, store):
        """Test looking up archive by content hash."""
        content = b"Hash lookup test content"
        content_hash = hashlib.sha256(content).hexdigest()

        # Store archive
        archive_id = store.store_archive(
            source_name="hash-test",
            file_path="hash-test.mbox",
            content=content
        )

        # Look up by hash
        found_id = store.get_archive_by_hash(content_hash)
        assert found_id == archive_id

    def test_multiple_archives_same_source(self, store):
        """Test storing and listing multiple archives for the same source."""
        source_name = "multi-archive-test"

        # Store multiple archives
        archives_data = [
            (b"Archive 1 content", "archive1.mbox"),
            (b"Archive 2 content", "archive2.mbox"),
            (b"Archive 3 content", "archive3.mbox"),
        ]

        stored_ids = []
        for content, filename in archives_data:
            archive_id = store.store_archive(source_name, filename, content)
            stored_ids.append(archive_id)

        # List all archives for source
        archives = store.list_archives(source_name)
        assert len(archives) == 3

        # Verify all IDs are present
        listed_ids = {a["archive_id"] for a in archives}
        assert set(stored_ids) == listed_ids

    def test_large_archive(self, store):
        """Test storing and retrieving a larger archive (>1MB)."""
        # Create 2MB of test data
        content = b"X" * (2 * 1024 * 1024)

        # Store
        archive_id = store.store_archive(
            source_name="large-test",
            file_path="large-archive.mbox",
            content=content
        )

        # Retrieve and verify
        retrieved = store.get_archive(archive_id)
        assert len(retrieved) == len(content)
        assert retrieved == content

        # Verify metadata
        archives = store.list_archives("large-test")
        assert len(archives) == 1
        assert archives[0]["size_bytes"] == len(content)

    def test_metadata_persistence(self, store):
        """Test that metadata persists across store instances."""
        content = b"Persistence test content"

        # Store archive
        archive_id = store.store_archive(
            source_name="persistence-test",
            file_path="persist.mbox",
            content=content
        )

        # Create new store instance (should load existing metadata)
        prefix = store.prefix
        store2 = AzureBlobArchiveStore(prefix=prefix)

        # Should be able to retrieve archive using new instance
        retrieved = store2.get_archive(archive_id)
        assert retrieved == content

        # Should appear in listings
        archives = store2.list_archives("persistence-test")
        assert len(archives) >= 1
        assert any(a["archive_id"] == archive_id for a in archives)

    def test_special_characters_in_filenames(self, store):
        """Test handling filenames with special characters."""
        content = b"Special chars test"

        # Test various special characters that might appear in filenames
        filenames = [
            "archive with spaces.mbox",
            "archive-with-dashes.mbox",
            "archive_with_underscores.mbox",
            "archive.multiple.dots.mbox",
        ]

        for filename in filenames:
            archive_id = store.store_archive(
                source_name="special-chars-test",
                file_path=filename,
                content=content + filename.encode()
            )

            # Should be able to retrieve
            retrieved = store.get_archive(archive_id)
            assert retrieved is not None


@pytest.mark.skipif(not AZURE_AVAILABLE, reason="azure-storage-blob not installed")
def test_integration_credentials_info():
    """Print information about running integration tests."""
    if has_azure_credentials():
        print("\n✓ Azure credentials found in environment")
        print("  Integration tests will run against actual Azure Blob Storage")
        if os.getenv("AZURE_STORAGE_CONNECTION_STRING"):
            print("  Using: AZURE_STORAGE_CONNECTION_STRING")
        else:
            print(f"  Account: {os.getenv('AZURE_STORAGE_ACCOUNT')}")
            print(f"  Container: {os.getenv('AZURE_STORAGE_CONTAINER', 'archives')}")
    else:
        print("\n✗ Azure credentials not found in environment")
        print("  Integration tests will be skipped")
        print("\nTo run integration tests, set one of:")
        print("  - AZURE_STORAGE_CONNECTION_STRING")
        print("  - AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_KEY")
        print("  - AZURE_STORAGE_ACCOUNT + AZURE_STORAGE_SAS_TOKEN")
