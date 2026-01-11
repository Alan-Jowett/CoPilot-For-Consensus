# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for secret configuration provider."""

from unittest.mock import MagicMock

import pytest
from copilot_config.secret_provider import SecretConfigProvider


class TestSecretConfigProvider:
    """Tests for SecretConfigProvider."""

    def test_get_secret_value(self):
        """Test getting a secret value."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.return_value = "secret_value"

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get("test_secret") == "secret_value"
        mock_secret_provider.get_secret.assert_called_once_with("test_secret")

    def test_get_missing_secret_returns_default(self):
        """Test getting missing secret returns default."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.side_effect = Exception("Secret not found")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get("missing_secret", "default") == "default"

    def test_get_secret_none_returns_default(self):
        """Test getting None secret returns the None value."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.return_value = None

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get("test_secret", "default") is None

    def test_get_bool_true_values(self):
        """Test getting boolean true values from secrets."""
        for val in ["true", "1", "yes", "on"]:
            mock_secret_provider = MagicMock()
            mock_secret_provider.get_secret.return_value = val

            provider = SecretConfigProvider(secret_provider=mock_secret_provider)

            assert provider.get_bool("test_bool") is True

    def test_get_bool_false_values(self):
        """Test getting boolean false values from secrets."""
        for val in ["false", "0", "no", "off"]:
            mock_secret_provider = MagicMock()
            mock_secret_provider.get_secret.return_value = val

            provider = SecretConfigProvider(secret_provider=mock_secret_provider)

            assert provider.get_bool("test_bool") is False

    def test_get_bool_missing_secret(self):
        """Test getting boolean from missing secret returns default."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.side_effect = Exception("Not found")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_bool("test_bool", default=True) is True

    def test_get_bool_native_type(self):
        """Test getting boolean that's already a bool type."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.return_value = True

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_bool("test_bool") is True

    def test_get_int_value(self):
        """Test getting integer value from secret."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.return_value = "42"

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_int("test_int") == 42

    def test_get_int_invalid_value(self):
        """Test getting integer from non-numeric secret returns default."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.return_value = "not_a_number"

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_int("test_int", 99) == 99

    def test_get_int_missing_secret(self):
        """Test getting integer from missing secret returns default."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret.side_effect = Exception("Not found")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_int("test_int", 99) == 99

    def test_get_bytes_value(self):
        """Test getting bytes value from secret."""
        test_bytes = b"secret_bytes"
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret_bytes.return_value = test_bytes

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_bytes("test_bytes") == test_bytes
        mock_secret_provider.get_secret_bytes.assert_called_once_with("test_bytes")

    def test_get_bytes_missing_secret(self):
        """Test getting bytes from missing secret returns default."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret_bytes.side_effect = Exception("Not found")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        default_bytes = b"default"
        assert provider.get_bytes("test_bytes", default=default_bytes) == default_bytes

    def test_get_bytes_returns_none_by_default(self):
        """Test getting bytes returns None by default when missing."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.get_secret_bytes.side_effect = Exception("Not found")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.get_bytes("test_bytes") is None

    def test_secret_exists_true(self):
        """Test checking if secret exists returns True."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.secret_exists.return_value = True

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.secret_exists("test_secret") is True
        mock_secret_provider.secret_exists.assert_called_once_with("test_secret")

    def test_secret_exists_false(self):
        """Test checking if secret exists returns False."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.secret_exists.return_value = False

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.secret_exists("test_secret") is False

    def test_secret_exists_provider_error(self):
        """Test checking if secret exists handles provider errors."""
        mock_secret_provider = MagicMock()
        mock_secret_provider.secret_exists.side_effect = Exception("Provider error")

        provider = SecretConfigProvider(secret_provider=mock_secret_provider)

        assert provider.secret_exists("test_secret") is False
