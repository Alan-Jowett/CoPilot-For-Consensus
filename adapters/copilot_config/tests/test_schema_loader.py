# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for schema loader and related functionality."""

import json
import os
import tempfile
from pathlib import Path

import pytest
from copilot_config.schema_loader import (
    ConfigSchema,
    ConfigSchemaError,
    ConfigValidationError,
    EnvConfigProvider,
    FieldSpec,
    SchemaConfigLoader,
    StaticConfigProvider,
    _is_version_compatible,
    _parse_semver,
    _resolve_schema_directory,
)


class TestParseSemver:
    """Tests for _parse_semver function."""

    def test_parse_valid_semver(self):
        """Test parsing valid semver string."""
        assert _parse_semver("1.2.3") == (1, 2, 3)
        assert _parse_semver("0.0.0") == (0, 0, 0)
        assert _parse_semver("10.20.30") == (10, 20, 30)

    def test_parse_semver_with_extra_parts(self):
        """Test parsing semver with extra parts (ignores extra)."""
        assert _parse_semver("1.2.3.4") == (1, 2, 3)

    def test_parse_invalid_semver_too_few_parts(self):
        """Test parsing semver with too few parts raises error."""
        with pytest.raises(ValueError, match="at least 3 components"):
            _parse_semver("1.2")

    def test_parse_invalid_semver_non_numeric(self):
        """Test parsing semver with non-numeric parts raises error."""
        with pytest.raises(ValueError, match="must be an integer"):
            _parse_semver("1.2.a")

    def test_parse_invalid_semver_empty_string(self):
        """Test parsing empty semver raises error."""
        with pytest.raises(ValueError, match="cannot be empty"):
            _parse_semver("")


class TestIsVersionCompatible:
    """Tests for _is_version_compatible function."""

    def test_compatible_versions(self):
        """Test version compatibility checks."""
        assert _is_version_compatible("1.2.3", "1.2.3") is True
        assert _is_version_compatible("1.3.0", "1.2.3") is True
        assert _is_version_compatible("2.0.0", "1.9.9") is True
        assert _is_version_compatible("1.2.4", "1.2.3") is True

    def test_incompatible_versions(self):
        """Test incompatible versions."""
        assert _is_version_compatible("1.2.2", "1.2.3") is False
        assert _is_version_compatible("1.1.9", "1.2.0") is False
        assert _is_version_compatible("0.9.9", "1.0.0") is False

    def test_invalid_versions_returns_true(self):
        """Test that invalid versions return True (permissive)."""
        assert _is_version_compatible("invalid", "1.0.0") is True
        assert _is_version_compatible("1.0.0", "invalid") is True


class TestResolveSchemaDirectory:
    """Tests for _resolve_schema_directory function."""

    def test_explicit_schema_dir(self):
        """Test resolving with explicit schema directory."""
        result = _resolve_schema_directory("/explicit/path")
        assert result == "/explicit/path"

    def test_schema_dir_from_env(self, monkeypatch):
        """Test resolving from SCHEMA_DIR environment variable."""
        monkeypatch.setenv("SCHEMA_DIR", "/env/path")
        result = _resolve_schema_directory()
        assert result == "/env/path"

    def test_schema_dir_default(self, monkeypatch):
        """Test default schema directory resolution."""
        # Remove env var if set
        monkeypatch.delenv("SCHEMA_DIR", raising=False)
        result = _resolve_schema_directory()
        # Should return some path with docs/schemas/configs
        assert "schemas" in result or "docs" in result


class TestFieldSpec:
    """Tests for FieldSpec class."""

    def test_field_spec_creation(self):
        """Test creating a FieldSpec."""
        spec = FieldSpec(
            name="test_field",
            field_type="string",
            required=True,
            env_var="TEST_FIELD"
        )

        assert spec.name == "test_field"
        assert spec.field_type == "string"
        assert spec.required is True
        assert spec.env_var == "TEST_FIELD"


class TestConfigSchema:
    """Tests for ConfigSchema class."""

    def test_config_schema_from_dict(self):
        """Test creating ConfigSchema from dictionary."""
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "min_service_version": "1.0.0",
            "service_settings": {
                "app_name": {
                    "type": "string",
                    "source": "env",
                    "env_var": "APP_NAME",
                    "default": "test-app"
                }
            },
            "adapters": {
                "message_bus": {"$ref": "../adapters/message_bus.json"}
            }
        }

        schema = ConfigSchema.from_dict(schema_data)

        assert schema.service_name == "test-service"
        assert schema.schema_version == "1.0.0"
        assert schema.min_service_version == "1.0.0"
        assert "app_name" in schema.fields
        assert "message_bus" in schema.adapters_schema

    def test_config_schema_from_json_file(self, tmp_path):
        """Test loading ConfigSchema from JSON file."""
        schema_file = tmp_path / "test-service.json"
        schema_data = {
            "service_name": "test-service",
            "schema_version": "1.0.0",
            "service_settings": {
                "port": {
                    "type": "int",
                    "source": "env",
                    "env_var": "PORT",
                    "default": 8080
                }
            }
        }
        schema_file.write_text(json.dumps(schema_data))

        schema = ConfigSchema.from_json_file(str(schema_file))

        assert schema.service_name == "test-service"
        assert "port" in schema.fields

    def test_config_schema_missing_file(self):
        """Test loading ConfigSchema from missing file raises error."""
        with pytest.raises(ConfigSchemaError, match="not found"):
            ConfigSchema.from_json_file("/nonexistent/path/schema.json")

    def test_config_schema_invalid_json(self, tmp_path):
        """Test loading ConfigSchema from invalid JSON raises error."""
        schema_file = tmp_path / "invalid.json"
        schema_file.write_text("{ invalid json")

        with pytest.raises(ConfigSchemaError, match="Invalid JSON"):
            ConfigSchema.from_json_file(str(schema_file))


