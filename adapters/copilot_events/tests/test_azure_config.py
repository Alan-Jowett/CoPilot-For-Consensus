# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus configuration helper utilities."""

import os
import sys
from pathlib import Path

import pytest

# Add the copilot_events module to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent))

from copilot_events.azure_config import get_azure_servicebus_kwargs


class TestGetAzureServiceBusKwargs:
    """Test get_azure_servicebus_kwargs function."""

    def test_managed_identity_mode(self, monkeypatch):
        """Test configuration extraction for managed identity mode."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.setenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", "mynamespace.servicebus.windows.net")

        result = get_azure_servicebus_kwargs()

        assert result == {
            "fully_qualified_namespace": "mynamespace.servicebus.windows.net",
            "use_managed_identity": True,
        }

    def test_managed_identity_mode_case_insensitive(self, monkeypatch):
        """Test that managed identity flag is case-insensitive."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "TRUE")
        monkeypatch.setenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", "mynamespace.servicebus.windows.net")

        result = get_azure_servicebus_kwargs()

        assert result["use_managed_identity"] is True

    def test_managed_identity_mode_missing_namespace(self, monkeypatch):
        """Test that missing namespace raises ValueError in managed identity mode."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.delenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", raising=False)

        with pytest.raises(ValueError, match="MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE"):
            get_azure_servicebus_kwargs()

    def test_connection_string_mode(self, monkeypatch):
        """Test configuration extraction for connection string mode."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false")
        monkeypatch.setenv("MESSAGE_BUS_CONNECTION_STRING", "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123")

        result = get_azure_servicebus_kwargs()

        assert result == {
            "connection_string": "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123",
        }

    def test_connection_string_mode_default(self, monkeypatch):
        """Test that connection string mode is used by default when USE_MANAGED_IDENTITY is not set."""
        monkeypatch.delenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", raising=False)
        monkeypatch.setenv("MESSAGE_BUS_CONNECTION_STRING", "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123")

        result = get_azure_servicebus_kwargs()

        assert "connection_string" in result
        assert "use_managed_identity" not in result

    def test_connection_string_mode_missing_connection_string(self, monkeypatch):
        """Test that missing connection string raises ValueError in connection string mode."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false")
        monkeypatch.delenv("MESSAGE_BUS_CONNECTION_STRING", raising=False)

        with pytest.raises(ValueError, match="MESSAGE_BUS_CONNECTION_STRING"):
            get_azure_servicebus_kwargs()

    def test_managed_identity_false_variants(self, monkeypatch):
        """Test various false values for managed identity flag."""
        monkeypatch.setenv("MESSAGE_BUS_CONNECTION_STRING", "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123")

        for false_value in ["false", "False", "FALSE", "0", "no", "NO"]:
            monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", false_value)
            result = get_azure_servicebus_kwargs()
            assert "connection_string" in result
            assert result["connection_string"] == "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123"
