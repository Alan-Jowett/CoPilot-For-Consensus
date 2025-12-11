# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Copilot-for-Consensus Consensus Detection SDK.

A shared library for consensus detection across discussion threads
in the Copilot-for-Consensus system.
"""

__version__ = "0.1.0"

from .thread import Thread, Message
from .consensus import (
    ConsensusDetector,
    ConsensusSignal,
    ConsensusLevel,
    HeuristicConsensusDetector,
    MockConsensusDetector,
    MLConsensusDetector,
    create_consensus_detector,
)

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
    "HeuristicConsensusDetector",
    "MockConsensusDetector",
    "MLConsensusDetector",
    "create_consensus_detector",
]
