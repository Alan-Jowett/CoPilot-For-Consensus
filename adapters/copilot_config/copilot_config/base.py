# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Base configuration provider interface."""

from abc import ABC, abstractmethod
from typing import Any


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
