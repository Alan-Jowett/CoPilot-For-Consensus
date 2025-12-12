# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Environment-backed configuration provider."""

import os
from typing import Any, Dict, Optional

from .base import ConfigProvider


class EnvConfigProvider(ConfigProvider):
    """Configuration provider that reads from environment variables."""

    def __init__(self, environ: Optional[Dict[str, str]] = None):
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
