# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all message bus drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

from copilot_config.generated.adapters.message_bus import (
    AdapterConfig_MessageBus,
    DriverConfig_MessageBus_AzureServiceBus,
    DriverConfig_MessageBus_Noop,
    DriverConfig_MessageBus_Rabbitmq,
)
from copilot_message_bus.factory import create_publisher


def get_schema_dir():
    """Get path to schemas directory."""
    return Path(__file__).parent.parent.parent.parent / "docs" / "schemas" / "configs" / "adapters"


def load_json(path):
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def get_typed_config(driver_name: str) -> AdapterConfig_MessageBus:
    """Create a minimal typed config for the given driver name."""
    if driver_name == "rabbitmq":
        # Provide username/password so driver instantiation succeeds.
        return AdapterConfig_MessageBus(
            message_bus_type="rabbitmq",
            driver=DriverConfig_MessageBus_Rabbitmq(
                rabbitmq_host="localhost",
                rabbitmq_port=5672,
                rabbitmq_username="guest",
                rabbitmq_password="guest",
            ),
        )

    if driver_name == "azure_service_bus":
        # Provide a connection string so driver instantiation succeeds.
        return AdapterConfig_MessageBus(
            message_bus_type="azure_service_bus",
            driver=DriverConfig_MessageBus_AzureServiceBus(
                connection_string="Endpoint=sb://test.servicebus.windows.net/;SharedAccessKeyName=test;SharedAccessKey=test",
                queue_name="test-queue",
            ),
        )

    if driver_name == "noop":
        return AdapterConfig_MessageBus(
            message_bus_type="noop",
            driver=DriverConfig_MessageBus_Noop(),
        )

    raise ValueError(f"Unknown driver_name: {driver_name}")


class TestMessageBusAllDrivers:
    """Test factory creation for all message bus drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "message_bus.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        
        for driver in drivers_enum:
            config = get_typed_config(driver)
            
            # Should not raise any exceptions
            # Note: validation may fail for actual connections, so use enable_validation=False
            publisher = create_publisher(
                config,
                enable_validation=False
            )
            assert publisher is not None, f"Failed to create publisher for driver: {driver}"
