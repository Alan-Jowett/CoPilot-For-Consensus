# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for Azure Service Bus configuration in the orchestrator service.

These tests verify that the orchestrator correctly passes Azure Service Bus
connection parameters (managed identity or connection string) to the subscriber
when MESSAGE_BUS_TYPE is set to "azureservicebus".

## Infrastructure Configuration Notes

The orchestrator service requires specific Azure Service Bus RBAC roles:
- **Azure Service Bus Data Sender** - to publish summarization.requested events
- **Azure Service Bus Data Receiver** - to consume embeddings.generated events

The orchestrator subscribes to the "orchestrator-service" queue, which receives
"embeddings.generated" events via routing. This queue is created dynamically by
the orchestrator service on startup.

For Bicep infrastructure configuration, see:
- infra/azure/modules/servicebus.bicep (role assignments)
- infra/azure/main.bicep (sender/receiver service lists)

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


class TestOrchestratorQueueNameConfiguration:
    """Test queue name auto-detection for different message bus types."""

    def test_queue_name_defaults_to_embeddings_generated_for_azure_servicebus(self, monkeypatch):
        """Test that queue_name defaults to 'embeddings.generated' for Azure Service Bus.

        When MESSAGE_BUS_TYPE is azureservicebus and ORCHESTRATOR_QUEUE_NAME is not set,
        the orchestrator should subscribe to 'embeddings.generated' queue.
        """
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("APP_VERSION", "0.1.0")
        # Ensure ORCHESTRATOR_QUEUE_NAME is not set
        monkeypatch.delenv("ORCHESTRATOR_QUEUE_NAME", raising=False)

        from copilot_config import load_typed_config

        config = load_typed_config("orchestrator")

        # queue_name should be None or not set when not explicitly configured
        queue_name = getattr(config, "queue_name", None)
        
        # Simulate the auto-detection logic from main.py
        if not queue_name:
            if config.message_bus_type == "azureservicebus":
                queue_name = "embeddings.generated"
            else:
                queue_name = "orchestrator-service"

        assert queue_name == "embeddings.generated"

    def test_queue_name_defaults_to_orchestrator_service_for_rabbitmq(self, monkeypatch):
        """Test that queue_name defaults to 'orchestrator-service' for RabbitMQ.

        When MESSAGE_BUS_TYPE is rabbitmq and ORCHESTRATOR_QUEUE_NAME is not set,
        the orchestrator should subscribe to 'orchestrator-service' queue.
        """
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "rabbitmq")
        monkeypatch.setenv("APP_VERSION", "0.1.0")
        # Ensure ORCHESTRATOR_QUEUE_NAME is not set
        monkeypatch.delenv("ORCHESTRATOR_QUEUE_NAME", raising=False)

        from copilot_config import load_typed_config

        config = load_typed_config("orchestrator")

        # queue_name should be None or not set when not explicitly configured
        queue_name = getattr(config, "queue_name", None)
        
        # Simulate the auto-detection logic from main.py
        if not queue_name:
            if config.message_bus_type == "azureservicebus":
                queue_name = "embeddings.generated"
            else:
                queue_name = "orchestrator-service"

        assert queue_name == "orchestrator-service"

    def test_queue_name_uses_explicit_configuration(self, monkeypatch):
        """Test that explicitly configured ORCHESTRATOR_QUEUE_NAME is respected.

        When ORCHESTRATOR_QUEUE_NAME is set to a custom value, it should be used
        regardless of MESSAGE_BUS_TYPE.
        """
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "azureservicebus")
        monkeypatch.setenv("APP_VERSION", "0.1.0")
        monkeypatch.setenv("ORCHESTRATOR_QUEUE_NAME", "custom-queue-name")

        from copilot_config import load_typed_config

        config = load_typed_config("orchestrator")

        # queue_name should be set to the explicitly configured value
        queue_name = getattr(config, "queue_name", None)
        
        # Simulate the auto-detection logic from main.py
        if not queue_name:
            if config.message_bus_type == "azureservicebus":
                queue_name = "embeddings.generated"
            else:
                queue_name = "orchestrator-service"

        assert queue_name == "custom-queue-name"
