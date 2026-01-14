# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Tests for consensus detection."""
from datetime import datetime, timedelta, timezone
import pytest
from copilot_config.generated.adapters.consensus_detector import (
    AdapterConfig_ConsensusDetector,
    DriverConfig_ConsensusDetector_Heuristic,
    DriverConfig_ConsensusDetector_Ml,
    DriverConfig_ConsensusDetector_Mock,
)
from copilot_consensus import (
    ConsensusDetector,
    ConsensusLevel,
    ConsensusSignal,
    Message,
    Thread,
    create_consensus_detector,
)
from copilot_consensus.consensus import (
    HeuristicConsensusDetector,
    MockConsensusDetector,
    MLConsensusDetector,
)


def _driver_config(driver: str, fields: dict[str, object] | None = None):
    fields = dict(fields or {})
    if driver == "heuristic":
        return DriverConfig_ConsensusDetector_Heuristic(**fields)
    if driver == "mock":
        return DriverConfig_ConsensusDetector_Mock(**fields)
    if driver == "ml":
        return DriverConfig_ConsensusDetector_Ml(**fields)
    raise ValueError(f"Unknown driver: {driver}")


class TestConsensusSignal:
    """Tests for ConsensusSignal model."""

    def test_consensus_signal_creation(self):
        """Test creating a consensus signal."""
        signal = ConsensusSignal(
            level=ConsensusLevel.CONSENSUS,
            confidence=0.8,
            signals=["signal1", "signal2"],
            explanation="Test explanation",
            metadata={"test": "data"}
        )

        assert signal.level == ConsensusLevel.CONSENSUS
        assert signal.confidence == 0.8
        assert len(signal.signals) == 2
        assert signal.explanation == "Test explanation"
        assert signal.metadata["test"] == "data"

    def test_consensus_signal_defaults(self):
        """Test consensus signal with default values."""
        signal = ConsensusSignal(
            level=ConsensusLevel.NO_CONSENSUS,
            confidence=0.5
        )

        assert signal.signals == []
        assert signal.explanation == ""
        assert signal.metadata == {}

    def test_confidence_validation(self):
        """Test that confidence must be between 0 and 1."""
        # Valid confidence
        signal = ConsensusSignal(level=ConsensusLevel.CONSENSUS, confidence=0.5)
        assert signal.confidence == 0.5

        # Invalid confidence (too low)
        with pytest.raises(ValueError):
            ConsensusSignal(level=ConsensusLevel.CONSENSUS, confidence=-0.1)

        # Invalid confidence (too high)
        with pytest.raises(ValueError):
            ConsensusSignal(level=ConsensusLevel.CONSENSUS, confidence=1.5)


