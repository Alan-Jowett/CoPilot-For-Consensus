# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for ArchiveAccessor."""

import shutil
import tempfile
from pathlib import Path

import pytest
from copilot_archive_store import (
    ArchiveAccessor,
    LocalVolumeArchiveStore,
    create_archive_accessor,
)


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


@pytest.fixture
def temp_file(temp_dir):
    """Create a temporary file with test content."""
    file_path = Path(temp_dir) / "test_file.mbox"
    content = b"Test file content"
    file_path.write_bytes(content)
    return str(file_path), content


def test_accessor_with_archive_store(store, temp_dir):
    """Test accessor using archive store."""
    content = b"Test archive content"

    # Store archive
    archive_id = store.store_archive("test-source", "test.mbox", content)

    # Create accessor with the store
    accessor = ArchiveAccessor(archive_store=store)

    # Retrieve via archive store
    retrieved = accessor.get_archive_content(archive_id=archive_id)
    assert retrieved == content


def test_accessor_fallback_to_file(temp_file):
    """Test accessor falls back to file access when archive store unavailable."""
    file_path, content = temp_file

    # Create accessor without archive store
    accessor = ArchiveAccessor(archive_store=None, enable_fallback=True)

    # Should fall back to file access
    retrieved = accessor.get_archive_content(fallback_file_path=file_path)
    assert retrieved == content


def test_accessor_no_fallback(temp_file):
    """Test accessor with fallback disabled."""
    file_path, content = temp_file

    # Create accessor with fallback disabled
    accessor = ArchiveAccessor(archive_store=None, enable_fallback=False)

    # Should return None when archive store unavailable and fallback disabled
    retrieved = accessor.get_archive_content(fallback_file_path=file_path)
    assert retrieved is None


def test_accessor_archive_store_priority(store, temp_file, temp_dir):
    """Test that archive store is tried before file fallback."""
    file_path, file_content = temp_file
    archive_content = b"Different archive content"

    # Store different content in archive store
    archive_id = store.store_archive("test-source", "test.mbox", archive_content)

    # Create accessor
    accessor = ArchiveAccessor(archive_store=store, enable_fallback=True)

    # Should use archive store, not file
    retrieved = accessor.get_archive_content(
        archive_id=archive_id,
        fallback_file_path=file_path
    )
    assert retrieved == archive_content
    assert retrieved != file_content


def test_accessor_not_found():
    """Test accessor when content not found."""
    accessor = ArchiveAccessor(archive_store=None, enable_fallback=True)

    # Should return None
    retrieved = accessor.get_archive_content(
        archive_id="nonexistent",
        fallback_file_path="/nonexistent/path"
    )
    assert retrieved is None


def test_check_archive_availability_via_store(store):
    """Test availability check via archive store."""
    content = b"Test content"
    archive_id = store.store_archive("test-source", "test.mbox", content)

    accessor = ArchiveAccessor(archive_store=store)
    available, method = accessor.check_archive_availability(archive_id=archive_id)

    assert available is True
    assert method == "archive_store"


def test_check_archive_availability_via_file(temp_file):
    """Test availability check via file path."""
    file_path, _ = temp_file

    accessor = ArchiveAccessor(archive_store=None, enable_fallback=True)
    available, method = accessor.check_archive_availability(fallback_file_path=file_path)

    assert available is True
    assert method == "file_path"


def test_check_archive_availability_not_found():
    """Test availability check for non-existent archive."""
    accessor = ArchiveAccessor(archive_store=None, enable_fallback=True)
    available, method = accessor.check_archive_availability(
        archive_id="nonexistent",
        fallback_file_path="/nonexistent/path"
    )

    assert available is False
    assert method == "unavailable"


def test_create_archive_accessor_with_config(temp_dir):
    """Test factory function with configuration."""
    accessor = create_archive_accessor(
        store_type="local",
        base_path=temp_dir
    )

    assert accessor is not None
    assert accessor.archive_store is not None
    assert isinstance(accessor.archive_store, LocalVolumeArchiveStore)


def test_create_archive_accessor_default():
    """Test factory function with defaults."""
    # Should create accessor even if no store type configured
    accessor = create_archive_accessor()

    assert accessor is not None
    # archive_store might be None if ARCHIVE_STORE_TYPE not set
    # That's fine - accessor should still work with file fallback


def test_create_archive_accessor_with_env(monkeypatch, temp_dir):
    """Test factory function reads from environment."""
    monkeypatch.setenv("ARCHIVE_STORE_TYPE", "local")
    monkeypatch.setenv("ARCHIVE_STORE_PATH", str(temp_dir))

    accessor = create_archive_accessor()

    assert accessor is not None
    assert accessor.archive_store is not None


def test_accessor_resilient_to_store_errors(temp_file):
    """Test that accessor handles archive store errors gracefully."""
    file_path, content = temp_file

    # Create a mock store that raises errors
    class ErrorStore:
        def get_archive(self, archive_id):
            raise RuntimeError("Store error")

        def archive_exists(self, archive_id):
            raise RuntimeError("Store error")

    accessor = ArchiveAccessor(archive_store=ErrorStore(), enable_fallback=True)

    # Should fall back to file despite store errors
    retrieved = accessor.get_archive_content(
        archive_id="test",
        fallback_file_path=file_path
    )
    assert retrieved == content
