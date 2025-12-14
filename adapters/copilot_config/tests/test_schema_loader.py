# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema-driven configuration loader."""

import json

import pytest

from copilot_config import (
    ConfigSchema,
    ConfigSchemaError,
    ConfigValidationError,
    EnvConfigProvider,
    FieldSpec,
    SchemaConfigLoader,
    StaticConfigProvider,
    load_config,
)


class TestFieldSpec:
    """Tests for FieldSpec class."""

    def test_create_field_spec(self):
        """Test creating a FieldSpec."""
        field = FieldSpec(
            name="database_host",
            field_type="string",
            required=True,
            source="env",
            env_var="DB_HOST",
        )
        
        assert field.name == "database_host"
        assert field.field_type == "string"
        assert field.required is True
        assert field.source == "env"
        assert field.env_var == "DB_HOST"

    def test_field_spec_defaults(self):
        """Test FieldSpec default values."""
        field = FieldSpec(name="test", field_type="string")
        
        assert field.required is False
        assert field.default is None
        assert field.source == "env"


class TestConfigSchema:
    """Tests for ConfigSchema class."""

    def test_from_dict_basic(self):
        """Test creating ConfigSchema from dictionary."""
        schema_data = {
            "service_name": "test-service",
            "metadata": {"version": "1.0.0"},
            "fields": {
                "database_host": {
                    "type": "string",
                    "source": "env",
                    "env_var": "DB_HOST",
                    "required": True,
                },
                "port": {
                    "type": "int",
                    "source": "env",
                    "env_var": "PORT",
                    "default": 8080,
                },
            },
        }
        
        schema = ConfigSchema.from_dict(schema_data)
        
        assert schema.service_name == "test-service"
        assert "database_host" in schema.fields
        assert "port" in schema.fields
        assert schema.fields["database_host"].required is True
        assert schema.fields["port"].default == 8080

    def test_from_json_file(self, tmp_path):
        """Test loading schema from JSON file."""
        schema_file = tmp_path / "test.json"
        schema_data = {
            "service_name": "test-service",
            "fields": {
                "app_name": {
                    "type": "string",
                    "source": "env",
                    "env_var": "APP_NAME",
                    "default": "test-app",
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data))
        
        schema = ConfigSchema.from_json_file(str(schema_file))
        
        assert schema.service_name == "test-service"
        assert "app_name" in schema.fields

    def test_from_json_file_missing_raises_error(self):
        """Test that missing schema file raises error."""
        with pytest.raises(ConfigSchemaError, match="Schema file not found"):
            ConfigSchema.from_json_file("/nonexistent/schema.json")

    def test_from_json_file_invalid_json_raises_error(self, tmp_path):
        """Test that invalid JSON raises error."""
        schema_file = tmp_path / "invalid.json"
        schema_file.write_text("{ invalid json }")
        
        with pytest.raises(ConfigSchemaError, match="Invalid JSON"):
            ConfigSchema.from_json_file(str(schema_file))


class TestSchemaConfigLoader:
    """Tests for SchemaConfigLoader class."""

    def test_load_simple_config(self):
        """Test loading simple configuration."""
        schema = ConfigSchema(
            service_name="test",
            fields={
                "app_name": FieldSpec(
                    name="app_name",
                    field_type="string",
                    source="env",
                    env_var="APP_NAME",
                    default="default-app",
                ),
            },
        )
        
        env_provider = EnvConfigProvider(environ={"APP_NAME": "my-app"})
        loader = SchemaConfigLoader(schema, env_provider=env_provider)
        
        config = loader.load()
        
        assert config["app_name"] == "my-app"

    def test_load_with_default_values(self):
        """Test loading configuration with default values."""
        schema = ConfigSchema(
            service_name="test",
            fields={
                "app_name": FieldSpec(
                    name="app_name",
                    field_type="string",
                    source="env",
                    env_var="APP_NAME",
                    default="default-app",
                ),
                "port": FieldSpec(
                    name="port",
                    field_type="int",
                    source="env",
                    env_var="PORT",
                    default=8080,
                ),
            },
        )
        
        env_provider = EnvConfigProvider(environ={})
        loader = SchemaConfigLoader(schema, env_provider=env_provider)
        
        config = loader.load()
        
        assert config["app_name"] == "default-app"
        assert config["port"] == 8080

    def test_load_required_field_missing_raises_error(self):
        """Test that missing required field raises error."""
        schema = ConfigSchema(
            service_name="test",
            fields={
                "database_host": FieldSpec(
                    name="database_host",
                    field_type="string",
                    source="env",
                    env_var="DB_HOST",
                    required=True,
                ),
            },
        )
        
        env_provider = EnvConfigProvider(environ={})
        loader = SchemaConfigLoader(schema, env_provider=env_provider)
        
        with pytest.raises(ConfigValidationError, match="database_host"):
            loader.load()

    def test_load_different_types(self):
        """Test loading different field types."""
        schema = ConfigSchema(
            service_name="test",
            fields={
                "app_name": FieldSpec(
                    name="app_name",
                    field_type="string",
                    source="env",
                    env_var="APP_NAME",
                    default="app",
                ),
                "port": FieldSpec(
                    name="port",
                    field_type="int",
                    source="env",
                    env_var="PORT",
                    default=8080,
                ),
                "debug": FieldSpec(
                    name="debug",
                    field_type="bool",
                    source="env",
                    env_var="DEBUG",
                    default=False,
                ),
                "temperature": FieldSpec(
                    name="temperature",
                    field_type="float",
                    source="env",
                    env_var="TEMPERATURE",
                    default=0.5,
                ),
            },
        )
        
        env_provider = EnvConfigProvider(environ={
            "APP_NAME": "test-app",
            "PORT": "9000",
            "DEBUG": "true",
            "TEMPERATURE": "0.7",
        })
        loader = SchemaConfigLoader(schema, env_provider=env_provider)
        
        config = loader.load()
        
        assert config["app_name"] == "test-app"
        assert config["port"] == 9000
        assert config["debug"] is True
        assert config["temperature"] == 0.7

    def test_load_from_static_provider(self):
        """Test loading configuration from static provider."""
        schema = ConfigSchema(
            service_name="test",
            fields={
                "app_name": FieldSpec(
                    name="app_name",
                    field_type="string",
                    source="static",
                ),
            },
        )
        
        static_provider = StaticConfigProvider({"app_name": "static-app"})
        loader = SchemaConfigLoader(schema, static_provider=static_provider)
        
        config = loader.load()
        
        assert config["app_name"] == "static-app"


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_with_schema_file(self, tmp_path):
        """Test loading config with schema file."""
        # Create schema directory and file
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "fields": {
                "app_name": {
                    "type": "string",
                    "source": "env",
                    "env_var": "APP_NAME",
                    "default": "test-app",
                },
                "port": {
                    "type": "int",
                    "source": "env",
                    "env_var": "PORT",
                    "default": 8080,
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data))
        
        # Load config
        env_provider = EnvConfigProvider(environ={"APP_NAME": "my-app", "PORT": "9000"})
        config = load_config(
            "test-service",
            schema_dir=str(schema_dir),
            env_provider=env_provider,
        )
        
        assert config["app_name"] == "my-app"
        assert config["port"] == 9000

    def test_load_config_missing_schema_raises_error(self, tmp_path):
        """Test that missing schema file raises error."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        with pytest.raises(ConfigSchemaError, match="Schema file not found"):
            load_config("nonexistent-service", schema_dir=str(schema_dir))

    def test_load_config_validation_error(self, tmp_path):
        """Test that validation errors are raised."""
        schema_dir = tmp_path / "schemas"
        schema_dir.mkdir()
        
        schema_file = schema_dir / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "fields": {
                "database_host": {
                    "type": "string",
                    "source": "env",
                    "env_var": "DB_HOST",
                    "required": True,
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data))
        
        env_provider = EnvConfigProvider(environ={})
        
        with pytest.raises(ConfigValidationError, match="database_host"):
            load_config(
                "test-service",
                schema_dir=str(schema_dir),
                env_provider=env_provider,
            )


class TestSchemaLoaderExceptionHandling:
    """Tests for exception handling in SchemaConfigLoader."""

    def test_load_storage_collection_handles_connection_error(self):
        """Test that ConnectionError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise ConnectionError("Connection refused")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=["default_value"])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on connection error
        assert result == ["default_value"]

    def test_load_storage_collection_handles_timeout_error(self):
        """Test that TimeoutError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise TimeoutError("Operation timed out")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=[])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on timeout error
        assert result == []

    def test_load_storage_collection_handles_os_error(self):
        """Test that OSError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise OSError("I/O error")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=[])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on OS error
        assert result == []

    def test_load_storage_collection_handles_attribute_error(self):
        """Test that AttributeError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise AttributeError("'NoneType' object has no attribute 'query'")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=["default"])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on attribute error
        assert result == ["default"]

    def test_load_storage_collection_handles_type_error(self):
        """Test that TypeError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise TypeError("expected str, got int")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=["default"])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on type error
        assert result == ["default"]

    def test_load_storage_collection_handles_key_error(self):
        """Test that KeyError during storage load returns default."""
        class FailingDocStoreProvider:
            def query_documents_from_collection(self, collection_name):
                raise KeyError("missing required key")
        
        from copilot_config.schema_loader import SchemaConfigLoader
        
        loader = SchemaConfigLoader(
            schema={},
            env_provider=EnvConfigProvider({}),
            doc_store_provider=FailingDocStoreProvider()
        )
        
        field_spec = FieldSpec(name="test_field", field_type="array", default=[])
        result = loader._load_storage_collection(field_spec)
        
        # Should return default value on key error
        assert result == []
