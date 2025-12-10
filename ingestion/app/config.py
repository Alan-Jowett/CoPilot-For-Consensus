# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import os
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path


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
    retry_max_attempts: int = 3
    retry_backoff_seconds: int = 60
    sources: List[SourceConfig] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "IngestionConfig":
        """Load configuration from environment variables."""
        return cls(
            storage_path=os.getenv("STORAGE_PATH", "/data/raw_archives"),
            message_bus_host=os.getenv("MESSAGE_BUS_HOST", "messagebus"),
            message_bus_port=int(os.getenv("MESSAGE_BUS_PORT", "5672")),
            message_bus_user=os.getenv("MESSAGE_BUS_USER", "guest"),
            message_bus_password=os.getenv("MESSAGE_BUS_PASSWORD", "guest"),
            message_bus_type=os.getenv("MESSAGE_BUS_TYPE", "rabbitmq"),
            ingestion_schedule_cron=os.getenv("INGESTION_SCHEDULE_CRON", "0 */6 * * *"),
            blob_storage_enabled=os.getenv("BLOB_STORAGE_ENABLED", "false").lower() == "true",
            blob_storage_connection_string=os.getenv("BLOB_STORAGE_CONNECTION_STRING"),
            blob_storage_container=os.getenv("BLOB_STORAGE_CONTAINER", "raw-archives"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            retry_max_attempts=int(os.getenv("RETRY_MAX_ATTEMPTS", "3")),
            retry_backoff_seconds=int(os.getenv("RETRY_BACKOFF_SECONDS", "60")),
        )

    @classmethod
    def from_yaml_file(cls, filepath: str) -> "IngestionConfig":
        """Load configuration from YAML file (config.yaml)."""
        try:
            import yaml
        except ImportError:
            raise ImportError("PyYAML required for YAML configuration. Install with: pip install pyyaml")
        
        config = cls.from_env()
        
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
