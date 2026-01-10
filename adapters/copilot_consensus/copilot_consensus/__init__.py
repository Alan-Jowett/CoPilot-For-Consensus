# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Consensus Detection Adapter.

A shared library for consensus detection across discussion threads
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .consensus import (
    ConsensusDetector,
    ConsensusLevel,
    ConsensusSignal,
    create_consensus_detector,
)
from .thread import Message, Thread

__all__ = [
    # Version
    "__version__",
    # Thread Models
    "Thread",
    "Message",
    # Consensus Detection
    "ConsensusDetector",
    "ConsensusSignal",
    "ConsensusLevel",
    "create_consensus_detector",
]
