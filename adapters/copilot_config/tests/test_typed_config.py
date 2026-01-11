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

    def test_load_config_with_defaults_no_source(self, tmp_path, monkeypatch):
        """Test that fields with only defaults (no source) are properly loaded.

        This test ensures the bug where fields like 'exchange' and 'exchange_type'
        with only defaults (no source="env" or source="secret") were being ignored
        is properly fixed.
        """
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        message_bus_drivers_dir = drivers_dir / "message_bus"
        message_bus_drivers_dir.mkdir()

        # Create service schema with message_bus adapter
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {
                "message_bus": {"$ref": "../adapters/message_bus.json"}
            }
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {
                    "field": "driver_name",
                    "env_var": "MESSAGE_BUS_TYPE"
                },
                "drivers": {
                    "properties": {
                        "rabbitmq": {
                            "$ref": "../drivers/message_bus/rabbitmq.json"
                        }
                    }
                }
            }
        }

        adapter_file = adapters_dir / "message_bus.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create RabbitMQ driver schema with fields that have defaults but no source
        driver_schema = {
            "properties": {
                "rabbitmq_host": {
                    "type": "string",
                    "source": "env",
                    "env_var": "RABBITMQ_HOST",
                    "default": "localhost"
                },
                "rabbitmq_port": {
                    "type": "integer",
                    "source": "env",
                    "env_var": "RABBITMQ_PORT",
                    "default": 5672
                },
                "exchange": {
                    "type": "string",
                    "default": "copilot.events"
                },
                "exchange_type": {
                    "type": "string",
                    "default": "topic"
                }
            }
        }

        driver_file = message_bus_drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "rabbitmq")
        monkeypatch.setenv("RABBITMQ_HOST", "messagebus")
        monkeypatch.setenv("RABBITMQ_PORT", "5672")

        # Load config
        config = load_service_config(
            "test-service",
            schema_dir=str(schema_dir)
        )

        # Verify adapter loaded
        assert config.service_name == "test-service"
        assert len(config.adapters) == 1
        message_bus_adapter = config.get_adapter("message_bus")
        assert message_bus_adapter is not None
        assert message_bus_adapter.driver_name == "rabbitmq"

        # Verify env-sourced fields are loaded
        assert message_bus_adapter.driver_config.rabbitmq_host == "messagebus"
        assert message_bus_adapter.driver_config.rabbitmq_port == 5672

        # BUG FIX VERIFICATION: Verify fields with only defaults (no source) are loaded
        assert message_bus_adapter.driver_config.exchange == "copilot.events"
        assert message_bus_adapter.driver_config.exchange_type == "topic"

    def test_load_config_integer_type_conversion(self, tmp_path, monkeypatch):
        """Test that environment variables with type 'integer' are properly converted to int.

        This test ensures the bug where schema type 'integer' wasn't recognized
        (only 'int' was checked) is properly fixed.
        """
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        document_store_drivers_dir = drivers_dir / "document_store"
        document_store_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {
                "document_store": {"$ref": "../adapters/document_store.json"}
            }
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {
                    "field": "driver_name",
                    "env_var": "DOCUMENT_STORE_TYPE"
                },
                "drivers": {
                    "properties": {
                        "mongodb": {
                            "$ref": "../drivers/document_store/mongodb.json"
                        }
                    }
                }
            }
        }

        adapter_file = adapters_dir / "document_store.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create MongoDB driver schema with port as "integer" type
        driver_schema = {
            "properties": {
                "host": {
                    "type": "string",
                    "source": "env",
                    "env_var": "MONGODB_HOST",
                    "default": "localhost"
                },
                "port": {
                    "type": "integer",  # Note: "integer" not "int"
                    "source": "env",
                    "env_var": "MONGODB_PORT",
                    "default": 27017
                },
                "database": {
                    "type": "string",
                    "source": "env",
                    "env_var": "MONGODB_DATABASE",
                    "default": "test"
                }
            }
        }

        driver_file = document_store_drivers_dir / "mongodb.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables - port is a string from environment
        monkeypatch.setenv("DOCUMENT_STORE_TYPE", "mongodb")
        monkeypatch.setenv("MONGODB_HOST", "documentdb")
        monkeypatch.setenv("MONGODB_PORT", "27017")  # String from env
        monkeypatch.setenv("MONGODB_DATABASE", "copilot")

        # Load config
        config = load_service_config(
            "test-service",
            schema_dir=str(schema_dir)
        )

        # Verify adapter loaded
        assert config.service_name == "test-service"
        document_store_adapter = config.get_adapter("document_store")
        assert document_store_adapter is not None
        assert document_store_adapter.driver_name == "mongodb"

        # BUG FIX VERIFICATION: Verify port is converted to int, not left as string
        assert document_store_adapter.driver_config.port == 27017
        assert isinstance(document_store_adapter.driver_config.port, int)
        assert document_store_adapter.driver_config.host == "documentdb"
        assert document_store_adapter.driver_config.database == "copilot"
