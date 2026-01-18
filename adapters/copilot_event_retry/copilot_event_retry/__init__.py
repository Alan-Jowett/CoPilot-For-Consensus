# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Event retry utilities for handling race conditions in distributed systems.

This module provides retry logic with exponential backoff and jitter for handling
transient failures, particularly race conditions where events arrive before documents
are queryable in eventually-consistent datastores like CosmosDB.
"""

from .event_handler import DocumentNotFoundError, RetryableError, handle_event_with_retry
from .retry_policy import RetryConfig, RetryContext, RetryPolicy

__all__ = [
    "RetryPolicy",
    "RetryConfig",
    "RetryContext",
    "handle_event_with_retry",
    "RetryableError",
    "DocumentNotFoundError",
]

__version__ = "1.0.0"
