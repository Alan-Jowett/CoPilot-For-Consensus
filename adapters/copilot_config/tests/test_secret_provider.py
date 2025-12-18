# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for SecretConfigProvider."""

import pytest
from unittest.mock import Mock, MagicMock

from copilot_config import SecretConfigProvider


class TestSecretConfigProvider:
    """Test suite for SecretConfigProvider."""
    
    @pytest.fixture
    def mock_secret_provider(self):
        """Create a mock secret provider."""
        return Mock()
    
    @pytest.fixture
    def provider(self, mock_secret_provider):
        """Create a SecretConfigProvider instance."""
        return SecretConfigProvider(secret_provider=mock_secret_provider)
    
    def test_get_success(self, provider, mock_secret_provider):
        """Test successful secret retrieval."""
        mock_secret_provider.get_secret.return_value = "secret-value"
        
        result = provider.get("api_key")
        
        assert result == "secret-value"
        mock_secret_provider.get_secret.assert_called_once_with("api_key")
    
    def test_get_with_default(self, provider, mock_secret_provider):
        """Test get returns default when secret not found."""
        mock_secret_provider.get_secret.side_effect = Exception("Not found")
        
        result = provider.get("missing_key", default="default-value")
        
        assert result == "default-value"
    
    def test_get_bool_true(self, provider, mock_secret_provider):
        """Test get_bool returns True for truthy values."""
        test_cases = ["true", "True", "TRUE", "1", "yes", "on"]
        
        for value in test_cases:
            mock_secret_provider.get_secret.return_value = value
            assert provider.get_bool("key") is True
    
    def test_get_bool_false(self, provider, mock_secret_provider):
        """Test get_bool returns False for falsy values."""
        test_cases = ["false", "False", "FALSE", "0", "no", "off"]
        
        for value in test_cases:
            mock_secret_provider.get_secret.return_value = value
            assert provider.get_bool("key") is False
    
    def test_get_bool_default(self, provider, mock_secret_provider):
        """Test get_bool returns default for invalid values."""
        mock_secret_provider.get_secret.return_value = "invalid"
        
        result = provider.get_bool("key", default=True)
        
        assert result is True
    
    def test_get_bool_missing(self, provider, mock_secret_provider):
        """Test get_bool returns default when secret not found."""
        mock_secret_provider.get_secret.side_effect = Exception("Not found")
        
        result = provider.get_bool("missing", default=True)
        
        assert result is True
    
    def test_get_int_success(self, provider, mock_secret_provider):
        """Test successful integer retrieval."""
        mock_secret_provider.get_secret.return_value = "42"
        
        result = provider.get_int("port")
        
        assert result == 42
    
    def test_get_int_invalid(self, provider, mock_secret_provider):
        """Test get_int returns default for invalid values."""
        mock_secret_provider.get_secret.return_value = "not-a-number"
        
        result = provider.get_int("port", default=8080)
        
        assert result == 8080
    
    def test_get_int_missing(self, provider, mock_secret_provider):
        """Test get_int returns default when secret not found."""
        mock_secret_provider.get_secret.side_effect = Exception("Not found")
        
        result = provider.get_int("missing", default=9090)
        
        assert result == 9090
    
    def test_get_bytes_success(self, provider, mock_secret_provider):
        """Test successful binary secret retrieval."""
        binary_data = b"\x00\x01\x02\x03"
        mock_secret_provider.get_secret_bytes.return_value = binary_data
        
        result = provider.get_bytes("cert")
        
        assert result == binary_data
        mock_secret_provider.get_secret_bytes.assert_called_once_with("cert")
    
    def test_get_bytes_missing(self, provider, mock_secret_provider):
        """Test get_bytes returns default when secret not found."""
        mock_secret_provider.get_secret_bytes.side_effect = Exception("Not found")
        
        result = provider.get_bytes("missing", default=b"default")
        
        assert result == b"default"
    
    def test_secret_exists_true(self, provider, mock_secret_provider):
        """Test secret_exists returns True for existing secrets."""
        mock_secret_provider.secret_exists.return_value = True
        
        assert provider.secret_exists("api_key") is True
        mock_secret_provider.secret_exists.assert_called_once_with("api_key")
    
    def test_secret_exists_false(self, provider, mock_secret_provider):
        """Test secret_exists returns False for non-existent secrets."""
        mock_secret_provider.secret_exists.return_value = False
        
        assert provider.secret_exists("missing") is False
    
    def test_secret_exists_exception(self, provider, mock_secret_provider):
        """Test secret_exists returns False on exception."""
        mock_secret_provider.secret_exists.side_effect = Exception("Provider error")
        
        assert provider.secret_exists("key") is False
