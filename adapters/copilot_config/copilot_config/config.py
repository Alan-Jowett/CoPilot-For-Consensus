# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Configuration provider abstraction for Copilot-for-Consensus services."""

import os
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict


class ConfigProvider(ABC):
    """Abstract base class for configuration providers.
    
    This interface defines a consistent way to access configuration values
    across different sources (environment variables, .env files, cloud config stores).
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        pass

    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Boolean configuration value or default
        """
        pass

    @abstractmethod
    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Integer configuration value or default
        """
        pass


class EnvConfigProvider(ConfigProvider):
    """Configuration provider that reads from environment variables.
    
    This provider reads configuration from os.environ and supports
    type conversion for common types (bool, int).
    """

    def __init__(self, environ: Optional[Dict[str, str]] = None):
        """Initialize the environment config provider.
        
        Args:
            environ: Environment dictionary to use (defaults to os.environ)
        """
        self._environ = environ if environ is not None else os.environ

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from environment variables.
        
        Args:
            key: Environment variable name
            default: Default value if key is not found
            
        Returns:
            Environment variable value or default
        """
        return self._environ.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value from environment variables.
        
        Accepts: "true", "1", "yes", "on" (case-insensitive) as True
        Accepts: "false", "0", "no", "off" (case-insensitive) as False
        
        Args:
            key: Environment variable name
            default: Default value if key is not found
            
        Returns:
            Boolean value or default
        """
        value = self._environ.get(key)
        if value is None:
            return default
        
        value_lower = value.lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        elif value_lower in ("false", "0", "no", "off"):
            return False
        else:
            return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value from environment variables.
        
        Args:
            key: Environment variable name
            default: Default value if key is not found or cannot be parsed
            
        Returns:
            Integer value or default
        """
        value = self._environ.get(key)
        if value is None:
            return default
        
        try:
            return int(value)
        except ValueError:
            return default


class StaticConfigProvider(ConfigProvider):
    """Configuration provider with static/hardcoded values.
    
    This provider is useful for testing and allows setting configuration
    values programmatically without relying on external sources.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the static config provider.
        
        Args:
            config: Dictionary of configuration values
        """
        self._config = config if config is not None else {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value from the static dictionary.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value from the static dictionary.
        
        Args:
            key: Configuration key
            default: Default value if key is not found
            
        Returns:
            Boolean value or default
        """
        value = self._config.get(key)
        if value is None:
            return default
        
        if isinstance(value, bool):
            return value
        
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ("true", "1", "yes", "on"):
                return True
            elif value_lower in ("false", "0", "no", "off"):
                return False
        
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value from the static dictionary.
        
        Args:
            key: Configuration key
            default: Default value if key is not found or cannot be converted
            
        Returns:
            Integer value or default
        """
        value = self._config.get(key)
        if value is None:
            return default
        
        if isinstance(value, int):
            return value
        
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self._config[key] = value


def create_config_provider(provider_type: Optional[str] = None) -> ConfigProvider:
    """Factory method to create a configuration provider.
    
    Args:
        provider_type: Type of provider to create ("env", "static", or None for auto-detect)
                      If None, uses environment variable CONFIG_PROVIDER_TYPE or defaults to "env"
    
    Returns:
        ConfigProvider instance
    """
    if provider_type is None:
        provider_type = os.environ.get("CONFIG_PROVIDER_TYPE", "env")
    
    provider_type = provider_type.lower()
    
    if provider_type == "env":
        return EnvConfigProvider()
    elif provider_type == "static":
        return StaticConfigProvider()
    else:
        # Default to environment provider
        return EnvConfigProvider()
