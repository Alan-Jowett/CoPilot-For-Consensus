# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for service configuration loading."""

import json
import os
from pathlib import Path

import pytest
from copilot_config import AdapterConfig, DriverConfig, ServiceConfig, load_service_config



class TestServiceConfig:
    """Tests for ServiceConfig model."""

    def test_service_config_creation(self):
        """Test creating a ServiceConfig instance."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})
        adapter_config = AdapterConfig(
            adapter_type="llm_backend",
            driver_name="openai",
            driver_config=driver_config
        )

        config = ServiceConfig(
            service_name="summarization",
            service_settings={"max_tokens": 500},
            adapters=[adapter_config],
            schema_version="1.0.0",
            min_service_version="1.0.0"
        )

        assert config.service_name == "summarization"
        assert config.service_settings["max_tokens"] == 500
        assert len(config.adapters) == 1
        assert config.adapters[0].adapter_type == "llm_backend"

    def test_get_adapter(self):
        """Test getting adapter by name."""
        driver_config = DriverConfig(driver_name="openai", config={})
        adapter_config = AdapterConfig(
            adapter_type="llm_backend",
            driver_name="openai",
            driver_config=driver_config
        )

        config = ServiceConfig(
            service_name="summarization",
            service_settings={},
            adapters=[adapter_config],
            schema_version="1.0.0"
        )

        llm_adapter = config.get_adapter("llm_backend")
        assert llm_adapter is not None
        assert llm_adapter.driver_name == "openai"

    def test_get_adapter_not_found(self):
        """Test getting non-existent adapter returns None."""
        config = ServiceConfig(
            service_name="summarization",
            service_settings={},
            adapters=[],
            schema_version="1.0.0"
        )

        result = config.get_adapter("nonexistent")
        assert result is None

    def test_get_service_setting(self):
        """Test getting service setting."""
        config = ServiceConfig(
            service_name="summarization",
            service_settings={"max_tokens": 500, "temperature": 0.7},
            adapters=[],
            schema_version="1.0.0"
        )

        assert config.get_service_setting("max_tokens") == 500
        assert config.get_service_setting("temperature") == 0.7

    def test_get_service_setting_not_found(self):
        """Test getting non-existent service setting returns None."""
        config = ServiceConfig(
            service_name="summarization",
            service_settings={},
            adapters=[],
            schema_version="1.0.0"
        )

        result = config.get_service_setting("nonexistent")
        assert result is None

    def test_get_service_setting_with_default(self):
        """Test getting service setting with default value."""
        config = ServiceConfig(
            service_name="summarization",
            service_settings={"max_tokens": 500},
            adapters=[],
            schema_version="1.0.0"
        )

        result = config.get_service_setting("temperature", default=0.7)
        assert result == 0.7


class TestAdapterConfig:
    """Tests for AdapterConfig model."""

    def test_adapter_config_creation(self):
        """Test creating an AdapterConfig instance."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})

        adapter_config = AdapterConfig(
            adapter_type="llm_backend",
            driver_name="openai",
            driver_config=driver_config
        )

        assert adapter_config.adapter_type == "llm_backend"
        assert adapter_config.driver_name == "openai"
        assert adapter_config.driver_config.driver_name == "openai"

    def test_adapter_config_attribute_delegation(self):
        """Test that AdapterConfig delegates attribute access to driver_config."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})
        adapter_config = AdapterConfig(
            adapter_type="llm_backend",
            driver_name="openai",
            driver_config=driver_config
        )

        # Should be able to access driver config attributes via adapter
        assert adapter_config.api_key == "secret"


class TestDriverConfig:
    """Tests for DriverConfig model."""

    def test_driver_config_creation(self):
        """Test creating a DriverConfig instance."""
        config_dict = {"api_key": "secret", "model": "gpt-4"}
        driver_config = DriverConfig(driver_name="openai", config=config_dict)

        assert driver_config.driver_name == "openai"
        assert driver_config.config == config_dict

    def test_driver_config_attribute_access(self):
        """Test accessing driver config via attributes."""
        driver_config = DriverConfig(
            driver_name="openai",
            config={"api_key": "secret", "model": "gpt-4"}
        )

        assert driver_config.api_key == "secret"
        assert driver_config.model == "gpt-4"

    def test_driver_config_missing_attribute_raises_attribute_error(self):
        """Accessing an unknown key not in schema raises AttributeError."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})

        with pytest.raises(AttributeError):
            _ = driver_config.nonexistent


class TestLoadServiceConfig:
    """Tests for load_service_config function."""

    def test_load_service_config_basic(self, tmp_path, monkeypatch):
        """Test loading service config from schema."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {
                "max_tokens": {
                    "type": "int",
                    "source": "env",
                    "env_var": "MAX_TOKENS",
                    "default": 500
                }
            },
            "adapters_schema": {}
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Set environment variables
        monkeypatch.setenv("SCHEMA_DIR", str(schema_dir))

        # Load config
        config = load_service_config(
            "test-service",
            schema_dir=str(schema_dir)
        )

        assert isinstance(config, ServiceConfig)
        assert config.service_name == "test-service"
        assert config.schema_version == "1.0.0"
        assert len(config.adapters) == 0

    def test_load_service_config_with_adapters(self, tmp_path, monkeypatch):
        """Test loading service config with adapters."""
        # Create schema directory structure
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        llm_drivers_dir = drivers_dir / "llm_backend"
        llm_drivers_dir.mkdir()

        # Create service schema with adapter reference
        service_schema = {
            "service_name": "summarization",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {
                "llm_backend": {"$ref": "../adapters/llm_backend.json"}
            }
        }

        service_file = services_dir / "summarization.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {
                    "field": "driver_name",
                    "env_var": "LLM_BACKEND"
                },
                "drivers": {
                    "properties": {
                        "openai": {
                            "$ref": "../drivers/llm_backend/llm_openai.json"
                        }
                    }
                }
            }
        }

        adapter_file = adapters_dir / "llm_backend.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "api_key": {
                    "type": "string",
                    "source": "secret",
                    "secret_name": "openai_api_key"
                },
                "model": {
                    "type": "string",
                    "source": "env",
                    "env_var": "OPENAI_MODEL",
                    "default": "gpt-4"
                }
            }
        }

        driver_file = llm_drivers_dir / "llm_openai.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4-turbo")

        # Load config
        config = load_service_config(
            "summarization",
            schema_dir=str(schema_dir)
        )

        assert config.service_name == "summarization"
        assert len(config.adapters) == 1
        assert config.adapters[0].adapter_type == "llm_backend"
        assert config.adapters[0].driver_name == "openai"
        assert config.adapters[0].driver_config.model == "gpt-4-turbo"
