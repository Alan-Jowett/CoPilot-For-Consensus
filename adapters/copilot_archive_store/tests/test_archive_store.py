# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ArchiveStore interface."""

from abc import ABC

import pytest
from copilot_archive_store import (
    ArchiveNotFoundError,
    ArchiveStore,
    ArchiveStoreError,
    create_archive_store,
)


def test_archive_store_is_abstract():
    """Test that ArchiveStore is an abstract base class."""
    assert issubclass(ArchiveStore, ABC)

    # Should not be able to instantiate directly
    with pytest.raises(TypeError):
        ArchiveStore()


def test_archive_store_has_required_methods():
    """Test that ArchiveStore defines all required abstract methods."""
    required_methods = [
        'store_archive',
        'get_archive',
        'get_archive_by_hash',
        'archive_exists',
        'delete_archive',
        'list_archives',
    ]

    for method_name in required_methods:
        assert hasattr(ArchiveStore, method_name)
        method = getattr(ArchiveStore, method_name)
        assert callable(method)


def test_create_archive_store_local():
    """Test factory creates local store."""
    store = create_archive_store("local", base_path="/tmp/test_archives")
    assert store is not None
    from copilot_archive_store import LocalVolumeArchiveStore
    assert isinstance(store, LocalVolumeArchiveStore)


def test_create_archive_store_default(tmp_path):
    """Test factory defaults to local store with constant defaults."""
    store = create_archive_store(base_path=str(tmp_path))
    assert store is not None
    from copilot_archive_store import LocalVolumeArchiveStore
    assert isinstance(store, LocalVolumeArchiveStore)


def test_create_archive_store_unknown_type():
    """Test factory raises error for unknown type."""
    with pytest.raises(ValueError, match="Unknown archive store type"):
        create_archive_store("invalid_type")


def test_create_archive_store_mongodb_not_implemented():
    """Test that MongoDB store raises NotImplementedError (until implemented)."""
    # MongoDB backend is planned but not yet implemented
    # The factory will raise NotImplementedError from the stub
    with pytest.raises(NotImplementedError, match="MongoDB backend not yet implemented"):
        create_archive_store("mongodb")


def test_create_archive_store_azure_blob():
    """Test that Azure Blob store can be created with proper credentials."""
    # Azure backend is now implemented
    # Without credentials, it should raise ValueError (not NotImplementedError)
    with pytest.raises(ValueError, match="Azure Storage"):
        create_archive_store("azure_blob")

    # With credentials, it should create an AzureBlobArchiveStore
    # (We can't fully test this without mocking, but we verify it doesn't raise NotImplementedError)
    try:
        from copilot_archive_store import AzureBlobArchiveStore
        # If we can import it, the backend is implemented
        assert AzureBlobArchiveStore is not None
    except ImportError:
        pytest.skip("azure-storage-blob not installed")


def test_create_archive_store_s3_not_implemented():
    """Test that S3 store is not yet implemented."""
    with pytest.raises(NotImplementedError):
        create_archive_store("s3")


def test_archive_store_exceptions():
    """Test that custom exceptions are defined."""
    # All exceptions should inherit from ArchiveStoreError
    assert issubclass(ArchiveNotFoundError, ArchiveStoreError)

    # Test exception instantiation
    error = ArchiveStoreError("test error")
    assert str(error) == "test error"

    not_found = ArchiveNotFoundError("archive not found")
    assert str(not_found) == "archive not found"
