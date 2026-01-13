# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all vector store drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path
import pytest


from copilot_config import DriverConfig
from copilot_vectorstore.factory import create_vector_store


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
    """Build minimal config with all fields from driver schema.
    
    Includes required fields and optional fields with schema defaults.
    """
    config_dict = {}
    required_fields = get_required_fields(driver_schema)
    
    # Map field names to reasonable defaults (for required fields without schema defaults)
    defaults = {
        "dimension": 384,
        "vector_size": 384,
        "index_type": "flat",
        "host": "localhost",
        "port": 6333,
        "collection_name": "test-collection",
        "endpoint": "https://test.search.windows.net",
        "api_key": "test-key",
        "index_name": "test-index",
        "upsert_batch_size": 100,
    }
    
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


class TestVectorStoreAllDrivers:
    """Test factory creation for all vector store drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "vector_store.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        drivers_dir = schema_dir / "drivers" / "vector_store"
        
        for driver in drivers_enum:
            # Load driver schema
            driver_schema_path = drivers_dir / f"vectorstore_{driver}.json"
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
            

            # Should not raise any exceptions (skip if optional dependencies are missing)
            try:
                store = create_vector_store(driver_name=driver, driver_config=config)
                assert store is not None, f"Failed to create vector store for driver: {driver}"
            except ImportError as e:
                pytest.skip(f"Optional dependencies for {driver} not installed: {str(e)}")


            except Exception as e:
                # Skip on connection errors or other runtime errors (e.g., service not running)
                error_str = str(e).lower()
                if any(x in error_str for x in ["connection", "refused", "connect", "timeout"]):
                    pytest.skip(f"Cannot connect to {driver} service: {type(e).__name__}")
                raise  # Re-raise other exceptions

