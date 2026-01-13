# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all message bus drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

from copilot_config import DriverConfig
from copilot_message_bus.factory import create_publisher


def get_schema_dir():
    """Get path to schemas directory."""
    return Path(__file__).parent.parent.parent.parent / "docs" / "schemas" / "configs" / "adapters"


def load_json(path):
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def get_required_fields(driver_schema):
    """Extract required fields from driver schema."""
    required = set()
    
    if "required" in driver_schema:
        required.update(driver_schema["required"])
    
    if "properties" in driver_schema:
        for field, field_schema in driver_schema["properties"].items():
            if isinstance(field_schema, dict) and field_schema.get("required") is True:
                required.add(field)
    
    return required


def get_minimal_config(driver_schema, driver_name=None):
    """Build minimal config with all fields from driver schema.
    
    Includes required fields and optional fields with schema defaults.
    """
    config_dict = {}
    required_fields = get_required_fields(driver_schema)
    
    # Map field names to reasonable defaults (for required fields without schema defaults)
    defaults = {
        "rabbitmq_host": "localhost",
        "rabbitmq_port": 5672,
        "rabbitmq_username": "guest",
        "rabbitmq_password": "guest",
        "connection_string": "Endpoint=sb://test.servicebus.windows.net/;",
        "enable_validation": True,
    }
    
    # For RabbitMQ, username and password are required by the driver even though schema marks them optional
    if driver_name == "rabbitmq":
        required_fields.update(["rabbitmq_username", "rabbitmq_password"])
    
    # For Azure Service Bus, connection_string is needed by the driver even though schema marks it optional
    if driver_name == "azure_service_bus":
        required_fields.add("connection_string")
    
    # Include all properties: required fields and optional fields with defaults
    properties = driver_schema.get("properties", {})
    for field, field_schema in properties.items():
        if field in required_fields:
            # Required field: use defaults or empty string
            if field in defaults:
                config_dict[field] = defaults[field]
            else:
                config_dict[field] = ""
        elif "default" in field_schema:
            # Optional field with default: use the schema default
            config_dict[field] = field_schema["default"]
        # Optional fields without defaults are skipped (will use None)
    
    return config_dict


class TestMessageBusAllDrivers:
    """Test factory creation for all message bus drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "message_bus.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        drivers_dir = schema_dir / "drivers" / "message_bus"
        
        for driver in drivers_enum:
            # Load driver schema
            driver_schema_path = drivers_dir / f"{driver}.json"
            assert driver_schema_path.exists(), f"Driver schema missing: {driver_schema_path}"
            
            driver_schema = load_json(driver_schema_path)
            config_dict = get_minimal_config(driver_schema, driver_name=driver)
            
            # Get all allowed keys from schema
            allowed_keys = set(driver_schema.get("properties", {}).keys())
            
            config = DriverConfig(
                driver_name=driver,
                config=config_dict,
                allowed_keys=allowed_keys,
            )
            
            # Should not raise any exceptions
            # Note: validation may fail for actual connections, so use enable_validation=False
            publisher = create_publisher(
                driver_name=driver,
                driver_config=config,
                enable_validation=False
            )
            assert publisher is not None, f"Failed to create publisher for driver: {driver}"
