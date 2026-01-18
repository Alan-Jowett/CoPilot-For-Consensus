# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema-driven configuration loader with validation."""

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


class ConfigProvider(ABC):
    """Abstract base class for configuration providers."""

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value."""
        raise NotImplementedError

    @abstractmethod
    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get a boolean configuration value."""
        raise NotImplementedError

    @abstractmethod
    def get_int(self, key: str, default: int = 0) -> int:
        """Get an integer configuration value."""
        raise NotImplementedError


class EnvConfigProvider(ConfigProvider):
    """Configuration provider that reads from environment variables."""

    def __init__(self, environ: dict[str, str] | None = None):
        self._environ = environ if environ is not None else os.environ

    def get(self, key: str, default: Any = None) -> Any:
        return self._environ.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._environ.get(key)
        if value is None:
            return default

        value_lower = value.lower()
        if value_lower in ("true", "1", "yes", "on"):
            return True
        if value_lower in ("false", "0", "no", "off"):
            return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._environ.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except ValueError:
            return default


class StaticConfigProvider(ConfigProvider):
    """Configuration provider that reads from a static dictionary."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config or {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        value = self._config.get(key)
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value_lower = value.lower()
            if value_lower in ("true", "1", "yes", "on"):
                return True
            if value_lower in ("false", "0", "no", "off"):
                return False
        return default

    def get_int(self, key: str, default: int = 0) -> int:
        value = self._config.get(key)
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default


def _resolve_schema_directory(schema_dir: str | None = None) -> str:
    """Resolve schema directory path.

    Args:
        schema_dir: Optional explicit schema directory path

    Returns:
        Resolved schema directory path
    """
    if schema_dir is not None:
        return schema_dir

    # First check environment variable
    schema_dir_env = os.environ.get("SCHEMA_DIR")
    if schema_dir_env is not None:
        return schema_dir_env

    # Try common locations relative to current working directory
    cwd = os.getcwd()
    possible_dirs: list[str] = []

    for base in (cwd, os.path.join(cwd, "..")):
        possible_dirs.append(os.path.join(base, "docs", "schemas", "configs"))

    # Also search upward from this module's location (more robust for tests)
    try:
        from pathlib import Path

        here = Path(__file__).resolve()
        for parent in here.parents:
            possible_dirs.append(str(parent / "docs" / "schemas" / "configs"))
    except Exception:
        # Fall back to cwd-based resolution
        pass

    for d in possible_dirs:
        if os.path.exists(d):
            return d

    # Default to docs/schemas/configs if nothing found
    return os.path.join(cwd, "docs", "schemas", "configs")


def _parse_semver(version: str) -> tuple[int, int, int]:
    """Parse semver string into tuple of ints.

    Args:
        version: Version string in semver format (e.g., "1.2.3")

    Returns:
        Tuple of (major, minor, patch) version numbers

    Raises:
        ValueError: If version string is not valid semver
    """
    if not version:
        raise ValueError("Version string cannot be empty")

    # Ensure we can split the version string; this also validates the type
    try:
        parts = version.split(".")
    except AttributeError as exc:
        raise ValueError(
            f"Version must be a string in 'major.minor.patch' format, got {type(version).__name__!r}"
        ) from exc

    if len(parts) < 3:
        raise ValueError(f"Version must have at least 3 components in 'major.minor.patch' format: {version!r}")

    labels = ("major", "minor", "patch")
    numeric_parts = []
    for index, label in enumerate(labels):
        part = parts[index]
        if not part.isdigit():
            raise ValueError(f"Version {label} component must be an integer, got {part!r} in {version!r}")
        numeric_parts.append(int(part))

    major, minor, patch = numeric_parts
    return (major, minor, patch)


def _is_version_compatible(service_version: str, min_required_version: str) -> bool:
    """Check if service version is compatible with minimum required version.

    Args:
        service_version: Current service version (semver format)
        min_required_version: Minimum required version (semver format)

    Returns:
        True if service version >= min required version, False otherwise

    Note:
        Returns True if versions cannot be parsed (permissive for testing)
    """
    try:
        service_parts = _parse_semver(service_version)
        min_parts = _parse_semver(min_required_version)
        return service_parts >= min_parts
    except ValueError:
        # Be permissive if versions can't be parsed (for testing/dev)
        return True


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""

    pass


class ConfigSchemaError(Exception):
    """Exception raised when schema is invalid or missing."""

    pass


@dataclass
class FieldSpec:
    """Specification for a single configuration field.

    env_var may be a single string or a list of strings (aliases). When a list
    is provided for env_var, the loader will resolve the first variable that is
    present in the environment, falling back to the first item if none are set.
    """

    name: str
    field_type: str  # "string", "int", "bool", "float", "object", "array"
    required: bool = False
    default: Any = None
    source: str = "env"  # "env", "document_store", "static", "secret"
    env_var: Any = None
    doc_store_path: str | None = None
    secret_name: str | None = None
    description: str | None = None
    nested_schema: dict[str, "FieldSpec"] | None = None


@dataclass
class ConfigSchema:
    """Configuration schema for a microservice."""

    service_name: str
    fields: dict[str, FieldSpec] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: str | None = None
    min_service_version: str | None = None
    service_settings: dict[str, FieldSpec] = field(default_factory=dict)
    adapters_schema: dict[str, str] = field(default_factory=dict)  # adapter_type -> schema file path

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigSchema":
        """Create ConfigSchema from dictionary.

        Args:
            data: Schema data as dictionary

        Returns:
            ConfigSchema instance
        """
        service_name = data.get("service_name", "unknown")
        metadata = data.get("metadata", {})

        # Support both 'fields' (old style) and 'service_settings' (new style)
        fields_data = data.get("service_settings") or data.get("fields", {})
        schema_version = data.get("schema_version")
        min_service_version = data.get("min_service_version")

        fields = {}
        for field_name, field_data in fields_data.items():
            fields[field_name] = cls._parse_field_spec(field_name, field_data)

        # Parse adapters section (new style)
        adapters_schema = {}
        adapters_data = data.get("adapters", {})
        for adapter_name, adapter_info in adapters_data.items():
            if isinstance(adapter_info, dict) and "$ref" in adapter_info:
                adapters_schema[adapter_name] = adapter_info["$ref"]

        return cls(
            service_name=service_name,
            fields=fields,
            metadata=metadata,
            schema_version=schema_version,
            min_service_version=min_service_version,
            service_settings=fields,  # Keep service_settings in sync with fields
            adapters_schema=adapters_schema,
        )

    @classmethod
    def _parse_field_spec(cls, name: str, data: dict[str, Any]) -> FieldSpec:
        """Parse a field specification from dictionary.

        Args:
            name: Field name
            data: Field specification data

        Returns:
            FieldSpec instance
        """
        nested_schema = None
        if data.get("type") == "object" and "properties" in data:
            nested_schema = {}
            for prop_name, prop_data in data["properties"].items():
                nested_schema[prop_name] = cls._parse_field_spec(prop_name, prop_data)

        # Handle storage_collection as doc_store_path for storage sources
        doc_store_path = data.get("doc_store_path")
        if data.get("source") == "storage" and not doc_store_path:
            doc_store_path = data.get("storage_collection")

        return FieldSpec(
            name=name,
            field_type=data.get("type", "string"),
            required=data.get("required", False),
            default=data.get("default"),
            source=data.get("source", "env"),
            env_var=data.get("env_var"),
            doc_store_path=doc_store_path,
            secret_name=data.get("secret_name"),
            description=data.get("description"),
            nested_schema=nested_schema,
        )

    @classmethod
    def from_json_file(cls, filepath: str) -> "ConfigSchema":
        """Load schema from JSON file.

        Args:
            filepath: Path to JSON schema file

        Returns:
            ConfigSchema instance

        Raises:
            ConfigSchemaError: If schema file is invalid or missing
        """
        if not os.path.exists(filepath):
            raise ConfigSchemaError(f"Schema file not found: {filepath}")

        try:
            with open(filepath) as f:
                data = json.load(f)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ConfigSchemaError(f"Invalid JSON in schema file {filepath}: {e}")
        except Exception as e:
            raise ConfigSchemaError(f"Error loading schema from {filepath}: {e}")


class SchemaConfigLoader:
    """Loads and validates configuration based on schema."""

    def __init__(
        self,
        schema: ConfigSchema,
        env_provider: ConfigProvider | None = None,
        static_provider: StaticConfigProvider | None = None,
        secret_provider: ConfigProvider | None = None,
    ):
        """Initialize the schema config loader.

        Args:
            schema: Configuration schema
            env_provider: Environment variable provider
            static_provider: Static/hardcoded provider
            secret_provider: Secret provider (from copilot_secrets)
        """
        self.schema = schema
        self.env_provider = env_provider or EnvConfigProvider()
        self.static_provider = static_provider
        self.secret_provider = secret_provider

    def load(self) -> dict[str, Any]:
        """Load and validate configuration based on schema.

        Returns:
            Validated configuration dictionary

        Raises:
            ConfigValidationError: If required fields are missing or validation fails
        """
        config = {}
        errors = []

        for field_name, field_spec in self.schema.fields.items():
            try:
                value = self._load_field(field_spec)
                config[field_name] = value
            except Exception as e:
                if field_spec.required:
                    errors.append(f"{field_name}: {str(e)}")
                else:
                    # Use default for optional fields
                    config[field_name] = field_spec.default

        if errors:
            raise ConfigValidationError(
                f"Configuration validation failed for {self.schema.service_name}:\n"
                + "\n".join(f"  - {err}" for err in errors)
            )

        return config

    def _load_field(self, field_spec: FieldSpec) -> Any:
        """Load a single field value based on its specification.

        Args:
            field_spec: Field specification

        Returns:
            Field value

        Raises:
            ConfigValidationError: If required field is missing
        """
        # Get the appropriate provider
        provider = self._get_provider(field_spec.source)

        if provider is None:
            if field_spec.required:
                raise ConfigValidationError(
                    f"Provider '{field_spec.source}' not available for required field '{field_spec.name}'"
                )
            return field_spec.default

        # Get the key to use based on source
        key = self._get_key_for_source(field_spec)

        # Load the value
        if field_spec.field_type == "bool":
            value = provider.get_bool(key, field_spec.default if field_spec.default is not None else False)
        elif field_spec.field_type == "int":
            value = provider.get_int(key, field_spec.default if field_spec.default is not None else 0)
        elif field_spec.field_type == "float":
            raw_value = provider.get(key)
            if raw_value is None:
                value = field_spec.default
            else:
                try:
                    value = float(raw_value)
                except (ValueError, TypeError):
                    value = field_spec.default
        elif field_spec.field_type == "object":
            value = provider.get(key, field_spec.default)
            if value is None and field_spec.nested_schema:
                # Try to load nested fields
                value = self._load_nested_object(field_spec.nested_schema, provider, key)
        else:  # string or array
            value = provider.get(key, field_spec.default)

        # Validate required fields
        if field_spec.required and value is None:
            raise ConfigValidationError(
                f"Required field '{field_spec.name}' is missing (source: {field_spec.source}, key: {key})"
            )

        return value

    def _load_nested_object(
        self, nested_schema: dict[str, FieldSpec], provider: ConfigProvider, parent_key: str
    ) -> dict[str, Any]:
        """Load a nested object configuration.

        Args:
            nested_schema: Nested field specifications
            provider: Configuration provider
            parent_key: Parent key for nested fields

        Returns:
            Nested configuration dictionary
        """
        del provider
        obj = {}
        for field_name, field_spec in nested_schema.items():
            nested_key = f"{parent_key}.{field_name}" if parent_key else field_name

            # Update field spec with nested key
            nested_field_spec = FieldSpec(
                name=field_spec.name,
                field_type=field_spec.field_type,
                required=field_spec.required,
                default=field_spec.default,
                source=field_spec.source,
                env_var=f"{parent_key}_{field_name}".upper() if not field_spec.env_var else field_spec.env_var,
                doc_store_path=nested_key if not field_spec.doc_store_path else field_spec.doc_store_path,
            )

            try:
                obj[field_name] = self._load_field(nested_field_spec)
            except ConfigValidationError:
                if field_spec.required:
                    raise
                obj[field_name] = field_spec.default

        return obj

    def _get_provider(self, source: str) -> ConfigProvider | None:
        """Get the appropriate provider for a source.

        Args:
            source: Source type

        Returns:
            ConfigProvider instance or None
        """
        if source == "env":
            return self.env_provider
        elif source == "static":
            return self.static_provider
        elif source == "secret":
            return self.secret_provider
        else:
            return None

    def _get_key_for_source(self, field_spec: FieldSpec) -> str:
        """Get the key to use for a field based on its source.

        Args:
            field_spec: Field specification

        Returns:
            Key string
        """
        if field_spec.source == "env":
            env_key = field_spec.env_var
            # Support alias list: search for the first variable that exists
            if isinstance(env_key, list):
                for candidate in env_key:
                    # Only EnvConfigProvider supports direct environment lookup
                    # Fallback: treat any non-empty value as present
                    if self.env_provider and self.env_provider.get(candidate) is not None:
                        return candidate
                # None found set; fall back to the first alias for defaulting
                return env_key[0] if env_key else field_spec.name.upper()
            # Single string or None
            return env_key or field_spec.name.upper()
        elif field_spec.source == "secret":
            # For secrets, use secret_name if provided, otherwise use field name
            return getattr(field_spec, "secret_name", None) or field_spec.name
        else:
            return field_spec.name


def _load_config(
    service_name: str,
    schema_dir: str | None = None,
    env_provider: ConfigProvider | None = None,
    static_provider: StaticConfigProvider | None = None,
    secret_provider: ConfigProvider | None = None,
    schema: Optional["ConfigSchema"] = None,
) -> dict[str, Any]:
    """Load and validate configuration for a service (internal function).

    INTERNAL API: Use load_typed_config() instead for type-safe, validated config loading.
    This function is internal and should not be called directly by services.

    This is the internal entry point for schema-driven configuration loading.
    Schemas are loaded from local disk only. Storage-backed configuration
    values must be loaded and merged separately by the caller.

    Args:
        service_name: Name of the service (e.g., "ingestion", "parsing")
        schema_dir: Directory containing schema files (defaults to ./schemas)
        env_provider: Optional custom environment provider
        static_provider: Optional static provider
        secret_provider: Optional secret provider (from copilot_secrets)
        schema: Optional pre-loaded ConfigSchema (avoids redundant I/O if already loaded)

    Returns:
        Validated configuration dictionary

    Raises:
        ConfigSchemaError: If schema is missing or invalid
        ConfigValidationError: If configuration validation fails
    """
    # Load schema from disk if not provided
    if schema is None:
        schema_dir_path = _resolve_schema_directory(schema_dir)

        # Service schemas typically live under <schema_dir>/services/<service>.json,
        # but keep a fallback to <schema_dir>/<service>.json for backward compatibility.
        schema_path = os.path.join(schema_dir_path, "services", f"{service_name}.json")
        if not os.path.exists(schema_path):
            fallback_path = os.path.join(schema_dir_path, f"{service_name}.json")
            if os.path.exists(fallback_path):
                schema_path = fallback_path

        schema = ConfigSchema.from_json_file(schema_path)

    # Validate schema version if min_service_version is specified
    if schema.min_service_version:
        service_version = os.environ.get("SERVICE_VERSION", "0.0.0")
        if not _is_version_compatible(service_version, schema.min_service_version):
            raise ConfigSchemaError(
                f"Service version {service_version} is not compatible with "
                f"minimum required schema version {schema.min_service_version}"
            )

    # Create loader (no document store coupling)
    loader = SchemaConfigLoader(
        schema=schema,
        env_provider=env_provider,
        static_provider=static_provider,
        secret_provider=secret_provider,
    )

    # Load and validate
    return loader.load()
