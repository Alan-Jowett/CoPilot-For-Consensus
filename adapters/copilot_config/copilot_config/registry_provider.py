# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Registry-backed configuration provider with hot-reload support."""

import time
from typing import Any, Callable

import requests

from .base import ConfigProvider


class RegistryConfigProvider(ConfigProvider):
    """Configuration provider that fetches from config registry service.

    Supports hot-reload via TTL-based cache refresh.
    """

    def __init__(
        self,
        registry_url: str,
        service_name: str,
        environment: str = "default",
        cache_ttl_seconds: int = 60,
        timeout_seconds: int = 10,
    ):
        """Initialize registry config provider.

        Args:
            registry_url: Base URL of config registry service (e.g., http://config-registry:8000)
            service_name: Service name to fetch config for
            environment: Environment name (default, dev, staging, prod)
            cache_ttl_seconds: Cache TTL in seconds (default: 60)
            timeout_seconds: Request timeout in seconds (default: 10)
        """
        self.registry_url = registry_url.rstrip("/")
        self.service_name = service_name
        self.environment = environment
        self.cache_ttl_seconds = cache_ttl_seconds
        self.timeout_seconds = timeout_seconds

        self._config_cache: dict[str, Any] | None = None
        self._cache_timestamp: float = 0

    def _fetch_config(self) -> dict[str, Any]:
        """Fetch configuration from registry.

        Returns:
            Configuration dictionary

        Raises:
            requests.RequestException: If fetch fails
        """
        url = f"{self.registry_url}/api/configs/{self.service_name}"
        params = {"environment": self.environment}

        response = requests.get(url, params=params, timeout=self.timeout_seconds)
        response.raise_for_status()

        return response.json()

    def _get_cached_config(self) -> dict[str, Any]:
        """Get cached configuration, refreshing if expired.

        Returns:
            Configuration dictionary
        """
        current_time = time.time()

        # Check if cache is valid
        if self._config_cache is None or (current_time - self._cache_timestamp) > self.cache_ttl_seconds:
            # Refresh cache
            self._config_cache = self._fetch_config()
            self._cache_timestamp = current_time

        return self._config_cache

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        try:
            config = self._get_cached_config()
            return config.get(key, default)
        except Exception:
            # If fetch fails, return default
            return default

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Get boolean configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Boolean configuration value or default
        """
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)

    def get_int(self, key: str, default: int = 0) -> int:
        """Get integer configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Integer configuration value or default
        """
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def get_float(self, key: str, default: float = 0.0) -> float:
        """Get float configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Float configuration value or default
        """
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def refresh(self) -> None:
        """Force cache refresh."""
        self._config_cache = None
        self._cache_timestamp = 0


class ConfigWatcher:
    """Watch for configuration changes and trigger callbacks.

    Polls the registry periodically and calls callback when changes detected.
    """

    def __init__(
        self,
        registry_url: str,
        service_name: str,
        environment: str = "default",
        poll_interval_seconds: int = 30,
        on_change: Callable[[dict[str, Any]], None] | None = None,
    ):
        """Initialize config watcher.

        Args:
            registry_url: Base URL of config registry service
            service_name: Service name to watch
            environment: Environment name
            poll_interval_seconds: Polling interval in seconds (default: 30)
            on_change: Callback function called when config changes
        """
        self.registry_url = registry_url.rstrip("/")
        self.service_name = service_name
        self.environment = environment
        self.poll_interval_seconds = poll_interval_seconds
        self.on_change = on_change

        self._running = False
        self._last_version = 0
        self._last_config: dict[str, Any] | None = None

    def _fetch_config_metadata(self) -> dict[str, Any] | None:
        """Fetch configuration metadata (including version).

        Returns:
            Configuration metadata or None if not found
        """
        try:
            url = f"{self.registry_url}/api/configs/{self.service_name}/history"
            params = {"environment": self.environment, "limit": 1}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            history = response.json()
            if history:
                return history[0]
            return None
        except Exception:
            return None

    def _check_for_changes(self) -> None:
        """Check for configuration changes."""
        metadata = self._fetch_config_metadata()
        if not metadata:
            return

        current_version = metadata.get("version", 0)
        current_config = metadata.get("config_data", {})

        # Check if version changed
        if current_version != self._last_version and self._last_version != 0:
            # Configuration changed
            if self.on_change:
                self.on_change(current_config)

        self._last_version = current_version
        self._last_config = current_config

    def start(self) -> None:
        """Start watching for changes (blocking).

        This method blocks and polls the registry periodically.
        Use in a separate thread or process if needed.
        """
        import signal
        import sys

        def signal_handler(sig, frame):
            self._running = False
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        self._running = True

        # Initial fetch
        self._check_for_changes()

        # Poll loop
        while self._running:
            time.sleep(self.poll_interval_seconds)
            self._check_for_changes()

    def stop(self) -> None:
        """Stop watching."""
        self._running = False
