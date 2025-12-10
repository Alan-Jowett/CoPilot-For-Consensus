# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for configuration providers."""

import os
import pytest

from copilot_events import (
    ConfigProvider,
    EnvConfigProvider,
    StaticConfigProvider,
    create_config_provider,
)


class TestEnvConfigProvider:
    """Tests for EnvConfigProvider class."""

    def test_get_existing_key(self):
        """Test getting an existing environment variable."""
        environ = {"TEST_KEY": "test_value"}
        provider = EnvConfigProvider(environ=environ)
        
        assert provider.get("TEST_KEY") == "test_value"

    def test_get_missing_key_with_default(self):
        """Test getting a missing key returns default."""
        provider = EnvConfigProvider(environ={})
        
        assert provider.get("MISSING_KEY", "default") == "default"

    def test_get_missing_key_without_default(self):
        """Test getting a missing key without default returns None."""
        provider = EnvConfigProvider(environ={})
        
        assert provider.get("MISSING_KEY") is None

    def test_get_bool_true_values(self):
        """Test getting boolean true values."""
        true_values = ["true", "True", "TRUE", "1", "yes", "YES", "on", "ON"]
        
        for value in true_values:
            environ = {"BOOL_KEY": value}
            provider = EnvConfigProvider(environ=environ)
            assert provider.get_bool("BOOL_KEY") is True, f"Failed for value: {value}"

    def test_get_bool_false_values(self):
        """Test getting boolean false values."""
        false_values = ["false", "False", "FALSE", "0", "no", "NO", "off", "OFF"]
        
        for value in false_values:
            environ = {"BOOL_KEY": value}
            provider = EnvConfigProvider(environ=environ)
            assert provider.get_bool("BOOL_KEY") is False, f"Failed for value: {value}"

    def test_get_bool_missing_key_with_default(self):
        """Test getting missing boolean key returns default."""
        provider = EnvConfigProvider(environ={})
        
        assert provider.get_bool("MISSING_KEY", True) is True
        assert provider.get_bool("MISSING_KEY", False) is False

    def test_get_bool_invalid_value_returns_default(self):
        """Test getting invalid boolean value returns default."""
        environ = {"BOOL_KEY": "invalid"}
        provider = EnvConfigProvider(environ=environ)
        
        assert provider.get_bool("BOOL_KEY", True) is True
        assert provider.get_bool("BOOL_KEY", False) is False

    def test_get_int_valid_value(self):
        """Test getting valid integer value."""
        environ = {"INT_KEY": "123"}
        provider = EnvConfigProvider(environ=environ)
        
        assert provider.get_int("INT_KEY") == 123

    def test_get_int_negative_value(self):
        """Test getting negative integer value."""
        environ = {"INT_KEY": "-456"}
        provider = EnvConfigProvider(environ=environ)
        
        assert provider.get_int("INT_KEY") == -456

    def test_get_int_missing_key_with_default(self):
        """Test getting missing integer key returns default."""
        provider = EnvConfigProvider(environ={})
        
        assert provider.get_int("MISSING_KEY", 42) == 42

    def test_get_int_invalid_value_returns_default(self):
        """Test getting invalid integer value returns default."""
        environ = {"INT_KEY": "not_a_number"}
        provider = EnvConfigProvider(environ=environ)
        
        assert provider.get_int("INT_KEY", 100) == 100

    def test_uses_os_environ_by_default(self):
        """Test that provider uses os.environ by default."""
        # Set a test environment variable
        os.environ["TEST_ENV_VAR"] = "test_value"
        
        try:
            provider = EnvConfigProvider()
            assert provider.get("TEST_ENV_VAR") == "test_value"
        finally:
            # Clean up
            del os.environ["TEST_ENV_VAR"]


