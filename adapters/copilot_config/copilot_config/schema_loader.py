# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Schema-driven configuration loader with validation."""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .config import ConfigProvider, EnvConfigProvider, StaticConfigProvider
from .providers import YamlConfigProvider, DocStoreConfigProvider


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    pass


class ConfigSchemaError(Exception):
    """Exception raised when schema is invalid or missing."""
    pass


@dataclass
class FieldSpec:
    """Specification for a single configuration field."""
    name: str
    field_type: str  # "string", "int", "bool", "float", "object", "array"
    required: bool = False
    default: Any = None
    source: str = "env"  # "env", "yaml", "document_store", "static"
    env_var: Optional[str] = None
    yaml_path: Optional[str] = None
    doc_store_path: Optional[str] = None
    description: Optional[str] = None
    nested_schema: Optional[Dict[str, 'FieldSpec']] = None


@dataclass
class ConfigSchema:
    """Configuration schema for a microservice."""
    service_name: str
    fields: Dict[str, FieldSpec] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConfigSchema':
        """Create ConfigSchema from dictionary.
        
        Args:
            data: Schema data as dictionary
            
        Returns:
            ConfigSchema instance
        """
        service_name = data.get("service_name", "unknown")
        metadata = data.get("metadata", {})
        fields_data = data.get("fields", {})
        
        fields = {}
        for field_name, field_data in fields_data.items():
            fields[field_name] = cls._parse_field_spec(field_name, field_data)
        
        return cls(service_name=service_name, fields=fields, metadata=metadata)

    @classmethod
    def _parse_field_spec(cls, name: str, data: Dict[str, Any]) -> FieldSpec:
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
            yaml_path=data.get("yaml_path"),
            doc_store_path=doc_store_path,
            description=data.get("description"),
            nested_schema=nested_schema,
        )

    @classmethod
    def from_json_file(cls, filepath: str) -> 'ConfigSchema':
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
            with open(filepath, "r") as f:
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
        env_provider: Optional[ConfigProvider] = None,
        yaml_provider: Optional[YamlConfigProvider] = None,
        doc_store_provider: Optional[DocStoreConfigProvider] = None,
        static_provider: Optional[StaticConfigProvider] = None,
    ):
        """Initialize the schema config loader.
        
        Args:
            schema: Configuration schema
            env_provider: Environment variable provider
            yaml_provider: YAML file provider
            doc_store_provider: Document store provider
            static_provider: Static/hardcoded provider
        """
        self.schema = schema
        self.env_provider = env_provider or EnvConfigProvider()
        self.yaml_provider = yaml_provider
        self.doc_store_provider = doc_store_provider
        self.static_provider = static_provider

    def load(self) -> Dict[str, Any]:
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
                f"Configuration validation failed for {self.schema.service_name}:\n" +
                "\n".join(f"  - {err}" for err in errors)
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
        # Special handling for storage source with list type
        if field_spec.source == "storage" and field_spec.field_type == "list":
            return self._load_storage_collection(field_spec)
        
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

    def _load_storage_collection(self, field_spec: FieldSpec) -> list:
        """Load all documents from a storage collection.
        
        Args:
            field_spec: Field specification for storage source
            
        Returns:
            List of documents from collection
        """
        if self.doc_store_provider is None:
            return field_spec.default or []
        
        try:
            collection_name = field_spec.doc_store_path or field_spec.name
            # Use the public interface to query documents
            documents = self.doc_store_provider.query_documents_from_collection(
                collection_name=collection_name
            )
            return documents if documents else field_spec.default or []
        except Exception:
            # If query fails, return default
            return field_spec.default or []

    def _load_nested_object(
        self, nested_schema: Dict[str, FieldSpec], provider: ConfigProvider, parent_key: str
    ) -> Dict[str, Any]:
        """Load a nested object configuration.
        
        Args:
            nested_schema: Nested field specifications
            provider: Configuration provider
            parent_key: Parent key for nested fields
            
        Returns:
            Nested configuration dictionary
        """
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
                yaml_path=nested_key if not field_spec.yaml_path else field_spec.yaml_path,
                doc_store_path=nested_key if not field_spec.doc_store_path else field_spec.doc_store_path,
            )
            
            try:
                obj[field_name] = self._load_field(nested_field_spec)
            except ConfigValidationError:
                if field_spec.required:
                    raise
                obj[field_name] = field_spec.default
        
        return obj

    def _get_provider(self, source: str) -> Optional[ConfigProvider]:
        """Get the appropriate provider for a source.
        
        Args:
            source: Source type
            
        Returns:
            ConfigProvider instance or None
        """
        if source == "env":
            return self.env_provider
        elif source == "yaml":
            return self.yaml_provider
        elif source == "document_store" or source == "storage":
            return self.doc_store_provider
        elif source == "static":
            return self.static_provider
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
            return field_spec.env_var or field_spec.name.upper()
        elif field_spec.source == "yaml":
            return field_spec.yaml_path or field_spec.name
        elif field_spec.source == "document_store" or field_spec.source == "storage":
            return field_spec.doc_store_path or field_spec.name
        else:
            return field_spec.name


