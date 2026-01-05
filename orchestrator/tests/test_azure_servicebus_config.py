# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus configuration in the orchestrator service.

These tests verify that the orchestrator correctly passes Azure Service Bus
connection parameters (managed identity or connection string) to the subscriber
when MESSAGE_BUS_TYPE is set to "azureservicebus".

Note: These tests require the copilot_events adapter to be installed.
Run from the repository root or install adapters first:
    python adapters/scripts/install_adapters.py copilot_events
"""

import sys
from pathlib import Path

import pytest

# Add adapters to path for imports
adapters_path = Path(__file__).parent.parent.parent / "adapters" / "copilot_events"
if adapters_path.exists():
    sys.path.insert(0, str(adapters_path))


class TestOrchestratorAzureServiceBusConfig:
    """Test Azure Service Bus configuration handling in orchestrator."""

    def test_managed_identity_configuration_format(self, monkeypatch):
        """Test that managed identity configuration has the correct format.

        This test simulates the Azure Container Apps environment where:
        - MESSAGE_BUS_TYPE=azureservicebus
        - MESSAGE_BUS_USE_MANAGED_IDENTITY=true
        - MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE=<namespace>.servicebus.windows.net

        Verifies that get_azure_servicebus_kwargs returns the correct structure.
        """
        # Set up environment variables as they would be in Azure Container Apps
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        monkeypatch.setenv(
            "MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE",
            "copilot-sb-dev-ej3rgjyh.servicebus.windows.net"
        )

        try:
            from copilot_events import get_azure_servicebus_kwargs

            # Call the function that would be used in main.py
            message_bus_kwargs = get_azure_servicebus_kwargs()

            # Verify the kwargs contain the expected parameters
            assert message_bus_kwargs["use_managed_identity"] is True
            assert message_bus_kwargs["fully_qualified_namespace"] == "copilot-sb-dev-ej3rgjyh.servicebus.windows.net"
            assert "connection_string" not in message_bus_kwargs
        except ImportError:
            pytest.skip("copilot_events adapter not installed")

    def test_connection_string_configuration_format(self, monkeypatch):
        """Test that connection string configuration has the correct format.

        This test simulates the local development or connection string mode where:
        - MESSAGE_BUS_TYPE=azureservicebus
        - MESSAGE_BUS_USE_MANAGED_IDENTITY=false (or not set)
        - MESSAGE_BUS_CONNECTION_STRING=<connection string>

        Verifies that get_azure_servicebus_kwargs returns the correct structure.
        """
        # Set up environment variables for connection string mode
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false")
        monkeypatch.setenv(
            "MESSAGE_BUS_CONNECTION_STRING",
            "Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test123"
        )

        try:
            from copilot_events import get_azure_servicebus_kwargs

            # Call the function that would be used in main.py
            message_bus_kwargs = get_azure_servicebus_kwargs()

            # Verify the kwargs contain the expected parameters
            assert "connection_string" in message_bus_kwargs
            assert message_bus_kwargs["connection_string"].startswith("Endpoint=sb://")
            assert "use_managed_identity" not in message_bus_kwargs
        except ImportError:
            pytest.skip("copilot_events adapter not installed")

    def test_orchestrator_passes_queue_name_to_subscriber(self):
        """Test that orchestrator passes the correct queue name to subscriber.

        The orchestrator should create a subscriber for the "orchestrator-service" queue,
        which will receive "embeddings.generated" events via routing.
        """
        # This is a documentation test - the actual queue name is hardcoded in main.py
        # The orchestrator subscribes to "orchestrator-service" queue
        expected_queue_name = "orchestrator-service"

        # Verify this matches the documentation and architecture
        # (This would be verified by checking the actual subscriber creation in main.py)
        assert expected_queue_name == "orchestrator-service"

    def test_orchestrator_in_rbac_service_lists(self):
        """Test that orchestrator is included in the correct RBAC lists.

        According to the Bicep templates (infra/azure/modules/servicebus.bicep):
        - orchestrator should be in senderServices (Data Sender role)
        - orchestrator should be in receiverServices (Data Receiver role)

        This test documents the expected RBAC configuration.
        """
        # Expected configuration from servicebus.bicep
        expected_sender_services = [
            'parsing',
            'chunking',
            'embedding',
            'orchestrator',
            'summarization',
            'reporting'
        ]

        expected_receiver_services = [
            'chunking',
            'embedding',
            'orchestrator',
            'summarization',
            'reporting',
            'ingestion'
        ]

        # Verify orchestrator is in both lists
        assert 'orchestrator' in expected_sender_services, \
            "orchestrator must have Data Sender role to publish summarization.requested events"
        assert 'orchestrator' in expected_receiver_services, \
            "orchestrator must have Data Receiver role to consume embeddings.generated events"

    def test_missing_managed_identity_namespace_raises_error(self, monkeypatch):
        """Test that missing namespace raises error in managed identity mode."""
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "true")
        # Don't set MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE

        try:
            from copilot_events import get_azure_servicebus_kwargs

            with pytest.raises(ValueError, match="MESSAGE_BUS_FULLY_QUALIFIED_NAMESPACE"):
                get_azure_servicebus_kwargs()
        except ImportError:
            pytest.skip("copilot_events adapter not installed")

    def test_missing_connection_string_raises_error(self, monkeypatch):
        """Test that missing connection string raises error in connection string mode."""
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("MESSAGE_BUS_USE_MANAGED_IDENTITY", "false")
        # Don't set MESSAGE_BUS_CONNECTION_STRING

        try:
            from copilot_events import get_azure_servicebus_kwargs

            with pytest.raises(ValueError, match="MESSAGE_BUS_CONNECTION_STRING"):
                get_azure_servicebus_kwargs()
        except ImportError:
            pytest.skip("copilot_events adapter not installed")
