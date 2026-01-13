# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all metrics drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

from copilot_config import DriverConfig
from copilot_metrics.factory import create_metrics_collector


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
    """Build minimal config with required fields from driver schema."""
    config_dict = {}
    required_fields = get_required_fields(driver_schema)
    
    # Map field names to reasonable defaults
    defaults = {
        "host": "localhost",
        "port": 9090,
        "namespace": "copilot",
        "raise_on_error": False,
        "pushgateway_url": "http://localhost:9091",
        "instrumentation_key": "test-key",
        "service_name": "copilot",
    }
    
    for field in required_fields:
        if field in defaults:
            config_dict[field] = defaults[field]
        else:
            config_dict[field] = ""
    
    return config_dict


class TestMetricsAllDrivers:
    """Test factory creation for all metrics drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "metrics.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        drivers_dir = schema_dir / "drivers" / "metrics"
        
        for driver in drivers_enum:
            # Load driver schema
            driver_schema_path = drivers_dir / f"metrics_{driver}.json"
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
            
            # Try to create driver; skip if optional dependencies are missing
            try:
                collector = create_metrics_collector(driver_name=driver, driver_config=config)
                assert collector is not None, f"Failed to create metrics collector for driver: {driver}"
            except ImportError as e:
                # Skip drivers with missing optional dependencies (e.g., prometheus_client)
                if "required for" in str(e):
                    print(f"Skipping {driver}: {e}")
                    continue
                raise
