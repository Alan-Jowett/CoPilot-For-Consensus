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
        """Test dict-style access to config values."""
        config_dict = {
            "app_name": "test-app",
            "port": 8080,
        }
        
        config = TypedConfig(config_dict)
        
        assert config["app_name"] == "test-app"
        assert config["port"] == 8080

    def test_get_with_default(self):
        """Test get method with default value."""
        config_dict = {"app_name": "test-app"}
        
        config = TypedConfig(config_dict)
        
        assert config.get("app_name") == "test-app"
        assert config.get("missing_key", "default") == "default"

    def test_missing_attribute_raises_error(self):
        """Test that missing attribute raises AttributeError."""
        config_dict = {"app_name": "test-app"}
        
        config = TypedConfig(config_dict)
        
        with pytest.raises(AttributeError, match="missing_key"):
            _ = config.missing_key

    def test_missing_key_raises_error(self):
        """Test that missing key raises KeyError."""
        config_dict = {"app_name": "test-app"}
        
        config = TypedConfig(config_dict)
        
        with pytest.raises(KeyError):
            _ = config["missing_key"]

    def test_to_dict(self):
        """Test converting config to dictionary."""
        config_dict = {
            "app_name": "test-app",
            "port": 8080,
        }
        
        config = TypedConfig(config_dict)
        
        result = config.to_dict()
        assert result == config_dict
        # Ensure it's a copy
        assert result is not config._config

    def test_contains(self):
        """Test checking if key exists."""
        config_dict = {"app_name": "test-app"}
        
        config = TypedConfig(config_dict)
        
        assert "app_name" in config
        assert "missing_key" not in config

    def test_repr(self):
        """Test string representation."""
        config_dict = {"app_name": "test-app"}
        
        config = TypedConfig(config_dict)
        
        assert "TypedConfig" in repr(config)
        assert "test-app" in repr(config)


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
