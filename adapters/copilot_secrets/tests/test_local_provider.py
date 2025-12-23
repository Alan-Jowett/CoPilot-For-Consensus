# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for local file secret provider."""

import pytest
from pathlib import Path
import tempfile

from copilot_secrets import (
    LocalFileSecretProvider,
    SecretNotFoundError,
    SecretProviderError,
)


@pytest.fixture
def temp_secrets_dir():
    """Create a temporary directory for secrets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def provider(temp_secrets_dir):
    """Create a LocalFileSecretProvider instance."""
    return LocalFileSecretProvider(base_path=str(temp_secrets_dir))


class TestLocalFileSecretProvider:
    """Test suite for LocalFileSecretProvider."""

    def test_init_with_valid_directory(self, temp_secrets_dir):
        """Test initialization with a valid directory."""
        provider = LocalFileSecretProvider(base_path=str(temp_secrets_dir))
        assert provider.base_path == temp_secrets_dir

    def test_init_with_nonexistent_directory(self):
        """Test initialization with a non-existent directory."""
        with pytest.raises(SecretProviderError, match="does not exist"):
            LocalFileSecretProvider(base_path="/nonexistent/path")

    def test_init_with_file_instead_of_directory(self, temp_secrets_dir):
        """Test initialization with a file path instead of directory."""
        file_path = temp_secrets_dir / "not_a_dir.txt"
        file_path.write_text("content")

        with pytest.raises(SecretProviderError, match="not a directory"):
            LocalFileSecretProvider(base_path=str(file_path))

    def test_get_secret_success(self, provider, temp_secrets_dir):
        """Test successful secret retrieval."""
        secret_file = temp_secrets_dir / "api_key"
        secret_file.write_text("my-secret-api-key\n")

        result = provider.get_secret("api_key")
        assert result == "my-secret-api-key"

    def test_get_secret_strips_whitespace(self, provider, temp_secrets_dir):
        """Test that get_secret strips leading/trailing whitespace."""
        secret_file = temp_secrets_dir / "jwt_key"
        secret_file.write_text("  \n  secret-value  \n  ")

        result = provider.get_secret("jwt_key")
        assert result == "secret-value"

    def test_get_secret_not_found(self, provider):
        """Test retrieval of non-existent secret."""
        with pytest.raises(SecretNotFoundError, match="Secret not found: missing"):
            provider.get_secret("missing")

    def test_get_secret_path_traversal_prevention(self, provider):
        """Test that path traversal attacks are prevented."""
        with pytest.raises(SecretProviderError, match="Invalid secret name"):
            provider.get_secret("../etc/passwd")

        with pytest.raises(SecretProviderError, match="Invalid secret name"):
            provider.get_secret("/etc/passwd")

    def test_get_secret_bytes_success(self, provider, temp_secrets_dir):
        """Test successful binary secret retrieval."""
        secret_file = temp_secrets_dir / "cert.pem"
        binary_content = b"\x00\x01\x02\x03\xff\xfe"
        secret_file.write_bytes(binary_content)

        result = provider.get_secret_bytes("cert.pem")
        assert result == binary_content

    def test_get_secret_bytes_not_found(self, provider):
        """Test binary retrieval of non-existent secret."""
        with pytest.raises(SecretNotFoundError, match="Secret not found"):
            provider.get_secret_bytes("missing_cert")

    def test_get_secret_version_warning(self, provider, temp_secrets_dir, caplog):
        """Test that version parameter logs a warning."""
        secret_file = temp_secrets_dir / "versioned_secret"
        secret_file.write_text("value")

        provider.get_secret("versioned_secret", version="v2")
        assert "Version parameter ignored" in caplog.text

    def test_secret_exists_returns_true(self, provider, temp_secrets_dir):
        """Test secret_exists returns True for existing secrets."""
        secret_file = temp_secrets_dir / "existing"
        secret_file.write_text("value")

        assert provider.secret_exists("existing") is True

    def test_secret_exists_returns_false(self, provider):
        """Test secret_exists returns False for non-existent secrets."""
        assert provider.secret_exists("nonexistent") is False

    def test_secret_exists_directory_returns_false(self, provider, temp_secrets_dir):
        """Test secret_exists returns False for directories."""
        dir_path = temp_secrets_dir / "subdir"
        dir_path.mkdir()

        assert provider.secret_exists("subdir") is False

    def test_get_secret_directory_raises_error(self, provider, temp_secrets_dir):
        """Test that attempting to read a directory raises an error."""
        dir_path = temp_secrets_dir / "subdir"
        dir_path.mkdir()

        with pytest.raises(SecretProviderError, match="not a file"):
            provider.get_secret("subdir")

    def test_multiline_secret(self, provider, temp_secrets_dir):
        """Test retrieval of multi-line secrets (e.g., PEM files)."""
        pem_content = """-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQC7VJTUt9Us8cKj
-----END PRIVATE KEY-----"""

        secret_file = temp_secrets_dir / "private_key.pem"
        secret_file.write_text(pem_content)

        result = provider.get_secret("private_key.pem")
        assert "BEGIN PRIVATE KEY" in result
        assert "END PRIVATE KEY" in result