def load_config(
    service_name: str,
    schema_dir: Optional[str] = None,
    env_provider: Optional[ConfigProvider] = None,
    yaml_provider: Optional[YamlConfigProvider] = None,
    doc_store_provider: Optional[DocStoreConfigProvider] = None,
    static_provider: Optional[StaticConfigProvider] = None,
) -> Dict[str, Any]:
    """Load and validate configuration for a service.
    
    This is the main entry point for schema-driven configuration loading.
    
    Args:
        service_name: Name of the service (e.g., "ingestion", "parsing")
        schema_dir: Directory containing schema files (defaults to ./schemas)
        env_provider: Optional custom environment provider
        yaml_provider: Optional YAML provider
        doc_store_provider: Optional document store provider
        static_provider: Optional static provider
        
    Returns:
        Validated configuration dictionary
        
    Raises:
        ConfigSchemaError: If schema is missing or invalid
        ConfigValidationError: If configuration validation fails
        
    Example:
        >>> config = load_config("ingestion")
        >>> rabbitmq_url = config["rabbitmq_url"]
    """
    # Determine schema directory
    if schema_dir is None:
        # First check environment variable
        schema_dir = os.environ.get("SCHEMA_DIR")
        
        if schema_dir is None:
            # Try common locations relative to current working directory
            possible_dirs = [
                os.path.join(os.getcwd(), "documents", "schemas", "configs"),
                os.path.join(os.getcwd(), "..", "documents", "schemas", "configs"),
            ]
            
            for d in possible_dirs:
                if os.path.exists(d):
                    schema_dir = d
                    break
            
            # Default to documents/schemas/configs if nothing found
            if schema_dir is None:
                schema_dir = os.path.join(os.getcwd(), "documents", "schemas", "configs")
    
    # Load schema
    schema_path = os.path.join(schema_dir, f"{service_name}.json")
    schema = ConfigSchema.from_json_file(schema_path)
    
    # If no doc_store_provider but schema needs storage, create one automatically
    if doc_store_provider is None and any(f.source == "storage" for f in schema.fields.values()):
        try:
            from copilot_storage import create_document_store
            doc_store = create_document_store()
            if doc_store.connect():
                doc_store_provider = DocStoreConfigProvider(doc_store)
            else:
                # If connection fails, log warning and fall back to no doc_store_provider
                logger = __import__('logging').getLogger(__name__)
                logger.warning(
                    "Document store connection failed for schema-based configuration. "
                    "Storage-backed configuration fields will use defaults. "
                    "Service: %s", service_name
                )
                # Required fields will fail validation if storage is needed
                pass
        except Exception as e:
            # If document store is unavailable, log warning and continue without it
            logger = __import__('logging').getLogger(__name__)
            logger.warning(
                "Document store unavailable for schema-based configuration. "
                "Storage-backed configuration fields will use defaults. "
                "Service: %s, Error: %s", service_name, str(e)
            )
            # Required fields will fail validation if storage is needed
            pass
    
    # Create loader
    loader = SchemaConfigLoader(
        schema=schema,
        env_provider=env_provider,
        yaml_provider=yaml_provider,
        doc_store_provider=doc_store_provider,
        static_provider=static_provider,
    )
    
    # Load and validate
    return loader.load()
