# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Legacy publisher module for backward compatibility.

This module provides backward compatibility for code that imports from
copilot_message_bus.publisher. The abstract class has been moved to base.py
and the factory has been moved to factory.py.
"""

from .base import EventPublisher
from .factory import create_publisher

__all__ = ["EventPublisher", "create_publisher"]
