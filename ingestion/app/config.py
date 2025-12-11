# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Dict, Any

import yaml
from copilot_config import ConfigProvider, create_config_provider


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
    def from_env(cls, config_provider: Optional[ConfigProvider] = None) -> "IngestionConfig":
        """Load configuration from environment variables.
        
        Args:
            config_provider: ConfigProvider to use (defaults to EnvConfigProvider)
        """
        if config_provider is None:
            config_provider = create_config_provider()
        
        return cls(
            storage_path=config_provider.get("STORAGE_PATH", "/data/raw_archives"),
            message_bus_host=config_provider.get("MESSAGE_BUS_HOST", "messagebus"),
            message_bus_port=config_provider.get_int("MESSAGE_BUS_PORT", 5672),
            message_bus_user=config_provider.get("MESSAGE_BUS_USER", "guest"),
            message_bus_password=config_provider.get("MESSAGE_BUS_PASSWORD", "guest"),
            message_bus_type=config_provider.get("MESSAGE_BUS_TYPE", "rabbitmq"),
            ingestion_schedule_cron=config_provider.get("INGESTION_SCHEDULE_CRON", "0 */6 * * *"),
            blob_storage_enabled=config_provider.get_bool("BLOB_STORAGE_ENABLED", False),
            blob_storage_connection_string=config_provider.get("BLOB_STORAGE_CONNECTION_STRING"),
            blob_storage_container=config_provider.get("BLOB_STORAGE_CONTAINER", "raw-archives"),
            log_level=config_provider.get("LOG_LEVEL", "INFO"),
            log_type=config_provider.get("LOG_TYPE", "stdout"),
            logger_name=config_provider.get("LOG_NAME", "ingestion-service"),
            metrics_backend=config_provider.get("METRICS_BACKEND", "noop"),
            retry_max_attempts=config_provider.get_int("RETRY_MAX_ATTEMPTS", 3),
            retry_backoff_seconds=config_provider.get_int("RETRY_BACKOFF_SECONDS", 60),
            error_reporter_type=config_provider.get("ERROR_REPORTER_TYPE", "console"),
            sentry_dsn=config_provider.get("SENTRY_DSN"),
            sentry_environment=config_provider.get("SENTRY_ENVIRONMENT", "production"),
        )

    @classmethod
    def from_yaml_file(cls, filepath: str, config_provider: Optional[ConfigProvider] = None) -> "IngestionConfig":
        """Load configuration from YAML file (config.yaml).
        
        Args:
            filepath: Path to YAML configuration file
            config_provider: ConfigProvider to use for env vars (defaults to EnvConfigProvider)
        """
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML configuration. Install with: pip install pyyaml")
        
        config = cls.from_env(config_provider)
        
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
