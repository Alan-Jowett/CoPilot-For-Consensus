# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for local filesystem fetcher."""

import os
import tempfile

from copilot_archive_fetcher import LocalFetcher, SourceConfig


class TestLocalFetcher:
    """Tests for LocalFetcher."""

    def test_local_fetcher_file_copy(self):
        """Test copying a single file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test file
            test_file = os.path.join(tmpdir, "test.txt")
            test_content = b"Test content"
            with open(test_file, "wb") as f:
                f.write(test_content)

            # Create fetcher and fetch
            output_dir = os.path.join(tmpdir, "output")
            config = SourceConfig(name="local-test", source_type="local", url=test_file)
            fetcher = LocalFetcher(config)
            success, files, error = fetcher.fetch(output_dir)

            assert success is True
            assert error is None
            assert files is not None
            assert len(files) == 1

            # Verify file was copied
            copied_file = files[0]
            assert os.path.exists(copied_file)
            with open(copied_file, "rb") as f:
                assert f.read() == test_content

    def test_local_fetcher_directory_copy(self):
        """Test copying a directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a test directory with files
            test_dir = os.path.join(tmpdir, "test_dir")
            os.makedirs(test_dir)

            file1 = os.path.join(test_dir, "file1.txt")
            file2 = os.path.join(test_dir, "file2.txt")

            with open(file1, "w") as f:
                f.write("Content 1")
            with open(file2, "w") as f:
                f.write("Content 2")

            # Create fetcher and fetch
            output_dir = os.path.join(tmpdir, "output")
            config = SourceConfig(name="local-dir-test", source_type="local", url=test_dir)
            fetcher = LocalFetcher(config)
            success, files, error = fetcher.fetch(output_dir)

            assert success is True
            assert error is None
            assert files is not None
            assert len(files) == 2

    def test_local_fetcher_nonexistent_path(self):
        """Test fetching from non-existent path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = SourceConfig(name="local-test", source_type="local", url="/nonexistent/path/to/file")
            fetcher = LocalFetcher(config)
            success, files, error = fetcher.fetch(tmpdir)

            assert success is False
            assert files is None
            assert error is not None
            assert "does not exist" in error

    def test_local_fetcher_subdirectories(self):
        """Test copying directories with subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create nested directory structure
            test_dir = os.path.join(tmpdir, "test_dir")
            subdir = os.path.join(test_dir, "subdir")
            os.makedirs(subdir)

            file1 = os.path.join(test_dir, "file1.txt")
            file2 = os.path.join(subdir, "file2.txt")

            with open(file1, "w") as f:
                f.write("Content 1")
            with open(file2, "w") as f:
                f.write("Content 2")

            # Fetch
            output_dir = os.path.join(tmpdir, "output")
            config = SourceConfig(name="nested-test", source_type="local", url=test_dir)
            fetcher = LocalFetcher(config)
            success, files, error = fetcher.fetch(output_dir)

            assert success is True
            assert len(files) == 2

            # Verify directory structure is preserved
            # The output should have test_dir/nested-test/file1.txt and test_dir/nested-test/subdir/file2.txt
            copied_dir = os.path.join(output_dir, "nested-test")
            assert os.path.exists(copied_dir), f"Expected directory {copied_dir} to exist"
            assert os.path.exists(os.path.join(copied_dir, "file1.txt")), "file1.txt should exist"
            assert os.path.exists(os.path.join(copied_dir, "subdir", "file2.txt")), "subdir/file2.txt should exist"
