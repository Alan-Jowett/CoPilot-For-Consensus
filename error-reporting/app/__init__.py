# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""
Error Reporting Service - A lightweight error aggregation service.

This service receives structured error events from all microservices,
stores them in memory (with optional persistence), and provides a web UI
and API for viewing and filtering errors.
"""

__version__ = "0.1.0"
