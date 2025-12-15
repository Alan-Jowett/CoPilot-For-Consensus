# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Typed configuration wrapper for services."""

from typing import Any, Dict, Optional


class TypedConfig:
    """Typed configuration wrapper that provides attribute access to config values.
    
    This class wraps the configuration dictionary returned by load_config()
    and provides attribute-style access to configuration values.
    
    Example:
        >>> config_dict = load_config("ingestion")
        >>> config = TypedConfig(config_dict)
        >>> print(config.message_bus_host)
        'messagebus'
        >>> print(config.message_bus_port)
        5672
    """

    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize typed config wrapper.
        
        Args:
            config_dict: Configuration dictionary from load_config()
        """
        self._config = config_dict

    def __getattr__(self, name: str) -> Any:
        """Get configuration value by attribute name.
        
        Args:
            name: Configuration key
            
        Returns:
            Configuration value
            
        Raises:
            AttributeError: If configuration key does not exist
        """
        if name.startswith('_'):
            # Block access to private attributes
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
        
        if name not in self._config:
            raise AttributeError(f"Configuration key '{name}' not found")
        
        return self._config[name]

    def __getitem__(self, key: str) -> Any:
        """Get configuration value by key (dict-style access).
        
        Args:
            key: Configuration key
            
        Returns:
            Configuration value
            
        Raises:
            KeyError: If configuration key does not exist
        """
        return self._config[key]

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self._config.get(key, default)

    def to_dict(self) -> Dict[str, Any]:
        """Get configuration as dictionary.
        
        Returns:
            Configuration dictionary
        """
        return self._config.copy()

    def __repr__(self) -> str:
        """String representation."""
        return f"TypedConfig({self._config!r})"

    def __contains__(self, key: str) -> bool:
        """Check if configuration key exists.
        
        Args:
            key: Configuration key
            
        Returns:
            True if key exists, False otherwise
        """
        return key in self._config


def load_typed_config(
    service_name: str,
    schema_dir: Optional[str] = None,
    **kwargs
) -> TypedConfig:
    """Load and validate configuration, returning a typed config object.
    
    This is the ONLY recommended way to load configuration in services.
    It ensures all configuration is validated against the service schema,
    providing type safety and compile-time guarantees.
    
    Args:
        service_name: Name of the service
        schema_dir: Directory containing schema files
        **kwargs: Additional arguments to pass to internal loader
        
    Returns:
        TypedConfig instance with validated configuration
        
    Raises:
        ConfigSchemaError: If schema is missing or invalid
        ConfigValidationError: If configuration validation fails
        
    Example:
        >>> config = load_typed_config("ingestion")
        >>> print(config.message_bus_host)
        'messagebus'
    """
    from .schema_loader import _load_config
    
    config_dict = _load_config(service_name, schema_dir=schema_dir, **kwargs)
    return TypedConfig(config_dict)
