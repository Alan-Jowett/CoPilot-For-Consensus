# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Shared utilities and base classes for microservices."""

from .retry_helper import retry_with_backoff
from .event_handler import safe_event_handler
from .base_service import BaseService

__version__ = "0.1.0"

__all__ = [
    "retry_with_backoff",
    "safe_event_handler",
    "BaseService",
]
