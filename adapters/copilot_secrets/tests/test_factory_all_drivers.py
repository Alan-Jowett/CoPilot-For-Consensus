# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all secret provider drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

from copilot_config import DriverConfig
from copilot_secrets.factory import create_secret_provider


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


def get_minimal_config(driver_schema):
    """Build minimal config with required and optional fields from driver schema."""
    config_dict = {}
    required_fields = get_required_fields(driver_schema)
    
    # Map field names to reasonable defaults
    defaults = {
        "base_path": "/tmp/secrets",
        "vault_url": "https://test.vault.azure.net/",
        "vault_name": "testvault",
    }
    
    # Add all fields (required and optional) from schema
    if "properties" in driver_schema:
        for field, field_schema in driver_schema["properties"].items():
            if field in defaults:
                config_dict[field] = defaults[field]
            elif isinstance(field_schema, dict) and "default" in field_schema:
                config_dict[field] = field_schema["default"]
            elif field in required_fields:
                config_dict[field] = ""
    
    return config_dict


class TestSecretProviderAllDrivers:
    """Test factory creation for all secret provider drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "secret_provider.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        drivers_dir = schema_dir / "drivers" / "secret_provider"
        
        for driver in drivers_enum:
            # Load driver schema
            driver_schema_path = drivers_dir / f"secret_{driver}.json"
            assert driver_schema_path.exists(), f"Driver schema missing: {driver_schema_path}"
            
            driver_schema = load_json(driver_schema_path)
            config_dict = get_minimal_config(driver_schema)
            
            # Get all allowed keys from schema
            allowed_keys = set(driver_schema.get("properties", {}).keys())
            
            config = DriverConfig(
                driver_name=driver,
                config=config_dict,
                allowed_keys=allowed_keys
            )
            
            # Should not raise any exceptions
            provider = create_secret_provider(driver_name=driver, driver_config=config)
            assert provider is not None, f"Failed to create secret provider for driver: {driver}"
