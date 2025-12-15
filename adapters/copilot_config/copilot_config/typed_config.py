# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Typed configuration wrapper for services."""

from typing import Any, Dict, Optional


class TypedConfig:
    """Typed configuration wrapper that provides attribute-only access to config values.
    
    This class wraps the configuration dictionary from _load_config()
    and provides ATTRIBUTE-ONLY access to configuration values.
    
    Dictionary-style access is intentionally NOT supported to enable static
    type checking, IDE autocomplete, and verification that all accessed keys
    are actually defined in the schema.
    
    Example:
        >>> config = load_typed_config("ingestion")
        >>> print(config.message_bus_host)  # ✓ Attribute style
        'messagebus'
        >>> print(config.message_bus_port)  # ✓ Works
        5672
        >>> print(config["host"])  # ✗ Will raise AttributeError
        AttributeError: TypedConfig does not support dict-style access
    """

    def __init__(self, config_dict: Dict[str, Any]):
        """Initialize typed config wrapper.
        
        Args:
            config_dict: Configuration dictionary from _load_config()
        """
        object.__setattr__(self, '_config', config_dict)

    def __getattr__(self, name: str) -> Any:
        """Get configuration value by attribute name only.
        
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
        
        config = object.__getattribute__(self, '_config')
        if name not in config:
            raise AttributeError(
                f"Configuration key '{name}' not found. "
                f"Available keys: {sorted(config.keys())}"
            )
        
        return config[name]

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent modification of configuration at runtime.
        
        Configuration should be immutable after loading.
        """
        if name == '_config':
            object.__setattr__(self, name, value)
        else:
            raise AttributeError(
                f"Cannot modify configuration. '{name}' is read-only. "
                "Configuration is immutable after loading."
            )

    def __getitem__(self, key: str) -> Any:
        """Explicitly block dictionary-style access.
        
        This ensures all config access goes through attributes for better
        verification and static analysis.
        """
        raise TypeError(
            f"TypedConfig does not support dict-style access (config['{key}']). "
            f"Use attribute-style instead: config.{key}"
        )

    def __repr__(self) -> str:
        """String representation."""
        config = object.__getattribute__(self, '_config')
        return f"TypedConfig({config!r})"
    
    def __dir__(self) -> list:
        """Show available configuration keys for IDE autocomplete."""
        config = object.__getattribute__(self, '_config')
        return sorted(config.keys())


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
