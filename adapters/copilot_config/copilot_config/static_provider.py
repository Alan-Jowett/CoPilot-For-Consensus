# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Static/dictionary-backed configuration provider."""

from typing import Any

from .base import ConfigProvider


class StaticConfigProvider(ConfigProvider):
    """Configuration provider with static values (useful for tests)."""

    def __init__(self, config: dict[str, Any] | None = None):
        self._config = config if config is not None else {}

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
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    def set(self, key: str, value: Any) -> None:
        self._config[key] = value
