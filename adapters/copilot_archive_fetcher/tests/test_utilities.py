# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for utility functions."""

import os
import tempfile

import pytest
from copilot_archive_fetcher import calculate_file_hash


class TestUtilities:
    """Tests for utility functions."""

    def test_calculate_file_hash_sha256(self):
        """Test calculating SHA256 hash of a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            test_content = b"Test content for hashing"

            with open(test_file, "wb") as f:
                f.write(test_content)

            hash_value = calculate_file_hash(test_file)

            # Expected SHA256 of "Test content for hashing"
            assert isinstance(hash_value, str)
            assert len(hash_value) == 64  # SHA256 is 64 hex characters
            assert all(c in "0123456789abcdef" for c in hash_value)

    def test_calculate_file_hash_consistency(self):
        """Test that hash is consistent for same file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "wb") as f:
                f.write(b"Consistent content")

            hash1 = calculate_file_hash(test_file)
            hash2 = calculate_file_hash(test_file)

            assert hash1 == hash2

    def test_calculate_file_hash_different_content(self):
        """Test that different files have different hashes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file1 = os.path.join(tmpdir, "file1.txt")
            file2 = os.path.join(tmpdir, "file2.txt")

            with open(file1, "wb") as f:
                f.write(b"Content 1")
            with open(file2, "wb") as f:
                f.write(b"Content 2")

            hash1 = calculate_file_hash(file1)
            hash2 = calculate_file_hash(file2)

            assert hash1 != hash2

    def test_calculate_file_hash_nonexistent(self):
        """Test hash calculation with nonexistent file."""
        with pytest.raises(FileNotFoundError):
            calculate_file_hash("/nonexistent/file.txt")

    def test_calculate_file_hash_md5(self):
        """Test calculating MD5 hash of a file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "wb") as f:
                f.write(b"Test")

            hash_value = calculate_file_hash(test_file, algorithm="md5")

            assert isinstance(hash_value, str)
            assert len(hash_value) == 32  # MD5 is 32 hex characters

    def test_calculate_file_hash_invalid_algorithm(self):
        """Test hash calculation with invalid algorithm."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test.txt")
            with open(test_file, "wb") as f:
                f.write(b"Test")

            with pytest.raises(ValueError) as exc_info:
                calculate_file_hash(test_file, algorithm="invalid_algo")

            assert "Unsupported hash algorithm" in str(exc_info.value)

    def test_calculate_file_hash_large_file(self):
        """Test hash calculation for larger file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "large.bin")

            # Create a file larger than chunk size (4096 bytes)
            with open(test_file, "wb") as f:
                f.write(b"x" * 10000)

            hash_value = calculate_file_hash(test_file)

            assert isinstance(hash_value, str)
            assert len(hash_value) == 64
