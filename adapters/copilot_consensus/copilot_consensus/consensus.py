# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Consensus detection abstraction layer.

This module provides an abstraction layer for consensus detection strategies,
allowing different heuristics, rule-based systems, or ML models to be plugged in
for identifying signs of agreement, dissent, or stagnation in threads.
"""

import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .thread import Thread


class ConsensusLevel(Enum):
    """Enumeration of consensus levels."""
    STRONG_CONSENSUS = "strong_consensus"
    CONSENSUS = "consensus"
    WEAK_CONSENSUS = "weak_consensus"
    NO_CONSENSUS = "no_consensus"
    DISSENT = "dissent"
    STAGNATION = "stagnation"


@dataclass
class ConsensusSignal:
    """Represents the result of consensus detection.

    Attributes:
        level: The detected consensus level
        confidence: Confidence score (0.0 to 1.0)
        signals: List of specific signals detected
        explanation: Human-readable explanation of the detection
        metadata: Additional detection metadata
    """
    level: ConsensusLevel
    confidence: float
    signals: list[str] = field(default_factory=list)
    explanation: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate confidence score."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {self.confidence}")


class ConsensusDetector(ABC):
    """Abstract base class for consensus detection strategies.

    Implementations of this interface can use different approaches:
    - Rule-based heuristics
    - Machine learning models
    - Hybrid approaches
    """

    @abstractmethod
    def detect(self, thread: Thread) -> ConsensusSignal:
        """Detect consensus signals in a thread.

        Args:
            thread: The thread to analyze

        Returns:
            ConsensusSignal with detected consensus level and supporting evidence
        """
        pass


class HeuristicConsensusDetector(ConsensusDetector):
    """Basic heuristic-based consensus detector.

    Uses simple rules to detect consensus:
    - Number of replies and participants
    - Presence of agreement keywords (+1, I agree, LGTM, etc.)
    - Presence of dissent keywords (disagree, oppose, concern, etc.)
    - Time since last activity
    """

    # Agreement keywords and patterns
    AGREEMENT_PATTERNS = [
        r'\+1\b',
        r'\bLGTM\b',
        r'\bI agree\b',
        r'\bagree with\b',
        r'\bsounds good\b',
        r'\bmakes sense\b',
        r'\bsupport this\b',
        r'\bapprove\b',
        r'\bconcur\b',
    ]

    # Dissent keywords and patterns
    DISSENT_PATTERNS = [
        r'\bdisagree\b',
        r'\boppose\b',
        r'\bconcern\b',
        r'\bproblem with\b',
        r'\bissue with\b',
        r'\bnot sure\b',
        r'\bwait\b',
        r'\bhold on\b',
        r'-1\b',
    ]

    def __init__(self,
                 agreement_threshold: int = 3,
                 min_participants: int = 2,
                 stagnation_days: int = 7):
        """Initialize the heuristic detector.

        Args:
            agreement_threshold: Minimum agreement signals for consensus
            min_participants: Minimum participants for valid consensus
            stagnation_days: Days of inactivity before considering stagnant
        """
        self.agreement_threshold = agreement_threshold
        self.min_participants = min_participants
        self.stagnation_days = stagnation_days

    def detect(self, thread: Thread) -> ConsensusSignal:
        """Detect consensus using heuristic rules."""
        signals = []
        metadata = {}

        # Count messages and participants
        message_count = thread.message_count
        reply_count = thread.reply_count
        participant_count = thread.participant_count

        metadata['message_count'] = message_count
        metadata['reply_count'] = reply_count
        metadata['participant_count'] = participant_count

        # Count agreement and dissent signals
        agreement_count = self._count_patterns(thread, self.AGREEMENT_PATTERNS)
        dissent_count = self._count_patterns(thread, self.DISSENT_PATTERNS)

        metadata['agreement_signals'] = agreement_count
        metadata['dissent_signals'] = dissent_count

        # Check for stagnation (no recent activity)
        if thread.last_activity_at:
            # Ensure last_activity_at is timezone-aware
            last_activity = thread.last_activity_at
            if last_activity.tzinfo is None:
                last_activity = last_activity.replace(tzinfo=timezone.utc)
            else:
                last_activity = last_activity.astimezone(timezone.utc)

            days_since_activity = (datetime.now(timezone.utc) - last_activity).days
            metadata['days_since_activity'] = days_since_activity

            if days_since_activity > self.stagnation_days:
                signals.append(f"No activity for {days_since_activity} days")
                return ConsensusSignal(
                    level=ConsensusLevel.STAGNATION,
                    confidence=0.8,
                    signals=signals,
                    explanation=f"Thread has been inactive for {days_since_activity} days",
                    metadata=metadata
                )

        # Determine consensus level based on signals
        if dissent_count > 0:
            signals.append(f"Found {dissent_count} dissent signal(s)")
            confidence = min(0.9, 0.5 + (dissent_count * 0.1))
            return ConsensusSignal(
                level=ConsensusLevel.DISSENT,
                confidence=confidence,
                signals=signals,
                explanation=f"Thread shows dissent with {dissent_count} opposing view(s)",
                metadata=metadata
            )

        # Check for consensus based on agreement and participation
        if agreement_count >= self.agreement_threshold and participant_count >= self.min_participants:
            signals.append(f"Found {agreement_count} agreement signal(s)")
            signals.append(f"{participant_count} participant(s) engaged")

            if agreement_count >= self.agreement_threshold * 2:
                confidence = min(0.95, 0.7 + (agreement_count * 0.05))
                explanation = (
                    f"Strong consensus with {agreement_count} agreement signals "
                    f"from {participant_count} participants"
                )
                return ConsensusSignal(
                    level=ConsensusLevel.STRONG_CONSENSUS,
                    confidence=confidence,
                    signals=signals,
                    explanation=explanation,
                    metadata=metadata
                )
            else:
                confidence = min(0.85, 0.6 + (agreement_count * 0.05))
                explanation = (
                    f"Consensus detected with {agreement_count} agreement signals "
                    f"from {participant_count} participants"
                )
                return ConsensusSignal(
                    level=ConsensusLevel.CONSENSUS,
                    confidence=confidence,
                    signals=signals,
                    explanation=explanation,
                    metadata=metadata
                )

        # Weak consensus: some agreement but below threshold
        if agreement_count > 0 or reply_count >= 2:
            signals.append(f"Limited agreement ({agreement_count} signal(s))")
            signals.append(f"{reply_count} reply/replies")
            explanation = (
                f"Weak consensus with limited engagement "
                f"({reply_count} replies, {agreement_count} agreements)"
            )
            return ConsensusSignal(
                level=ConsensusLevel.WEAK_CONSENSUS,
                confidence=0.5,
                signals=signals,
                explanation=explanation,
                metadata=metadata
            )

        # No consensus
        signals.append("Insufficient activity or agreement signals")
        return ConsensusSignal(
            level=ConsensusLevel.NO_CONSENSUS,
            confidence=0.7,
            signals=signals,
            explanation="No clear consensus detected in thread",
            metadata=metadata
        )

    def _count_patterns(self, thread: Thread, patterns: list[str]) -> int:
        """Count occurrences of patterns across all messages in thread."""
        count = 0
        for message in thread.messages:
            content = message.content
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    count += 1
        return count


class MockConsensusDetector(ConsensusDetector):
    """Mock consensus detector for testing.

    Returns predefined consensus signals for testing purposes.
    Can be configured to return specific levels and confidence scores.
    """

    def __init__(self,
                 level: ConsensusLevel = ConsensusLevel.CONSENSUS,
                 confidence: float = 0.8):
        """Initialize mock detector.

        Args:
            level: The consensus level to return
            confidence: The confidence score to return
        """
        self.level = level
        self.confidence = confidence

    def detect(self, thread: Thread) -> ConsensusSignal:
        """Return predefined consensus signal."""
        return ConsensusSignal(
            level=self.level,
            confidence=self.confidence,
            signals=["mock_signal"],
            explanation=f"Mock detection: {self.level.value}",
            metadata={"mock": True, "thread_id": thread.thread_id}
        )


class MLConsensusDetector(ConsensusDetector):
    """Placeholder for ML-based consensus detection.

    This is a scaffold for future implementation of machine learning-based
    consensus detection. Could use:
    - Transformer models for sentiment analysis
    - Custom trained models on labeled consensus data
    - Ensemble methods combining multiple ML approaches
    """

    def __init__(self, model_path: str | None = None):
        """Initialize ML detector.

        Args:
            model_path: Path to trained model (if available)
        """
        self.model_path = model_path
        self.model = None
        # TODO: Load model when implemented

    def detect(self, thread: Thread) -> ConsensusSignal:
        """Detect consensus using ML model.

        Note: This is a placeholder implementation.
        """
        # TODO: Implement ML-based detection
        raise NotImplementedError(
            "ML-based consensus detection is not yet implemented. "
            "Use HeuristicConsensusDetector or MockConsensusDetector instead."
        )


def create_consensus_detector(detector_type: str | None = None) -> ConsensusDetector:
    """Factory method to create consensus detector based on configuration.

    Args:
        detector_type: Type of detector to create. Can be:
            - "heuristic": HeuristicConsensusDetector (default)
            - "mock": MockConsensusDetector
            - "ml": MLConsensusDetector
            If None, checks CONSENSUS_DETECTOR_TYPE environment variable.

    Returns:
        Instance of the requested ConsensusDetector

    Raises:
        ValueError: If unknown detector type is specified
    """
    if detector_type is None:
        detector_type = os.environ.get("CONSENSUS_DETECTOR_TYPE", "heuristic")

    detector_type = detector_type.lower()

    if detector_type == "heuristic":
        return HeuristicConsensusDetector()
    elif detector_type == "mock":
        return MockConsensusDetector()
    elif detector_type == "ml":
        return MLConsensusDetector()
    else:
        raise ValueError(
            f"Unknown consensus detector type: {detector_type}. "
            f"Valid types are: heuristic, mock, ml"
        )
