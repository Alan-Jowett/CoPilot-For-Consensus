# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Comprehensive factory tests for all embedding backend drivers.

This test module validates that each driver listed in the schema can be
instantiated via the factory with its required parameters.
"""

import json
from pathlib import Path

import pytest

from copilot_config.generated.adapters.embedding_backend import (
    AdapterConfig_EmbeddingBackend,
    DriverConfig_EmbeddingBackend_AzureOpenai,
    DriverConfig_EmbeddingBackend_Huggingface,
    DriverConfig_EmbeddingBackend_Mock,
    DriverConfig_EmbeddingBackend_Openai,
    DriverConfig_EmbeddingBackend_Sentencetransformers,
)
from copilot_embedding.factory import create_embedding_provider


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
        "dimension": 384,
        "model_name": "sentence-transformers/all-MiniLM-L6-v2",
        "model": "text-embedding-ada-002",
        "device": "cpu",
        "api_key": "test-key",
        "api_base": "https://api.openai.com/v1",
        "api_version": "2023-05-15",
        "deployment_name": "test-deployment",
        "cache_dir": None,
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


class TestEmbeddingBackendAllDrivers:
    """Test factory creation for all embedding backend drivers."""
    
    def test_all_drivers_instantiate(self):
        """Test that each driver in schema can be instantiated via factory."""
        schema_dir = get_schema_dir()
        schema = load_json(schema_dir / "embedding_backend.json")
        drivers_enum = schema["properties"]["discriminant"]["enum"]
        drivers_dir = schema_dir / "drivers" / "embedding_backend"
        
        for driver in drivers_enum:
            # Load driver schema
            driver_schema_path = drivers_dir / f"embedding_{driver}.json"
            assert driver_schema_path.exists(), f"Driver schema missing: {driver_schema_path}"
            
            driver_schema = load_json(driver_schema_path)
            config_dict = get_minimal_config(driver_schema)

            if driver == "mock":
                config = DriverConfig_EmbeddingBackend_Mock(**config_dict)
            elif driver == "sentencetransformers":
                config = DriverConfig_EmbeddingBackend_Sentencetransformers(**config_dict)
            elif driver == "openai":
                config = DriverConfig_EmbeddingBackend_Openai(**config_dict)
            elif driver == "azure_openai":
                config = DriverConfig_EmbeddingBackend_AzureOpenai(**config_dict)
            elif driver == "huggingface":
                config = DriverConfig_EmbeddingBackend_Huggingface(**config_dict)
            else:
                raise AssertionError(f"Unexpected driver in schema: {driver}")
            
            adapter_config = AdapterConfig_EmbeddingBackend(
                embedding_backend_type=driver,
                driver=config,
            )

            # Should not raise any exceptions (skip if optional dependencies are missing)
            try:
                provider = create_embedding_provider(adapter_config)
                assert provider is not None, f"Failed to create provider for driver: {driver}"
            except ImportError as e:
                pytest.skip(f"Optional dependencies for {driver} not installed: {str(e)}")

