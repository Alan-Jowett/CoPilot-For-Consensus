# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for registry-based configuration provider."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests
from copilot_config.registry_provider import ConfigWatcher, RegistryConfigProvider


class TestRegistryConfigProvider:
    """Tests for RegistryConfigProvider."""

    @patch("copilot_config.registry_provider.requests.get")
    def test_get_config(self, mock_get):
        """Test getting configuration from registry."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"db_host": "localhost", "db_port": 5432}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000", service_name="test-service", environment="dev"
        )

        # Get config values
        assert provider.get("db_host") == "localhost"
        assert provider.get_int("db_port") == 5432
        assert provider.get("nonexistent", "default") == "default"

    @patch("copilot_config.registry_provider.requests.get")
    def test_cache_ttl(self, mock_get):
        """Test that cache respects TTL."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": "initial"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000",
            service_name="test-service",
            cache_ttl_seconds=1,
        )

        # First access - should fetch
        assert provider.get("value") == "initial"
        assert mock_get.call_count == 1

        # Second access within TTL - should use cache
        assert provider.get("value") == "initial"
        assert mock_get.call_count == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Update mock to return new value
        mock_response.json.return_value = {"value": "updated"}

        # Access after TTL - should fetch again
        assert provider.get("value") == "updated"
        assert mock_get.call_count == 2

    @patch("copilot_config.registry_provider.requests.get")
    def test_refresh(self, mock_get):
        """Test manual cache refresh."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": "initial"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000",
            service_name="test-service",
            cache_ttl_seconds=3600,  # Long TTL
        )

        # First access
        assert provider.get("value") == "initial"
        assert mock_get.call_count == 1

        # Update mock
        mock_response.json.return_value = {"value": "updated"}

        # Manual refresh
        provider.refresh()
        assert provider.get("value") == "updated"
        assert mock_get.call_count == 2

    @patch("copilot_config.registry_provider.requests.get")
    def test_error_handling(self, mock_get):
        """Test graceful error handling."""
        mock_get.side_effect = requests.RequestException("Network error")

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000", service_name="test-service"
        )

        # Should return default on error
        assert provider.get("key", "default") == "default"
        assert provider.get_int("port", 5432) == 5432
        assert provider.get_bool("debug", False) is False

    @patch("copilot_config.registry_provider.requests.get")
    def test_type_conversions(self, mock_get):
        """Test type conversion methods."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "str_value": "hello",
            "int_value": 42,
            "float_value": 3.14,
            "bool_true": True,
            "bool_false": False,
            "bool_string_true": "true",
            "bool_string_false": "false",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000", service_name="test-service"
        )

        # String
        assert provider.get("str_value") == "hello"

        # Int
        assert provider.get_int("int_value") == 42
        assert isinstance(provider.get_int("int_value"), int)

        # Float
        assert provider.get_float("float_value") == 3.14
        assert isinstance(provider.get_float("float_value"), float)

        # Bool
        assert provider.get_bool("bool_true") is True
        assert provider.get_bool("bool_false") is False
        assert provider.get_bool("bool_string_true") is True
        assert provider.get_bool("bool_string_false") is False

    @patch("copilot_config.registry_provider.requests.get")
    def test_environment_parameter(self, mock_get):
        """Test that environment parameter is passed correctly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"key": "value"}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = RegistryConfigProvider(
            registry_url="http://registry:8000", service_name="test-service", environment="prod"
        )

        provider.get("key")

        # Verify request was made with correct params
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["environment"] == "prod"


class TestConfigWatcher:
    """Tests for ConfigWatcher."""

    @patch("copilot_config.registry_provider.requests.get")
    def test_detect_changes(self, mock_get):
        """Test that watcher detects configuration changes."""
        # Initial response
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"version": 1, "config_data": {"key": "value1"}}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        callback_called = []

        def on_change(config):
            callback_called.append(config)

        watcher = ConfigWatcher(
            registry_url="http://registry:8000",
            service_name="test-service",
            environment="dev",
            poll_interval_seconds=1,
            on_change=on_change,
        )

        # Initial check
        watcher._check_for_changes()
        assert len(callback_called) == 0  # No callback on first check

        # Simulate version change
        mock_response.json.return_value = [
            {"version": 2, "config_data": {"key": "value2"}}
        ]

        # Second check
        watcher._check_for_changes()
        assert len(callback_called) == 1
        assert callback_called[0] == {"key": "value2"}

    @patch("copilot_config.registry_provider.requests.get")
    def test_no_callback_on_same_version(self, mock_get):
        """Test that callback is not called for same version."""
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"version": 1, "config_data": {"key": "value"}}
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        callback_called = []

        def on_change(config):
            callback_called.append(config)

        watcher = ConfigWatcher(
            registry_url="http://registry:8000",
            service_name="test-service",
            on_change=on_change,
        )

        # Multiple checks with same version
        watcher._check_for_changes()
        watcher._check_for_changes()
        watcher._check_for_changes()

        # Callback should not be called
        assert len(callback_called) == 0

    @patch("copilot_config.registry_provider.requests.get")
    def test_error_handling(self, mock_get):
        """Test watcher handles errors gracefully."""
        mock_get.side_effect = requests.RequestException("Network error")

        watcher = ConfigWatcher(
            registry_url="http://registry:8000",
            service_name="test-service",
            on_change=lambda cfg: None,
        )

        # Should not raise exception
        watcher._check_for_changes()
