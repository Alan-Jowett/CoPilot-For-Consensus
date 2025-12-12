# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml
from copilot_config import load_typed_config


@dataclass
class SourceConfig:
    """Configuration for an archive source."""
    name: str
    source_type: str  # "rsync", "imap", "http", "local"
    url: str
    enabled: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    port: Optional[int] = None
    folder: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict) -> "SourceConfig":
        """Create SourceConfig from dictionary, expanding env variables."""
        config_data = data.copy()
        
        # Expand environment variables
        for key in ["username", "password", "url"]:
            if key in config_data and isinstance(config_data[key], str):
                config_data[key] = os.path.expandvars(config_data[key])
        
        # Extract known fields
        known_fields = {"name", "source_type", "url", "enabled", "username", "password", "port", "folder"}
        extra = {k: v for k, v in config_data.items() if k not in known_fields}
        
        config_data["extra"] = extra
        
        # Remove extra fields from main init
        for key in extra:
            del config_data[key]
        
        return cls(**config_data)


@dataclass
class IngestionConfig:
    """Ingestion service configuration."""
    storage_path: str = "/data/raw_archives"
    message_bus_host: str = "messagebus"
    message_bus_port: int = 5672
    message_bus_user: str = "guest"
    message_bus_password: str = "guest"
    message_bus_type: str = "rabbitmq"  # "rabbitmq", "service_bus"
    ingestion_schedule_cron: str = "0 */6 * * *"  # Every 6 hours
    blob_storage_enabled: bool = False
    blob_storage_connection_string: Optional[str] = None
    blob_storage_container: str = "raw-archives"
    log_level: str = "INFO"
    log_type: str = "stdout"
    logger_name: str = "ingestion-service"
    metrics_backend: str = "noop"
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 60
    error_reporter_type: str = "console"  # "console", "silent", "sentry"
    sentry_dsn: Optional[str] = None
    sentry_environment: str = "production"
    sources: List[SourceConfig] = field(default_factory=list)

    @classmethod
    def from_env(cls, schema_path: Optional[str] = None, config_provider: Optional[object] = None) -> "IngestionConfig":
        """Load configuration from environment variables using schema.
        
        Args:
            schema_path: Path to schema file (defaults to standard location)
            config_provider: Backward-compatibility parameter, ignored. Tests may pass this.
        """
        # Load from schema-based environment
        config_obj = load_typed_config("ingestion")

        # Backward compatibility: if a legacy config_provider is supplied, use it to override
        # values expected by older tests (StaticConfigProvider pattern).
        if config_provider is not None:
            # Helper functions guarded by hasattr to support different provider implementations
            def _get(name, default=None):
                if hasattr(config_provider, "get"):
                    try:
                        return config_provider.get(name, default)
                    except Exception:
                        return default
                return default

            def _get_int(name, default=0):
                if hasattr(config_provider, "get_int"):
                    try:
                        return int(config_provider.get_int(name, default))
                    except Exception:
                        return default
                val = _get(name, default)
                try:
                    return int(val)
                except Exception:
                    return default

            def _get_bool(name, default=False):
                if hasattr(config_provider, "get_bool"):
                    try:
                        return bool(config_provider.get_bool(name, default))
                    except Exception:
                        return default
                val = _get(name, default)
                if isinstance(val, bool):
                    return val
                if isinstance(val, str):
                    return val.lower() in ("true", "1", "yes")
                return bool(val)

            # Build overrides from provider
            overrides = {
                "storage_path": _get("STORAGE_PATH", config_obj.storage_path),
                "message_bus_host": _get("MESSAGE_BUS_HOST", config_obj.message_bus_host),
                "message_bus_port": _get_int("MESSAGE_BUS_PORT", config_obj.message_bus_port),
                "message_bus_user": _get("MESSAGE_BUS_USER", config_obj.message_bus_user),
                "message_bus_password": _get("MESSAGE_BUS_PASSWORD", config_obj.message_bus_password),
                "message_bus_type": _get("MESSAGE_BUS_TYPE", config_obj.message_bus_type),
                "ingestion_schedule_cron": _get("INGESTION_SCHEDULE_CRON", config_obj.ingestion_schedule_cron),
                "blob_storage_enabled": _get_bool("BLOB_STORAGE_ENABLED", config_obj.blob_storage_enabled),
                "blob_storage_connection_string": _get("BLOB_STORAGE_CONNECTION_STRING", config_obj.blob_storage_connection_string),
                "blob_storage_container": _get("BLOB_STORAGE_CONTAINER", config_obj.blob_storage_container),
                "log_level": _get("LOG_LEVEL", config_obj.log_level),
                "log_type": _get("LOG_TYPE", config_obj.log_type),
                "logger_name": _get("LOG_NAME", config_obj.logger_name),
                "metrics_backend": _get("METRICS_BACKEND", config_obj.metrics_backend),
                "retry_max_attempts": _get_int("RETRY_MAX_ATTEMPTS", config_obj.retry_max_attempts),
                "retry_backoff_seconds": _get_int("RETRY_BACKOFF_SECONDS", config_obj.retry_backoff_seconds),
                "error_reporter_type": _get("ERROR_REPORTER_TYPE", config_obj.error_reporter_type),
                "sentry_dsn": _get("SENTRY_DSN", config_obj.sentry_dsn),
                "sentry_environment": _get("SENTRY_ENVIRONMENT", config_obj.sentry_environment),
            }

            # Apply overrides onto a new instance
            return cls(**overrides)
        
        return cls(
            storage_path=config_obj.storage_path,
            message_bus_host=config_obj.message_bus_host,
            message_bus_port=config_obj.message_bus_port,
            message_bus_user=config_obj.message_bus_user,
            message_bus_password=config_obj.message_bus_password,
            message_bus_type=config_obj.message_bus_type,
            ingestion_schedule_cron=config_obj.ingestion_schedule_cron,
            blob_storage_enabled=config_obj.blob_storage_enabled,
            blob_storage_connection_string=config_obj.blob_storage_connection_string,
            blob_storage_container=config_obj.blob_storage_container,
            log_level=config_obj.log_level,
            log_type=config_obj.log_type,
            logger_name=config_obj.logger_name,
            metrics_backend=config_obj.metrics_backend,
            retry_max_attempts=config_obj.retry_max_attempts,
            retry_backoff_seconds=config_obj.retry_backoff_seconds,
            error_reporter_type=config_obj.error_reporter_type,
            sentry_dsn=config_obj.sentry_dsn,
            sentry_environment=config_obj.sentry_environment,
        )

    @classmethod
    def from_yaml_file(cls, filepath: str, schema_path: Optional[str] = None, config_provider: Optional[object] = None) -> "IngestionConfig":
        """Load configuration from YAML file (config.yaml).
        
        Args:
            filepath: Path to YAML configuration file
            schema_path: Path to schema file (defaults to standard location)
            config_provider: Backward-compatibility parameter, ignored. Tests may pass this.
        """
        # Backward compatibility: accept and ignore legacy config_provider argument
        _ = config_provider
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML configuration. Install with: pip install pyyaml")
        
        config = cls.from_env(schema_path)
        
        if not os.path.exists(filepath):
            return config
        
        with open(filepath, "r") as f:
            yaml_config = yaml.safe_load(f) or {}
        
        # Load sources from YAML
        if "sources" in yaml_config:
            config.sources = [SourceConfig.from_dict(s) for s in yaml_config["sources"]]
        
        return config

    def get_enabled_sources(self) -> List[SourceConfig]:
        """Get list of enabled sources."""
        return [s for s in self.sources if s.enabled]

    def ensure_storage_path(self) -> None:
        """Create storage path if it doesn't exist."""
        storage_dir = Path(self.storage_path)
        storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Create metadata directory
        metadata_dir = storage_dir / "metadata"
        metadata_dir.mkdir(exist_ok=True)
