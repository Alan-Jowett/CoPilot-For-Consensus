# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Typed configuration wrapper for services."""

import os
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

    def __init__(self, config_dict: Dict[str, Any], schema_version: Optional[str] = None, 
                 min_service_version: Optional[str] = None):
        """Initialize typed config wrapper.
        
        Args:
            config_dict: Configuration dictionary from _load_config()
            schema_version: Schema version string (semver format)
            min_service_version: Minimum service version required (semver format)
        """
        object.__setattr__(self, '_config', config_dict)
        object.__setattr__(self, '_schema_version', schema_version)
        object.__setattr__(self, '_min_service_version', min_service_version)
    
    def get_schema_version(self) -> Optional[str]:
        """Get the schema version.
        
        Returns:
            Schema version string or None
        """
        return object.__getattribute__(self, '_schema_version')
    
    def get_min_service_version(self) -> Optional[str]:
        """Get the minimum service version.
        
        Returns:
            Minimum service version string or None
        """
        return object.__getattribute__(self, '_min_service_version')

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
    
    Automatically integrates with the secrets system:
    - Reads secret_provider_type from service config (e.g., "local", "vault")
    - Reads secrets_base_path from service config
    - Creates secret provider based on config and transparently merges secrets
    
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
    from .schema_loader import _load_config, ConfigSchema
    import os
    
    # Try to import secrets support (optional)
    try:
        from copilot_secrets import create_secret_provider
        from .secret_provider import SecretConfigProvider
        secrets_available = True
    except ImportError:
        secrets_available = False
    
    # Load the schema to get version information
    schema_dir_path = schema_dir
    if schema_dir_path is None:
        # First check environment variable
        schema_dir_path = os.environ.get("SCHEMA_DIR")
        
        if schema_dir_path is None:
            # Try common locations relative to current working directory
            possible_dirs = [
                os.path.join(os.getcwd(), "documents", "schemas", "configs"),
                os.path.join(os.getcwd(), "..", "documents", "schemas", "configs"),
            ]
            
            for d in possible_dirs:
                if os.path.exists(d):
                    schema_dir_path = d
                    break
            
            # Default to documents/schemas/configs if nothing found
            if schema_dir_path is None:
                schema_dir_path = os.path.join(os.getcwd(), "documents", "schemas", "configs")
    
    schema_path = os.path.join(schema_dir_path, f"{service_name}.json")
    schema = ConfigSchema.from_json_file(schema_path)
    
    # First pass: load config without secrets to read secret provider config from fields
    initial_config = _load_config(service_name, schema_dir=schema_dir, **kwargs)
    
    # Read secret provider configuration from config fields
    provider_type = initial_config.get("secret_provider_type", "local")
    base_path = initial_config.get("secrets_base_path", "/run/secrets")
    
    secret_provider = None
    if provider_type and secrets_available:
        try:
            secret_provider_instance = create_secret_provider(
                provider_type=provider_type,
                base_path=base_path,
            )
            secret_provider = SecretConfigProvider(secret_provider=secret_provider_instance)
        except Exception as e:
            # If secret provider fails, continue without it
            import sys
            print(f"[DEBUG typed_config] Failed to create secret provider: {e}", file=sys.stderr)
            secret_provider = None
    
    # Second pass: reload config with secret provider if one was created
    if secret_provider:
        config_dict = _load_config(
            service_name,
            schema_dir=schema_dir,
            secret_provider=secret_provider,
            **kwargs
        )
    else:
        config_dict = initial_config
    
    return TypedConfig(
        config_dict,
        schema_version=schema.schema_version,
        min_service_version=schema.min_service_version
    )
