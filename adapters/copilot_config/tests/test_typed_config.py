# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for typed configuration wrapper."""

import json
import pytest

from copilot_config import TypedConfig, load_typed_config, EnvConfigProvider


class TestTypedConfig:
    """Tests for TypedConfig class."""

    def test_attribute_access(self):
        """Test attribute-style access to config values."""
        config_dict = {
            "app_name": "test-app",
            "port": 8080,
            "debug": True,
        }

        config = TypedConfig(config_dict)

        assert config.app_name == "test-app"
        assert config.port == 8080
        assert config.debug is True

    def test_dict_style_access(self):
        """Test that dict-style access raises TypeError."""
        config_dict = {
            "app_name": "test-app",
            "port": 8080,
        }

        config = TypedConfig(config_dict)

        with pytest.raises(TypeError, match="does not support dict-style"):
            _ = config["app_name"]
        with pytest.raises(TypeError, match="does not support dict-style"):
            _ = config["port"]

    def test_get_with_default(self):
        """Test that get method raises AttributeError."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        with pytest.raises(AttributeError, match="Configuration key 'get' not found"):
            config.get("app_name")

    def test_missing_attribute_raises_error(self):
        """Test that missing attribute raises AttributeError."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        with pytest.raises(AttributeError, match="missing_key"):
            _ = config.missing_key

    def test_missing_key_raises_error(self):
        """Test that dict-style access raises TypeError."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        with pytest.raises(TypeError, match="does not support dict-style"):
            _ = config["missing_key"]

    def test_to_dict(self):
        """Test that to_dict method raises AttributeError."""
        config_dict = {
            "app_name": "test-app",
            "port": 8080,
        }

        config = TypedConfig(config_dict)

        with pytest.raises(AttributeError, match="Configuration key 'to_dict' not found"):
            config.to_dict()

    def test_contains(self):
        """Test that 'in' operator raises TypeError."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        with pytest.raises(TypeError, match="does not support dict-style"):
            "app_name" in config

    def test_repr(self):
        """Test string representation."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        assert "TypedConfig" in repr(config)
        assert "test-app" in repr(config)

    def test_immutability(self):
        """Test that config is immutable after loading."""
        config_dict = {"app_name": "test-app"}

        config = TypedConfig(config_dict)

        # Attempting to set an attribute should raise AttributeError
        with pytest.raises(AttributeError, match="Cannot modify configuration"):
            config.app_name = "new-value"

        # Attempting to set a new attribute should also raise
        with pytest.raises(AttributeError, match="Cannot modify configuration"):
            config.new_key = "value"

        # Original value should be unchanged
        assert config.app_name == "test-app"


class TestLoadTypedConfig:
    """Tests for load_typed_config function."""

    def test_load_typed_config(self, tmp_path):
        """Test loading typed config from schema."""
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

        # Load typed config
        env_provider = EnvConfigProvider(environ={"APP_NAME": "my-app"})
        config = load_typed_config(
            "test-service",
            schema_dir=str(schema_dir),
            env_provider=env_provider,
        )

        assert isinstance(config, TypedConfig)
        assert config.app_name == "my-app"
        assert config.port == 8080

    def test_load_typed_config_attribute_access(self, tmp_path):
        """Test attribute access on loaded typed config."""
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
                    "default": "localhost",
                },
                "database_port": {
                    "type": "int",
                    "source": "env",
                    "env_var": "DB_PORT",
                    "default": 5432,
                },
            },
        }
        schema_file.write_text(json.dumps(schema_data))

        config = load_typed_config("test-service", schema_dir=str(schema_dir))

        # Should be able to access via attributes
        assert config.database_host == "localhost"
        assert config.database_port == 5432
