# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Unit tests for archive fetcher module."""

import os
import tempfile
import pytest
from pathlib import Path

from app.archive_fetcher import (
    LocalFetcher,
    calculate_file_hash,
    create_fetcher,
)
from app.config import SourceConfig


class TestCalculateFileHash:
    """Tests for calculate_file_hash function."""

    def test_calculate_file_hash_sha256(self):
        """Test calculating SHA256 hash of a file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("test content")
            f.flush()
            file_path = f.name

        try:
            file_hash = calculate_file_hash(file_path)
            # Known hash for "test content"
            expected = "6ae8a75555209fd6c44157c0aed8016e763ff435a19cf186f76863140143ff72"
            assert file_hash == expected
        finally:
            os.unlink(file_path)

    def test_calculate_file_hash_consistency(self):
        """Test that hash is consistent across multiple calls."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("consistent content")
            f.flush()
            file_path = f.name

        try:
            hash1 = calculate_file_hash(file_path)
            hash2 = calculate_file_hash(file_path)
            assert hash1 == hash2
        finally:
            os.unlink(file_path)


class TestLocalFetcher:
    """Tests for LocalFetcher."""

    def test_local_fetcher_copy_file(self):
        """Test copying a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source file
            source_file = os.path.join(tmpdir, "source.mbox")
            with open(source_file, "w") as f:
                f.write("test mail content")

            # Create destination directory
            dest_dir = os.path.join(tmpdir, "dest")

            # Create fetcher and fetch
            source = SourceConfig(
                name="test",
                source_type="local",
                url=source_file,
            )
            fetcher = LocalFetcher(source)
            success, file_paths, error = fetcher.fetch(dest_dir)

            assert success is True
            assert file_paths is not None
            assert len(file_paths) == 1
            file_path = file_paths[0]
            assert os.path.exists(file_path)
            assert "source.mbox" in file_path

            # Verify content
            with open(file_path, "r") as f:
                content = f.read()
                assert content == "test mail content"

    def test_local_fetcher_copy_directory(self):
        """Test copying a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create source directory with files
            source_dir = os.path.join(tmpdir, "source_dir")
            os.makedirs(source_dir)
            with open(os.path.join(source_dir, "file1.mbox"), "w") as f:
                f.write("content1")
            with open(os.path.join(source_dir, "file2.mbox"), "w") as f:
                f.write("content2")

            # Create destination directory
            dest_dir = os.path.join(tmpdir, "dest")

            # Create fetcher and fetch
            source = SourceConfig(
                name="test",
                source_type="local",
                url=source_dir,
            )
            fetcher = LocalFetcher(source)
            success, file_paths, error = fetcher.fetch(dest_dir)

            assert success is True
            assert len(file_paths) == 2
            assert any("file1.mbox" in fp for fp in file_paths)
            assert any("file2.mbox" in fp for fp in file_paths)

    def test_local_fetcher_nonexistent_source(self):
        """Test with nonexistent source."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = SourceConfig(
                name="test",
                source_type="local",
                url="/nonexistent/path",
            )
            fetcher = LocalFetcher(source)
            success, file_paths, error = fetcher.fetch(tmpdir)

            assert success is False
            assert error is not None
            assert "does not exist" in error


class TestCreateFetcher:
    """Tests for create_fetcher factory."""

    def test_create_local_fetcher(self):
        """Test creating local fetcher."""
        source = SourceConfig(
            name="test",
            source_type="local",
            url="/path",
        )
        fetcher = create_fetcher(source)
        assert isinstance(fetcher, LocalFetcher)

    def test_create_fetcher_invalid_type(self):
        """Test creating fetcher with invalid type."""
        source = SourceConfig(
            name="test",
            source_type="invalid",
            url="/path",
        )
        with pytest.raises(ValueError):
            create_fetcher(source)
