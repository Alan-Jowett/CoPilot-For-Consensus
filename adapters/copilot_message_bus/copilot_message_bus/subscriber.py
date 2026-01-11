# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Legacy subscriber module for backward compatibility.

This module provides backward compatibility for code that imports from
copilot_message_bus.subscriber. The abstract class has been moved to base.py
and the factory has been moved to factory.py.
"""

from .base import EventSubscriber
from .factory import create_subscriber

__all__ = ["EventSubscriber", "create_subscriber"]
