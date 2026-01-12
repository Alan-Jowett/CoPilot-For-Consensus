# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for service configuration loading."""

import json

import pytest
from copilot_config import AdapterConfig, DriverConfig, ServiceConfig, load_service_config


class TestServiceConfig:
    """Tests for ServiceConfig model."""

    def test_service_config_creation(self):
        """Test creating a ServiceConfig instance."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})
        adapter_config = AdapterConfig(adapter_type="llm_backend", driver_name="openai", driver_config=driver_config)

        config = ServiceConfig(
            service_name="summarization",
            service_settings={"max_tokens": 500},
            adapters=[adapter_config],
            schema_version="1.0.0",
            min_service_version="1.0.0",
        )

        assert config.service_name == "summarization"
        assert config.service_settings["max_tokens"] == 500
        assert len(config.adapters) == 1
        assert config.adapters[0].adapter_type == "llm_backend"

    def test_get_adapter(self):
        """Test getting adapter by name."""
        driver_config = DriverConfig(driver_name="openai", config={})
        adapter_config = AdapterConfig(adapter_type="llm_backend", driver_name="openai", driver_config=driver_config)

        config = ServiceConfig(
            service_name="summarization", service_settings={}, adapters=[adapter_config], schema_version="1.0.0"
        )

        llm_adapter = config.get_adapter("llm_backend")
        assert llm_adapter is not None
        assert llm_adapter.driver_name == "openai"

    def test_get_adapter_not_found(self):
        """Test getting non-existent adapter returns None."""
        config = ServiceConfig(service_name="summarization", service_settings={}, adapters=[], schema_version="1.0.0")

        result = config.get_adapter("nonexistent")
        assert result is None

    def test_get_service_setting(self):
        """Test getting service setting."""
        config = ServiceConfig(
            service_name="summarization",
            service_settings={"max_tokens": 500, "temperature": 0.7},
            adapters=[],
            schema_version="1.0.0",
        )

        assert config.get_service_setting("max_tokens") == 500
        assert config.get_service_setting("temperature") == 0.7

    def test_get_service_setting_not_found(self):
        """Test getting non-existent service setting returns None."""
        config = ServiceConfig(service_name="summarization", service_settings={}, adapters=[], schema_version="1.0.0")

        result = config.get_service_setting("nonexistent")
        assert result is None

    def test_get_service_setting_with_default(self):
        """Test getting service setting with default value."""
        config = ServiceConfig(
            service_name="summarization", service_settings={"max_tokens": 500}, adapters=[], schema_version="1.0.0"
        )

        result = config.get_service_setting("temperature", default=0.7)
        assert result == 0.7


class TestAdapterConfig:
    """Tests for AdapterConfig model."""

    def test_adapter_config_creation(self):
        """Test creating an AdapterConfig instance."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})

        adapter_config = AdapterConfig(adapter_type="llm_backend", driver_name="openai", driver_config=driver_config)

        assert adapter_config.adapter_type == "llm_backend"
        assert adapter_config.driver_name == "openai"
        assert adapter_config.driver_config.driver_name == "openai"

    def test_adapter_config_attribute_delegation(self):
        """Test that AdapterConfig delegates attribute access to driver_config."""
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret"})
        adapter_config = AdapterConfig(adapter_type="llm_backend", driver_name="openai", driver_config=driver_config)

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
        driver_config = DriverConfig(driver_name="openai", config={"api_key": "secret", "model": "gpt-4"})

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
                "max_tokens": {"type": "int", "source": "env", "env_var": "MAX_TOKENS", "default": 500}
            },
            "adapters_schema": {},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Set environment variables
        monkeypatch.setenv("SCHEMA_DIR", str(schema_dir))

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

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
            "adapters": {"llm_backend": {"$ref": "../adapters/llm_backend.json"}},
        }

        service_file = services_dir / "summarization.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "LLM_BACKEND"},
                "drivers": {"properties": {"openai": {"$ref": "../drivers/llm_backend/llm_openai.json"}}},
            }
        }

        adapter_file = adapters_dir / "llm_backend.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "api_key": {"type": "string", "source": "secret", "secret_name": "openai_api_key"},
                "model": {"type": "string", "source": "env", "env_var": "OPENAI_MODEL", "default": "gpt-4"},
            }
        }

        driver_file = llm_drivers_dir / "llm_openai.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4-turbo")

        # Load config
        config = load_service_config("summarization", schema_dir=str(schema_dir))

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
            "adapters": {"message_bus": {"$ref": "../adapters/message_bus.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "MESSAGE_BUS_TYPE"},
                "drivers": {"properties": {"rabbitmq": {"$ref": "../drivers/message_bus/rabbitmq.json"}}},
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
                    "default": "localhost",
                },
                "rabbitmq_port": {"type": "integer", "source": "env", "env_var": "RABBITMQ_PORT", "default": 5672},
                "exchange": {"type": "string", "default": "copilot.events"},
                "exchange_type": {"type": "string", "default": "topic"},
            }
        }

        driver_file = message_bus_drivers_dir / "rabbitmq.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables
        monkeypatch.setenv("MESSAGE_BUS_TYPE", "rabbitmq")
        monkeypatch.setenv("RABBITMQ_HOST", "messagebus")
        monkeypatch.setenv("RABBITMQ_PORT", "5672")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

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
            "adapters": {"document_store": {"$ref": "../adapters/document_store.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "DOCUMENT_STORE_TYPE"},
                "drivers": {"properties": {"mongodb": {"$ref": "../drivers/document_store/mongodb.json"}}},
            }
        }

        adapter_file = adapters_dir / "document_store.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create MongoDB driver schema with port as "integer" type
        driver_schema = {
            "properties": {
                "host": {"type": "string", "source": "env", "env_var": "MONGODB_HOST", "default": "localhost"},
                "port": {
                    "type": "integer",  # Note: "integer" not "int"
                    "source": "env",
                    "env_var": "MONGODB_PORT",
                    "default": 27017,
                },
                "database": {"type": "string", "source": "env", "env_var": "MONGODB_DATABASE", "default": "test"},
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
        config = load_service_config("test-service", schema_dir=str(schema_dir))

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

    def test_multiple_env_var_candidates(self, tmp_path, monkeypatch):
        """Test that multiple env_var candidates are tried in order."""
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

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"llm_backend": {"$ref": "../adapters/llm_backend.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "LLM_BACKEND"},
                "drivers": {"properties": {"openai": {"$ref": "../drivers/llm_backend/llm_openai.json"}}},
            }
        }

        adapter_file = adapters_dir / "llm_backend.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with multiple env_var candidates
        driver_schema = {
            "properties": {
                "api_key": {
                    "type": "string",
                    "source": "env",
                    "env_var": ["OPENAI_API_KEY_PRIMARY", "OPENAI_API_KEY_FALLBACK"],
                    "default": "default_key",
                }
            }
        }

        driver_file = llm_drivers_dir / "llm_openai.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set only the fallback env var
        monkeypatch.setenv("LLM_BACKEND", "openai")
        monkeypatch.setenv("OPENAI_API_KEY_FALLBACK", "fallback_api_key")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify the fallback value is used
        llm_adapter = config.get_adapter("llm_backend")
        assert llm_adapter.driver_config.api_key == "fallback_api_key"

    def test_boolean_type_conversion(self, tmp_path, monkeypatch):
        """Test boolean type conversion from environment variables."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        test_drivers_dir = drivers_dir / "test_adapter"
        test_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "drivers": {"properties": {"test": {"$ref": "../drivers/test_adapter/test.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with boolean field
        driver_schema = {
            "properties": {
                "enabled": {"type": "boolean", "source": "env", "env_var": "TEST_ENABLED"},
                "debug": {"type": "bool", "source": "env", "env_var": "TEST_DEBUG"},
            }
        }

        driver_file = test_drivers_dir / "test.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variables with various boolean values
        monkeypatch.setenv("TEST_ADAPTER_TYPE", "test")
        monkeypatch.setenv("TEST_ENABLED", "true")
        monkeypatch.setenv("TEST_DEBUG", "1")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify boolean conversion
        test_adapter = config.get_adapter("test_adapter")
        assert test_adapter.driver_config.enabled is True
        assert test_adapter.driver_config.debug is True

    def test_invalid_integer_conversion_fallback(self, tmp_path, monkeypatch):
        """Test that invalid integer values are kept as strings."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        test_drivers_dir = drivers_dir / "test_adapter"
        test_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "drivers": {"properties": {"test": {"$ref": "../drivers/test_adapter/test.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with integer field
        driver_schema = {"properties": {"count": {"type": "int", "source": "env", "env_var": "TEST_COUNT"}}}

        driver_file = test_drivers_dir / "test.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Set environment variable with invalid integer
        monkeypatch.setenv("TEST_ADAPTER_TYPE", "test")
        monkeypatch.setenv("TEST_COUNT", "not_a_number")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify the value is kept as string when int conversion fails
        test_adapter = config.get_adapter("test_adapter")
        assert test_adapter.driver_config.count == "not_a_number"

    def test_required_discriminant_missing(self, tmp_path, monkeypatch):
        """Test that missing required discriminant raises ValueError."""
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
            "service_settings": {},
            "adapters": {"required_adapter": {"$ref": "../adapters/required_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema with required discriminant
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "REQUIRED_ADAPTER_TYPE", "required": True},
                "drivers": {"properties": {}},
            }
        }

        adapter_file = adapters_dir / "required_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Don't set the required environment variable
        # Load config should raise ValueError
        with pytest.raises(ValueError, match="requires discriminant configuration"):
            load_service_config("test-service", schema_dir=str(schema_dir))

    def test_optional_adapter_with_default(self, tmp_path, monkeypatch):
        """Test optional adapter with default driver value."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        test_drivers_dir = drivers_dir / "optional_adapter"
        test_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"optional_adapter": {"$ref": "../adapters/optional_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema with optional discriminant and default
        adapter_schema = {
            "properties": {
                "discriminant": {
                    "field": "driver_name",
                    "env_var": "OPTIONAL_ADAPTER_TYPE",
                    "default": "default_driver",
                },
                "drivers": {"properties": {"default_driver": {"$ref": "../drivers/optional_adapter/default.json"}}},
            }
        }

        adapter_file = adapters_dir / "optional_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {"properties": {"setting": {"type": "string", "default": "default_value"}}}

        driver_file = test_drivers_dir / "default.json"
        driver_file.write_text(json.dumps(driver_schema))

        # Don't set the env var, should use default
        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify default driver is used
        adapter = config.get_adapter("optional_adapter")
        assert adapter is not None
        assert adapter.driver_name == "default_driver"

    def test_optional_adapter_no_default_skipped(self, tmp_path, monkeypatch):
        """Test that optional adapter with no default is skipped."""
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
            "service_settings": {},
            "adapters": {"optional_adapter": {"$ref": "../adapters/optional_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema with optional discriminant and no default
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "OPTIONAL_ADAPTER_TYPE"},
                "drivers": {"properties": {}},
            }
        }

        adapter_file = adapters_dir / "optional_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Don't set the env var
        # Load config - adapter should be skipped
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify adapter is not present
        adapter = config.get_adapter("optional_adapter")
        assert adapter is None

    def test_missing_driver_schema_reference(self, tmp_path, monkeypatch):
        """Test that missing driver schema reference raises ValueError."""
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
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema without schema reference for selected driver
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "drivers": {"properties": {"other_driver": {"$ref": "../drivers/test_adapter/other.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Set env var to a driver without schema reference
        monkeypatch.setenv("TEST_ADAPTER_TYPE", "missing_driver")

        # Load config should raise ValueError
        with pytest.raises(ValueError, match="has no schema reference for driver"):
            load_service_config("test-service", schema_dir=str(schema_dir))

    def test_missing_driver_schema_file(self, tmp_path, monkeypatch):
        """Test that missing driver schema file raises FileNotFoundError."""
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
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema pointing to non-existent driver file
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "drivers": {"properties": {"test": {"$ref": "../drivers/test_adapter/missing.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        monkeypatch.setenv("TEST_ADAPTER_TYPE", "test")

        # Load config should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Driver schema file not found"):
            load_service_config("test-service", schema_dir=str(schema_dir))

    def test_common_properties_extraction(self, tmp_path, monkeypatch):
        """Test that common properties are extracted and merged with driver config."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        test_drivers_dir = drivers_dir / "test_adapter"
        test_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema with common properties
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "common": {
                    "properties": {
                        "timeout": {"type": "int", "source": "env", "env_var": "TEST_TIMEOUT", "default": 30},
                        "retry_count": {"type": "int", "default": 3},
                    }
                },
                "drivers": {"properties": {"test": {"$ref": "../drivers/test_adapter/test.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema
        driver_schema = {
            "properties": {
                "api_key": {"type": "string", "source": "env", "env_var": "TEST_API_KEY", "default": "default_key"}
            }
        }

        driver_file = test_drivers_dir / "test.json"
        driver_file.write_text(json.dumps(driver_schema))

        monkeypatch.setenv("TEST_ADAPTER_TYPE", "test")
        monkeypatch.setenv("TEST_TIMEOUT", "60")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify common properties are included
        adapter = config.get_adapter("test_adapter")
        assert adapter.driver_config.timeout == 60
        assert adapter.driver_config.retry_count == 3
        assert adapter.driver_config.api_key == "default_key"

    def test_missing_adapter_schema_file(self, tmp_path, monkeypatch):
        """Test that missing adapter schema file raises FileNotFoundError."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        # Create service schema referencing non-existent adapter
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"missing_adapter": {"$ref": "../adapters/missing_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Load config should raise FileNotFoundError
        with pytest.raises(FileNotFoundError, match="Adapter schema file not found"):
            load_service_config("test-service", schema_dir=str(schema_dir))

    def test_composite_adapter_oidc_providers(self, tmp_path, monkeypatch):
        """Test composite adapter pattern (like oidc_providers with multiple providers)."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        oidc_drivers_dir = drivers_dir / "oidc_providers"
        oidc_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"oidc_providers": {"$ref": "../adapters/oidc_providers.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create composite adapter schema (no discriminant)
        adapter_schema = {
            "properties": {
                "oidc_providers": {
                    "properties": {
                        "github": {"$ref": "./drivers/oidc_providers/github.json"},
                        "google": {"$ref": "./drivers/oidc_providers/google.json"},
                    }
                }
            }
        }

        adapter_file = adapters_dir / "oidc_providers.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create GitHub provider schema
        github_schema = {
            "properties": {
                "github_client_id": {"type": "string", "source": "env", "env_var": "GITHUB_CLIENT_ID"},
                "github_client_secret": {"type": "string", "source": "env", "env_var": "GITHUB_CLIENT_SECRET"},
            }
        }

        github_file = oidc_drivers_dir / "github.json"
        github_file.write_text(json.dumps(github_schema))

        # Create Google provider schema
        google_schema = {
            "properties": {
                "google_client_id": {"type": "string", "source": "env", "env_var": "GOOGLE_CLIENT_ID"},
                "google_client_secret": {"type": "string", "source": "env", "env_var": "GOOGLE_CLIENT_SECRET"},
            }
        }

        google_file = oidc_drivers_dir / "google.json"
        google_file.write_text(json.dumps(google_schema))

        # Set environment variables for GitHub provider only
        monkeypatch.setenv("GITHUB_CLIENT_ID", "github_id_123")
        monkeypatch.setenv("GITHUB_CLIENT_SECRET", "github_secret_456")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify composite adapter is created with only configured providers
        adapter = config.get_adapter("oidc_providers")
        assert adapter is not None
        assert adapter.driver_name == "multi"
        assert "github" in adapter.driver_config.config
        assert "google" not in adapter.driver_config.config  # Not configured

    def test_composite_adapter_no_properties_error(self, tmp_path, monkeypatch):
        """Test that composite adapter without properties raises ValueError."""
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
            "service_settings": {},
            "adapters": {"bad_adapter": {"$ref": "../adapters/bad_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema without discriminant and without composite properties
        adapter_schema = {"properties": {}}

        adapter_file = adapters_dir / "bad_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Load config should raise ValueError
        with pytest.raises(ValueError, match="has no discriminant and no composite properties"):
            load_service_config("test-service", schema_dir=str(schema_dir))

    def test_backcompat_secret_provider(self, tmp_path, monkeypatch):
        """Test backward compatibility: secret provider via env without adapter schema reference."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        secret_drivers_dir = drivers_dir / "secret_provider"
        secret_drivers_dir.mkdir()

        # Create service schema WITHOUT secret_provider in adapters
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {},  # No secret_provider adapter
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create secret_provider adapter schema for backward compat
        secret_adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "SECRET_PROVIDER_TYPE"},
                "drivers": {"properties": {"env": {"$ref": "../drivers/secret_provider/env.json"}}},
            }
        }

        secret_adapter_file = adapters_dir / "secret_provider.json"
        secret_adapter_file.write_text(json.dumps(secret_adapter_schema))

        # Create env secret provider driver schema
        env_secret_schema = {"properties": {}}

        env_secret_file = secret_drivers_dir / "env.json"
        env_secret_file.write_text(json.dumps(env_secret_schema))

        # Set SECRET_PROVIDER_TYPE to trigger back-compat behavior
        monkeypatch.setenv("SECRET_PROVIDER_TYPE", "env")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify secret_provider adapter is added via back-compat path
        secret_adapter = config.get_adapter("secret_provider")
        assert secret_adapter is not None
        assert secret_adapter.driver_name == "env"

    def test_env_var_with_empty_candidates(self, tmp_path, monkeypatch):
        """Test that empty/None env_var candidates are skipped."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()

        services_dir = schema_dir / "services"
        services_dir.mkdir()

        adapters_dir = schema_dir / "adapters"
        adapters_dir.mkdir()

        drivers_dir = adapters_dir / "drivers"
        drivers_dir.mkdir()

        test_drivers_dir = drivers_dir / "test_adapter"
        test_drivers_dir.mkdir()

        # Create service schema
        service_schema = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {},
            "adapters": {"test_adapter": {"$ref": "../adapters/test_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create adapter schema
        adapter_schema = {
            "properties": {
                "discriminant": {"field": "driver_name", "env_var": "TEST_ADAPTER_TYPE"},
                "drivers": {"properties": {"test": {"$ref": "../drivers/test_adapter/test.json"}}},
            }
        }

        adapter_file = adapters_dir / "test_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Create driver schema with None/empty candidates mixed with valid one
        driver_schema = {
            "properties": {
                "api_key": {
                    "type": "string",
                    "source": "env",
                    "env_var": [None, "", "VALID_API_KEY"],  # First two should be skipped
                    "default": "default_key",
                }
            }
        }

        driver_file = test_drivers_dir / "test.json"
        driver_file.write_text(json.dumps(driver_schema))

        monkeypatch.setenv("TEST_ADAPTER_TYPE", "test")
        monkeypatch.setenv("VALID_API_KEY", "valid_key_value")

        # Load config
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # Verify the valid env var is used (empty/None candidates skipped)
        adapter = config.get_adapter("test_adapter")
        assert adapter.driver_config.api_key == "valid_key_value"

    def test_composite_adapter_with_missing_ref(self, tmp_path, monkeypatch):
        """Test composite adapter where child has no $ref."""
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
            "service_settings": {},
            "adapters": {"composite_adapter": {"$ref": "../adapters/composite_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create composite adapter schema with child without $ref
        adapter_schema = {
            "properties": {
                "composite_adapter": {
                    "properties": {
                        "provider1": {
                            # Missing $ref - should be skipped
                            "type": "object"
                        }
                    }
                }
            }
        }

        adapter_file = adapters_dir / "composite_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Load config - should complete without error, but no adapter should be created
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # No providers configured, so composite adapter not created
        adapter = config.get_adapter("composite_adapter")
        assert adapter is None

    def test_composite_adapter_with_nonexistent_child_schema(self, tmp_path, monkeypatch):
        """Test composite adapter where child schema file doesn't exist."""
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
            "service_settings": {},
            "adapters": {"composite_adapter": {"$ref": "../adapters/composite_adapter.json"}},
        }

        service_file = services_dir / "test-service.json"
        service_file.write_text(json.dumps(service_schema))

        # Create composite adapter schema with child referencing non-existent file
        adapter_schema = {
            "properties": {
                "composite_adapter": {
                    "properties": {"provider1": {"$ref": "./drivers/composite_adapter/nonexistent.json"}}
                }
            }
        }

        adapter_file = adapters_dir / "composite_adapter.json"
        adapter_file.write_text(json.dumps(adapter_schema))

        # Load config - should skip non-existent child schema
        config = load_service_config("test-service", schema_dir=str(schema_dir))

        # No providers configured (schema doesn't exist), so composite adapter not created
        adapter = config.get_adapter("composite_adapter")
        assert adapter is None
