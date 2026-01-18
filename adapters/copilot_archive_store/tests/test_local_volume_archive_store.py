# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for LocalVolumeArchiveStore."""

import shutil
import tempfile
from pathlib import Path

import pytest
from copilot_archive_store.local_volume_archive_store import LocalVolumeArchiveStore


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def store(temp_dir):
    """Create a LocalVolumeArchiveStore instance for testing."""
    return LocalVolumeArchiveStore(base_path=temp_dir)


def test_store_archive(store, temp_dir):
    """Test storing an archive."""
    content = b"This is a test archive content"
    archive_id = store.store_archive(source_name="test-source", file_path="archive.mbox", content=content)

    # Archive ID should be first 16 chars of SHA256 hash
    assert archive_id is not None
    assert len(archive_id) == 16

    # File should exist on disk
    source_dir = Path(temp_dir) / "test-source"
    assert source_dir.exists()
    assert (source_dir / "archive.mbox").exists()

    # Content should match
    with open(source_dir / "archive.mbox", "rb") as f:
        stored_content = f.read()
    assert stored_content == content


def test_get_archive(store):
    """Test retrieving an archive."""
    content = b"Test archive content"
    archive_id = store.store_archive(source_name="test-source", file_path="test.mbox", content=content)

    # Retrieve the archive
    retrieved = store.get_archive(archive_id)
    assert retrieved == content


def test_get_archive_not_found(store):
    """Test retrieving non-existent archive returns None."""
    result = store.get_archive("nonexistent_id")
    assert result is None


def test_get_archive_by_hash(store):
    """Test retrieving archive ID by content hash."""
    import hashlib

    content = b"Test content for hash lookup"
    content_hash = hashlib.sha256(content).hexdigest()

    # Store the archive
    archive_id = store.store_archive(source_name="test-source", file_path="test.mbox", content=content)

    # Look up by hash
    found_id = store.get_archive_by_hash(content_hash)
    assert found_id == archive_id


def test_get_archive_by_hash_not_found(store):
    """Test hash lookup for non-existent content."""
    result = store.get_archive_by_hash("0" * 64)
    assert result is None


def test_archive_exists(store):
    """Test checking if archive exists."""
    content = b"Test content"
    archive_id = store.store_archive(source_name="test-source", file_path="test.mbox", content=content)

    # Should exist
    assert store.archive_exists(archive_id) is True

    # Non-existent should not exist
    assert store.archive_exists("nonexistent") is False


def test_delete_archive(store, temp_dir):
    """Test deleting an archive."""
    content = b"Test content to delete"
    archive_id = store.store_archive(source_name="test-source", file_path="test.mbox", content=content)

    # Verify it exists
    assert store.archive_exists(archive_id) is True

    # Delete it
    deleted = store.delete_archive(archive_id)
    assert deleted is True

    # Should no longer exist
    assert store.archive_exists(archive_id) is False

    # File should be removed from disk
    source_dir = Path(temp_dir) / "test-source"
    assert not (source_dir / "test.mbox").exists()


def test_delete_archive_not_found(store):
    """Test deleting non-existent archive returns False."""
    result = store.delete_archive("nonexistent")
    assert result is False


def test_list_archives(store):
    """Test listing archives for a source."""
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


def test_list_archives_empty(store):
    """Test listing archives when none exist for a source."""
    archives = store.list_archives("nonexistent-source")
    assert archives == []


def test_deduplication(store):
    """Test that storing the same content twice returns same archive_id."""
    content = b"Duplicate content"

    id1 = store.store_archive("source-a", "file1.mbox", content)
    id2 = store.store_archive("source-b", "file2.mbox", content)

    # Same content should produce same ID (deduplication)
    assert id1 == id2


def test_metadata_persistence(temp_dir):
    """Test that metadata persists across store instances."""
    content = b"Persistent content"

    # Create store and add archive
    store1 = LocalVolumeArchiveStore(base_path=temp_dir)
    archive_id = store1.store_archive("test-source", "test.mbox", content)

    # Create new store instance (should load existing metadata)
    store2 = LocalVolumeArchiveStore(base_path=temp_dir)

    # Should be able to retrieve archive
    retrieved = store2.get_archive(archive_id)
    assert retrieved == content

    # Should appear in listings
    archives = store2.list_archives("test-source")
    assert len(archives) == 1
    assert archives[0]["archive_id"] == archive_id


def test_archive_metadata_structure(store):
    """Test that archive metadata has correct structure."""
    content = b"Test content"
    archive_id = store.store_archive("test-source", "test.mbox", content)

    archives = store.list_archives("test-source")
    assert len(archives) == 1

    metadata = archives[0]
    assert "archive_id" in metadata
    assert "source_name" in metadata
    assert "file_path" in metadata
    assert "original_path" in metadata
    assert "content_hash" in metadata
    assert "size_bytes" in metadata
    assert "stored_at" in metadata

    assert metadata["archive_id"] == archive_id
    assert metadata["source_name"] == "test-source"
    assert metadata["size_bytes"] == len(content)