class TestHeuristicConsensusDetector:
    """Tests for HeuristicConsensusDetector."""

    def create_test_thread(self, messages_data):
        """Helper to create a test thread from message data."""
        messages = []
        base_time = datetime.now(timezone.utc)

        for i, data in enumerate(messages_data):
            msg = Message(
                message_id=f"msg-{i}",
                author=data.get("author", f"user{i}@example.com"),
                subject=data.get("subject", "Test Subject"),
                content=data.get("content", ""),
                timestamp=data.get("timestamp", base_time + timedelta(hours=i)),
                in_reply_to=data.get("in_reply_to")
            )
            messages.append(msg)

        return Thread(
            thread_id="test-thread",
            subject="Test Thread",
            messages=messages
        )

    def test_strong_consensus_detection(self):
        """Test detection of strong consensus."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        thread = self.create_test_thread([
            {"content": "I propose we do X"},
            {"content": "+1 I agree with this proposal", "author": "user1@example.com"},
            {"content": "LGTM, sounds good to me", "author": "user2@example.com"},
            {"content": "I agree, this makes sense", "author": "user3@example.com"},
            {"content": "+1 from me as well", "author": "user4@example.com"},
            {"content": "I support this approach", "author": "user5@example.com"},
        ])

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.STRONG_CONSENSUS
        assert signal.confidence > 0.7
        assert signal.metadata["agreement_signals"] >= 6
        assert signal.metadata["participant_count"] >= 2

    def test_consensus_detection(self):
        """Test detection of regular consensus."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        thread = self.create_test_thread([
            {"content": "What about option A?"},
            {"content": "+1 for option A", "author": "user1@example.com"},
            {"content": "I agree with option A", "author": "user2@example.com"},
            {"content": "Sounds good, LGTM", "author": "user3@example.com"},
        ])

        signal = detector.detect(thread)

        assert signal.level in [ConsensusLevel.CONSENSUS, ConsensusLevel.STRONG_CONSENSUS]
        assert signal.confidence > 0.5
        assert signal.metadata["agreement_signals"] >= 3

    def test_dissent_detection(self):
        """Test detection of dissent."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        thread = self.create_test_thread([
            {"content": "Let's go with approach X"},
            {"content": "I agree with X", "author": "user1@example.com"},
            {"content": "I disagree, I think we should wait", "author": "user2@example.com"},
            {"content": "I have concerns about X", "author": "user3@example.com"},
        ])

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.DISSENT
        assert signal.metadata["dissent_signals"] > 0

    def test_weak_consensus_detection(self):
        """Test detection of weak consensus."""
        detector = HeuristicConsensusDetector(agreement_threshold=5, min_participants=2, stagnation_days=7)

        thread = self.create_test_thread([
            {"content": "Should we proceed?"},
            {"content": "Maybe, let me think", "author": "user1@example.com"},
            {"content": "I guess so", "author": "user2@example.com"},
        ])

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.WEAK_CONSENSUS
        assert signal.confidence <= 0.6

    def test_no_consensus_detection(self):
        """Test detection of no consensus."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        thread = self.create_test_thread([
            {"content": "Initial message with no replies"},
        ])

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.NO_CONSENSUS

    def test_stagnation_detection(self):
        """Test detection of stagnant threads."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        # Create thread with old timestamp
        old_time = datetime.now(timezone.utc) - timedelta(days=10)
        thread = self.create_test_thread([
            {"content": "Old message", "timestamp": old_time},
            {"content": "Old reply", "timestamp": old_time + timedelta(hours=1)},
        ])

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.STAGNATION
        assert signal.metadata["days_since_activity"] > 7

    def test_agreement_patterns(self):
        """Test various agreement patterns are detected."""
        detector = HeuristicConsensusDetector(agreement_threshold=1, min_participants=2, stagnation_days=7)

        agreement_phrases = [
            "+1",
            "LGTM",
            "I agree",
            "agree with you",
            "sounds good",
            "makes sense",
            "support this",
            "I approve",
            "I concur",
        ]

        for phrase in agreement_phrases:
            thread = self.create_test_thread([
                {"content": "Proposal"},
                {"content": f"Yes, {phrase}", "author": "user1@example.com"},
            ])

            signal = detector.detect(thread)
            assert signal.metadata["agreement_signals"] >= 1, f"Failed to detect: {phrase}"

    def test_dissent_patterns(self):
        """Test various dissent patterns are detected."""
        detector = HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7)

        dissent_phrases = [
            "I disagree",
            "I oppose this",
            "I have a concern",
            "there's a problem with this",
            "I see an issue with",
            "I'm not sure about",
            "we should wait",
            "hold on",
            "-1",
        ]

        for phrase in dissent_phrases:
            thread = self.create_test_thread([
                {"content": "Proposal"},
                {"content": f"{phrase} because reasons", "author": "user1@example.com"},
            ])

            signal = detector.detect(thread)
            assert signal.level == ConsensusLevel.DISSENT, f"Failed to detect dissent: {phrase}"
            assert signal.metadata["dissent_signals"] >= 1


class TestMockConsensusDetector:
    """Tests for MockConsensusDetector."""

    def test_mock_detector_default(self):
        """Test mock detector with default values."""
        detector = MockConsensusDetector(level=ConsensusLevel.CONSENSUS, confidence=0.8)

        thread = Thread(
            thread_id="test-thread",
            subject="Test",
            messages=[]
        )

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.CONSENSUS
        assert signal.confidence == 0.8
        assert signal.metadata["mock"] is True
        assert signal.metadata["thread_id"] == "test-thread"

    def test_mock_detector_custom(self):
        """Test mock detector with custom values."""
        detector = MockConsensusDetector(
            level=ConsensusLevel.STRONG_CONSENSUS,
            confidence=0.95
        )

        thread = Thread(
            thread_id="test-thread",
            subject="Test",
            messages=[]
        )

        signal = detector.detect(thread)

        assert signal.level == ConsensusLevel.STRONG_CONSENSUS
        assert signal.confidence == 0.95

    def test_mock_detector_all_levels(self):
        """Test mock detector can return all consensus levels."""
        thread = Thread(thread_id="test", subject="Test", messages=[])

        for level in ConsensusLevel:
            detector = MockConsensusDetector(level=level, confidence=0.7)
            signal = detector.detect(thread)
            assert signal.level == level


class TestMLConsensusDetector:
    """Tests for MLConsensusDetector."""

    def test_ml_detector_not_implemented(self):
        """Test that ML detector raises NotImplementedError."""
        detector = MLConsensusDetector()

        thread = Thread(
            thread_id="test-thread",
            subject="Test",
            messages=[]
        )

        with pytest.raises(NotImplementedError):
            detector.detect(thread)


class TestConsensusDetectorFactory:
    """Tests for create_consensus_detector factory function."""

    def test_create_heuristic_detector(self):
        """Test creating heuristic detector."""
        config = _driver_config(
            "heuristic",
            {"agreement_threshold": 3, "min_participants": 2, "stagnation_days": 7},
        )
        detector = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="heuristic",
                driver=config,
            )
        )
        assert isinstance(detector, HeuristicConsensusDetector)

    def test_create_mock_detector(self):
        """Test creating mock detector."""
        config = _driver_config("mock", {"level": "consensus", "confidence": 0.9})
        detector = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="mock",
                driver=config,
            )
        )
        assert isinstance(detector, MockConsensusDetector)

    def test_create_ml_detector(self):
        """Test creating ML detector."""
        config = _driver_config("ml", {"model_path": "/tmp/model.bin"})
        detector = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="ml",
                driver=config,
            )
        )
        assert isinstance(detector, MLConsensusDetector)

    def test_create_unknown_detector(self):
        """Test that unknown detector type raises ValueError."""
        config = _driver_config("heuristic", {})
        with pytest.raises(ValueError, match=r"Unknown consensus_detector driver: unknown"):
            create_consensus_detector(
                AdapterConfig_ConsensusDetector(
                    consensus_detector_type="unknown",  # type: ignore[arg-type]
                    driver=config,
                )
            )

    def test_create_detector_missing_config(self):
        """Test error when config is missing."""
        with pytest.raises(ValueError, match="consensus_detector config is required"):
            create_consensus_detector(None)

    def test_create_detector_case_insensitive(self):
        """Test that detector type is case-insensitive."""
        config_heuristic = _driver_config(
            "heuristic",
            {"agreement_threshold": 3, "min_participants": 2, "stagnation_days": 7},
        )
        config_mock = _driver_config("mock", {"level": "consensus", "confidence": 0.8})
        config_ml = _driver_config("ml", {"model_path": None})

        detector1 = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="HEURISTIC",  # type: ignore[arg-type]
                driver=config_heuristic,
            )
        )
        detector2 = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="Mock",  # type: ignore[arg-type]
                driver=config_mock,
            )
        )
        detector3 = create_consensus_detector(
            AdapterConfig_ConsensusDetector(
                consensus_detector_type="Ml",  # type: ignore[arg-type]
                driver=config_ml,
            )
        )

        assert isinstance(detector1, HeuristicConsensusDetector)
        assert isinstance(detector2, MockConsensusDetector)
        assert isinstance(detector3, MLConsensusDetector)


class TestConsensusDetectorInterface:
    """Tests to verify ConsensusDetector interface compliance."""

    def test_all_detectors_implement_interface(self):
        """Test that all detector classes implement the interface."""
        detectors = [
            HeuristicConsensusDetector(agreement_threshold=3, min_participants=2, stagnation_days=7),
            MockConsensusDetector(level=ConsensusLevel.CONSENSUS, confidence=0.8),
            MLConsensusDetector(),
        ]

        for detector in detectors:
            assert isinstance(detector, ConsensusDetector)
            assert hasattr(detector, "detect")
            assert callable(detector.detect)
