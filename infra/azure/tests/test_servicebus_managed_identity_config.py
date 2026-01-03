# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus managed identity configuration in Container Apps."""

import os
import sys
from pathlib import Path

import pytest

# Add the copilot_events module to path for direct import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "adapters" / "copilot_events"))

from copilot_events.azure_config import get_azure_servicebus_kwargs

# Minimum number of parts in a valid FQDN (namespace.servicebus.windows.net)
MIN_FQDN_PARTS = 4


class TestServiceBusManagedIdentityConfiguration:
    """Test that Container Apps environment variables work with get_azure_servicebus_kwargs."""

    def test_container_apps_managed_identity_configuration(self, monkeypatch):
        """Test that the Container Apps configuration with managed identity works correctly.
        
        This simulates the environment variables that will be set in Azure Container Apps
        after the infrastructure changes are deployed.
        """
        # Simulate Container Apps environment variables after our Bicep changes
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.setenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", "myservicebus-sb-dev-abc123.servicebus.windows.net")
        
        # Call the function that will be used by services
        result = get_azure_servicebus_kwargs()
        
        # Verify the configuration is correct for managed identity
        assert result == {
            "fully_qualified_namespace": "myservicebus-sb-dev-abc123.servicebus.windows.net",
            "use_managed_identity": True,
        }

    def test_container_apps_all_services_configuration(self, monkeypatch):
        """Test configuration for all services that use Azure Service Bus.
        
        This verifies that all services (reporting, ingestion, parsing, chunking, 
        embedding, orchestrator, summarization) will work with the same configuration.
        """
        services = [
            'reporting',
            'ingestion', 
            'parsing',
            'chunking',
            'embedding',
            'orchestrator',
            'summarization',
        ]
        
        # Simulate the configuration that will be set for all services
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.setenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", "test-sb-env-xyz.servicebus.windows.net")
        
        for service in services:
            # Each service calls get_azure_servicebus_kwargs()
            result = get_azure_servicebus_kwargs()
            
            # All services should get the same managed identity configuration
            assert result["use_managed_identity"] is True
            assert result["fully_qualified_namespace"] == "test-sb-env-xyz.servicebus.windows.net"
            assert "connection_string" not in result

    def test_fqdn_format_validation(self, monkeypatch):
        """Test that the FQDN format matches Azure Service Bus requirements."""
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.setenv("MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE", "mynamespace.servicebus.windows.net")
        
        result = get_azure_servicebus_kwargs()
        
        # Verify FQDN format
        fqdn = result["fully_qualified_namespace"]
        assert fqdn.endswith(".servicebus.windows.net")
        assert len(fqdn.split(".")) >= MIN_FQDN_PARTS  # namespace.servicebus.windows.net
        
    def test_backward_compatibility_with_connection_string(self, monkeypatch):
        """Test that connection string mode still works for local development.
        
        This ensures that existing local development setups using connection strings
        are not broken by the managed identity changes.
        """
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false")
        monkeypatch.setenv("MESSAGE_BUS_CONNECTION_STRING", "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=RootManageSharedAccessKey;SharedAccessKey=test123")
        
        result = get_azure_servicebus_kwargs()
        
        # Connection string mode should still work
        assert "connection_string" in result
        assert "use_managed_identity" not in result
        assert result["connection_string"].startswith("Endpoint=sb://")
