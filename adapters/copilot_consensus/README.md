<!-- SPDX-License-Identifier: MIT
     Copyright (c) 2025 Copilot-for-Consensus contributors -->

# Consensus Detection Abstraction Layer

This module provides an abstraction layer for consensus detection in discussion threads. It allows different strategies (heuristics, ML models, etc.) to be plugged in for identifying signs of agreement, dissent, or stagnation.

## Overview

The consensus detection system consists of:

- **`Thread`** and **`Message`**: Data models for representing discussion threads
- **`ConsensusDetector`**: Abstract base class for consensus detection strategies
- **`ConsensusSignal`**: Result object containing detected consensus level and evidence
- **`ConsensusLevel`**: Enumeration of possible consensus states

## Consensus Levels

- **`STRONG_CONSENSUS`**: Clear, widespread agreement
- **`CONSENSUS`**: General agreement with good participation
- **`WEAK_CONSENSUS`**: Limited agreement or engagement
- **`NO_CONSENSUS`**: No clear direction
- **`DISSENT`**: Active disagreement or opposition
- **`STAGNATION`**: No recent activity

## Available Detectors

### HeuristicConsensusDetector

Rule-based detector using simple heuristics:

- Counts replies and participants
- Detects agreement keywords (+1, LGTM, "I agree", etc.)
- Detects dissent keywords (disagree, oppose, concern, etc.)
- Identifies stagnation based on time since last activity

**Configuration:**
```python
detector = HeuristicConsensusDetector(
    agreement_threshold=3,  # Minimum agreement signals for consensus
    min_participants=2,     # Minimum participants for valid consensus
    stagnation_days=7       # Days before considering thread stagnant
)
```

### MockConsensusDetector

For testing purposes. Returns predefined consensus signals.

```python
detector = MockConsensusDetector(
    level=ConsensusLevel.CONSENSUS,
    confidence=0.8
)
```

### MLConsensusDetector

Placeholder for future ML-based detection. Not yet implemented.

## Usage Examples

### Basic Usage

```python
from copilot_consensus import (
    Thread,
    Message,
    create_consensus_detector,
)
from datetime import datetime, timezone

# Create a thread
messages = [
    Message(
        message_id="msg-1",
        author="alice@example.com",
        subject="Proposal",
        content="I propose we do X",
        timestamp=datetime.now(timezone.utc),
    ),
    Message(
        message_id="msg-2",
        author="bob@example.com",
        subject="Re: Proposal",
        content="+1 I agree with this",
        timestamp=datetime.now(timezone.utc),
        in_reply_to="msg-1",
    ),
]

thread = Thread(
    thread_id="thread-123",
    subject="Proposal",
    messages=messages,
)

# Detect consensus
detector = create_consensus_detector()  # Uses heuristic by default
signal = detector.detect(thread)

print(f"Consensus Level: {signal.level.value}")
print(f"Confidence: {signal.confidence}")
print(f"Explanation: {signal.explanation}")
```

### Using Factory Pattern

```python
from copilot_consensus import create_consensus_detector

# Create detector from environment variable
detector = create_consensus_detector()

# Or explicitly specify type
heuristic = create_consensus_detector("heuristic")
mock = create_consensus_detector("mock")
```

### Environment Configuration

Set the `CONSENSUS_DETECTOR_TYPE` environment variable:

```bash
export CONSENSUS_DETECTOR_TYPE=heuristic  # Default
export CONSENSUS_DETECTOR_TYPE=mock       # For testing
export CONSENSUS_DETECTOR_TYPE=ml         # When implemented
```

### Integration with Summarization Service

```python
from copilot_consensus import create_consensus_detector

class SummarizationService:
    def __init__(self):
        self.consensus_detector = create_consensus_detector()

    def summarize_thread(self, thread):
        # Detect consensus
        consensus = self.consensus_detector.detect(thread)

        # Use consensus information in summary
        summary = self._generate_summary(thread)

        return {
            "summary": summary,
            "consensus_level": consensus.level.value,
            "consensus_confidence": consensus.confidence,
            "consensus_explanation": consensus.explanation,
        }
```

## Testing

```python
import pytest
from copilot_consensus import (
    MockConsensusDetector,
    ConsensusLevel,
    Thread,
)

def test_my_service():
    # Use mock detector for predictable testing
    mock_detector = MockConsensusDetector(
        level=ConsensusLevel.STRONG_CONSENSUS,
        confidence=0.95
    )

    service = MyService(consensus_detector=mock_detector)
    result = service.process_thread(thread)

    assert result["consensus_level"] == "strong_consensus"
```

## Extending with Custom Detectors

To implement a custom consensus detector:

```python
from copilot_consensus import ConsensusDetector, ConsensusSignal, ConsensusLevel

class CustomConsensusDetector(ConsensusDetector):
    def __init__(self, custom_param):
        self.custom_param = custom_param

    def detect(self, thread):
        # Implement your detection logic
        level = ConsensusLevel.CONSENSUS
        confidence = 0.8

        return ConsensusSignal(
            level=level,
            confidence=confidence,
            signals=["custom_signal"],
            explanation="Custom detection result",
            metadata={"custom": "data"}
        )
```

## Thread Properties

The `Thread` model provides useful properties:

- **`message_count`**: Total number of messages
- **`reply_count`**: Number of replies (excluding root message)
- **`participant_count`**: Number of unique participants
- **`started_at`**: Timestamp of first message
- **`last_activity_at`**: Timestamp of most recent message

## Best Practices

1. **Use the factory method**: `create_consensus_detector()` allows easy configuration switching
2. **Check confidence scores**: Don't rely solely on the level; consider confidence
3. **Inspect signals and metadata**: These provide evidence for the detection
4. **Use mock detector in tests**: Ensures predictable, fast test execution
5. **Configure thresholds**: Tune `HeuristicConsensusDetector` parameters for your use case

## Future Enhancements

- Implement ML-based detection using transformers
- Add sentiment analysis integration
- Support for weighted participant contributions
- Time-series analysis of consensus evolution
- Multi-language support for keyword detection
