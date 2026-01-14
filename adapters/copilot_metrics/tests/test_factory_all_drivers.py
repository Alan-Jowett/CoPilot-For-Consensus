# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all metrics drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

from copilot_metrics.factory import create_metrics_collector
from copilot_config.generated.adapters.metrics import (
    AdapterConfig_Metrics,
    DriverConfig_Metrics_AzureMonitor,
    DriverConfig_Metrics_Noop,
    DriverConfig_Metrics_Prometheus,
    DriverConfig_Metrics_Pushgateway,
)


def get_schema_dir():
    """Get path to schemas directory."""
    return Path(__file__).parent.parent.parent.parent / "docs" / "schemas" / "configs" / "adapters"


def load_json(path):
    """Load JSON file."""
    with open(path) as f:
        return json.load(f)


def get_minimal_typed_driver_config(driver: str):
    """Build a minimal typed driver config for the requested metrics driver."""
    if driver == "noop":
        return DriverConfig_Metrics_Noop()

    if driver == "prometheus":
        return DriverConfig_Metrics_Prometheus()

    if driver == "pushgateway":
        return DriverConfig_Metrics_Pushgateway(
            gateway="http://localhost:9091",
            job="copilot",
        )

    if driver == "azure_monitor":
        return DriverConfig_Metrics_AzureMonitor(
            connection_string="InstrumentationKey=00000000-0000-4000-8000-000000000000",
        )

    raise AssertionError(f"Unhandled driver: {driver}")


class TestMetricsAllDrivers:
    """Test factory creation for all metrics drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "metrics.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        
        for driver in drivers_enum:
            driver_config = get_minimal_typed_driver_config(driver)
            config = AdapterConfig_Metrics(metrics_type=driver, driver=driver_config)
            
            # Try to create driver; skip if optional dependencies are missing
            try:
                collector = create_metrics_collector(config)
                assert collector is not None, f"Failed to create metrics collector for driver: {driver}"
            except ImportError as e:
                # Skip drivers with missing optional dependencies (e.g., prometheus_client)
                if "required for" in str(e):
                    print(f"Skipping {driver}: {e}")
                    continue
                raise