class TestEnvConfigProvider:
    """Tests for EnvConfigProvider."""

    def test_get_value_from_env(self):
        """Test getting value from environment."""
        environ = {"TEST_VAR": "test_value"}
        provider = EnvConfigProvider(environ=environ)

        assert provider.get("TEST_VAR") == "test_value"

    def test_get_missing_value(self):
        """Test getting missing value returns default."""
        provider = EnvConfigProvider(environ={})

        assert provider.get("MISSING_VAR", "default") == "default"

    def test_get_bool_true_values(self):
        """Test getting boolean true values."""
        for val in ["true", "1", "yes", "on"]:
            provider = EnvConfigProvider(environ={"TEST_BOOL": val})
            assert provider.get_bool("TEST_BOOL") is True

    def test_get_bool_false_values(self):
        """Test getting boolean false values."""
        for val in ["false", "0", "no", "off"]:
            provider = EnvConfigProvider(environ={"TEST_BOOL": val})
            assert provider.get_bool("TEST_BOOL") is False

    def test_get_int_value(self):
        """Test getting integer value."""
        provider = EnvConfigProvider(environ={"TEST_INT": "42"})

        assert provider.get_int("TEST_INT") == 42

    def test_get_int_invalid_value(self):
        """Test getting integer from non-numeric value returns default."""
        provider = EnvConfigProvider(environ={"TEST_INT": "not_a_number"})

        assert provider.get_int("TEST_INT", 99) == 99


class TestStaticConfigProvider:
    """Tests for StaticConfigProvider."""

    def test_get_value_from_static(self):
        """Test getting value from static config."""
        config = {"app_name": "test-app"}
        provider = StaticConfigProvider(config=config)

        assert provider.get("app_name") == "test-app"

    def test_get_bool_from_static(self):
        """Test getting boolean from static config."""
        config = {"debug": True}
        provider = StaticConfigProvider(config=config)

        assert provider.get_bool("debug") is True

    def test_get_int_from_static(self):
        """Test getting integer from static config."""
        config = {"port": 8080}
        provider = StaticConfigProvider(config=config)

        assert provider.get_int("port") == 8080


class TestSchemaConfigLoader:
    """Tests for SchemaConfigLoader."""

    def test_load_simple_config(self):
        """Test loading simple configuration."""
        schema = ConfigSchema(
            service_name="test-service",
            fields={
                "app_name": FieldSpec(
                    name="app_name",
                    field_type="string",
                    required=False,
                    default="test-app",
                    env_var="APP_NAME"
                )
            }
        )

        env_provider = EnvConfigProvider(environ={"APP_NAME": "my-app"})
        loader = SchemaConfigLoader(schema=schema, env_provider=env_provider)

        config = loader.load()

        assert config["app_name"] == "my-app"

    def test_load_required_field_missing(self):
        """Test loading with missing required field raises error."""
        schema = ConfigSchema(
            service_name="test-service",
            fields={
                "api_key": FieldSpec(
                    name="api_key",
                    field_type="string",
                    required=True,
                    env_var="API_KEY"
                )
            }
        )

        env_provider = EnvConfigProvider(environ={})
        loader = SchemaConfigLoader(schema=schema, env_provider=env_provider)

        with pytest.raises(ConfigValidationError, match="Required field"):
            loader.load()

    def test_load_with_defaults(self):
        """Test loading with default values."""
        schema = ConfigSchema(
            service_name="test-service",
            fields={
                "port": FieldSpec(
                    name="port",
                    field_type="int",
                    required=False,
                    default=8080,
                    env_var="PORT"
                )
            }
        )

        env_provider = EnvConfigProvider(environ={})
        loader = SchemaConfigLoader(schema=schema, env_provider=env_provider)

        config = loader.load()

        assert config["port"] == 8080

    def test_load_with_type_conversion(self):
        """Test loading with type conversion."""
        schema = ConfigSchema(
            service_name="test-service",
            fields={
                "port": FieldSpec(
                    name="port",
                    field_type="int",
                    required=False,
                    env_var="PORT"
                ),
                "debug": FieldSpec(
                    name="debug",
                    field_type="bool",
                    required=False,
                    env_var="DEBUG"
                )
            }
        )

        env_provider = EnvConfigProvider(environ={"PORT": "9000", "DEBUG": "true"})
        loader = SchemaConfigLoader(schema=schema, env_provider=env_provider)

        config = loader.load()

        assert config["port"] == 9000
        assert config["debug"] is True