class TestStaticConfigProvider:
    """Tests for StaticConfigProvider class."""

    def test_get_existing_key(self):
        """Test getting an existing configuration key."""
        config = {"key1": "value1", "key2": "value2"}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get("key1") == "value1"
        assert provider.get("key2") == "value2"

    def test_get_missing_key_with_default(self):
        """Test getting a missing key returns default."""
        provider = StaticConfigProvider(config={})
        
        assert provider.get("missing_key", "default") == "default"

    def test_get_missing_key_without_default(self):
        """Test getting a missing key without default returns None."""
        provider = StaticConfigProvider(config={})
        
        assert provider.get("missing_key") is None

    def test_get_bool_native_boolean(self):
        """Test getting native boolean values."""
        config = {"bool_true": True, "bool_false": False}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_bool("bool_true") is True
        assert provider.get_bool("bool_false") is False

    def test_get_bool_string_values(self):
        """Test getting boolean from string values."""
        config = {
            "str_true": "true",
            "str_false": "false",
            "str_yes": "yes",
            "str_no": "no",
        }
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_bool("str_true") is True
        assert provider.get_bool("str_false") is False
        assert provider.get_bool("str_yes") is True
        assert provider.get_bool("str_no") is False

    def test_get_bool_missing_key_with_default(self):
        """Test getting missing boolean key returns default."""
        provider = StaticConfigProvider(config={})
        
        assert provider.get_bool("missing_key", True) is True
        assert provider.get_bool("missing_key", False) is False

    def test_get_bool_invalid_value_returns_default(self):
        """Test getting invalid boolean value returns default."""
        config = {"bool_key": "invalid"}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_bool("bool_key", True) is True
        assert provider.get_bool("bool_key", False) is False

    def test_get_int_native_integer(self):
        """Test getting native integer value."""
        config = {"int_key": 123}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_int("int_key") == 123

    def test_get_int_string_value(self):
        """Test getting integer from string value."""
        config = {"int_key": "456"}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_int("int_key") == 456

    def test_get_int_missing_key_with_default(self):
        """Test getting missing integer key returns default."""
        provider = StaticConfigProvider(config={})
        
        assert provider.get_int("missing_key", 42) == 42

    def test_get_int_invalid_value_returns_default(self):
        """Test getting invalid integer value returns default."""
        config = {"int_key": "not_a_number"}
        provider = StaticConfigProvider(config=config)
        
        assert provider.get_int("int_key", 100) == 100

    def test_set_value(self):
        """Test setting a configuration value."""
        provider = StaticConfigProvider(config={})
        
        provider.set("new_key", "new_value")
        assert provider.get("new_key") == "new_value"

    def test_set_overwrites_existing_value(self):
        """Test setting overwrites existing value."""
        config = {"key": "old_value"}
        provider = StaticConfigProvider(config=config)
        
        provider.set("key", "new_value")
        assert provider.get("key") == "new_value"

    def test_empty_config_by_default(self):
        """Test that provider has empty config by default."""
        provider = StaticConfigProvider()
        
        assert provider.get("any_key") is None


class TestCreateConfigProvider:
    """Tests for create_config_provider factory method."""

    def test_create_env_provider(self):
        """Test creating environment config provider."""
        provider = create_config_provider("env")
        
        assert isinstance(provider, EnvConfigProvider)

    def test_create_static_provider(self):
        """Test creating static config provider."""
        provider = create_config_provider("static")
        
        assert isinstance(provider, StaticConfigProvider)

    def test_create_with_uppercase(self):
        """Test creating provider with uppercase type."""
        provider = create_config_provider("ENV")
        
        assert isinstance(provider, EnvConfigProvider)

    def test_create_with_none_defaults_to_env(self):
        """Test that None defaults to env provider."""
        # Ensure CONFIG_PROVIDER_TYPE is not set
        old_value = os.environ.pop("CONFIG_PROVIDER_TYPE", None)
        
        try:
            provider = create_config_provider(None)
            assert isinstance(provider, EnvConfigProvider)
        finally:
            # Restore old value if it existed
            if old_value is not None:
                os.environ["CONFIG_PROVIDER_TYPE"] = old_value

    def test_create_with_none_uses_env_var(self):
        """Test that None uses CONFIG_PROVIDER_TYPE env var."""
        os.environ["CONFIG_PROVIDER_TYPE"] = "static"
        
        try:
            provider = create_config_provider(None)
            assert isinstance(provider, StaticConfigProvider)
        finally:
            # Clean up
            del os.environ["CONFIG_PROVIDER_TYPE"]

    def test_create_with_unknown_type_defaults_to_env(self):
        """Test that unknown type defaults to env provider."""
        provider = create_config_provider("unknown")
        
        assert isinstance(provider, EnvConfigProvider)


class TestConfigProviderInterface:
    """Tests to ensure implementations follow the interface."""

    def test_env_provider_implements_interface(self):
        """Test that EnvConfigProvider implements ConfigProvider."""
        assert issubclass(EnvConfigProvider, ConfigProvider)

    def test_static_provider_implements_interface(self):
        """Test that StaticConfigProvider implements ConfigProvider."""
        assert issubclass(StaticConfigProvider, ConfigProvider)

    def test_env_provider_has_required_methods(self):
        """Test that EnvConfigProvider has all required methods."""
        provider = EnvConfigProvider(environ={})
        
        assert hasattr(provider, "get")
        assert hasattr(provider, "get_bool")
        assert hasattr(provider, "get_int")
        assert callable(provider.get)
        assert callable(provider.get_bool)
        assert callable(provider.get_int)

    def test_static_provider_has_required_methods(self):
        """Test that StaticConfigProvider has all required methods."""
        provider = StaticConfigProvider(config={})
        
        assert hasattr(provider, "get")
        assert hasattr(provider, "get_bool")
        assert hasattr(provider, "get_int")
        assert callable(provider.get)
        assert callable(provider.get_bool)
        assert callable(provider.get_int)
