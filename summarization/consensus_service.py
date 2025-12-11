# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

"""Consensus detection service for summarization.

This module demonstrates integration of consensus detection
with the summarization service.
"""

import logging
import sys
import os

# Add SDK to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk', 'copilot_consensus'))

from copilot_consensus import (
    Thread,
    Message,
    ConsensusDetector,
    ConsensusSignal,
    create_consensus_detector,
)

logger = logging.getLogger(__name__)


class ConsensusAnalysisService:
    """Service for analyzing consensus in threads.
    
    This service wraps consensus detection and provides
    additional context for summarization.
    """
    
    def __init__(self, detector: ConsensusDetector = None):
        """Initialize the consensus analysis service.
        
        Args:
            detector: ConsensusDetector to use. If None, creates
                     detector based on environment configuration.
        """
        self.detector = detector or create_consensus_detector()
        logger.info(f"Initialized with detector: {type(self.detector).__name__}")
    
    def analyze_thread(self, thread: Thread) -> dict:
        """Analyze a thread for consensus and return comprehensive results.
        
        Args:
            thread: The thread to analyze
            
        Returns:
            Dictionary containing:
                - consensus_signal: The ConsensusSignal result
                - summary: Human-readable summary
                - recommendations: List of recommended actions
        """
        logger.info(f"Analyzing thread: {thread.thread_id}")
        
        # Detect consensus
        signal = self.detector.detect(thread)
        
        # Generate summary
        summary = self._generate_summary(thread, signal)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(thread, signal)
        
        return {
            "consensus_signal": signal,
            "summary": summary,
            "recommendations": recommendations,
        }
    
    def _generate_summary(self, thread: Thread, signal: ConsensusSignal) -> str:
        """Generate human-readable summary of consensus analysis."""
        parts = [
            f"Thread '{thread.subject}' (ID: {thread.thread_id})",
            f"- Messages: {thread.message_count}",
            f"- Participants: {thread.participant_count}",
            f"- Consensus Level: {signal.level.value}",
            f"- Confidence: {signal.confidence:.2f}",
            f"- Explanation: {signal.explanation}",
        ]
        
        if signal.signals:
            parts.append(f"- Signals: {', '.join(signal.signals)}")
        
        return "\n".join(parts)
    
    def _generate_recommendations(self, thread: Thread, 
                                  signal: ConsensusSignal) -> list:
        """Generate actionable recommendations based on consensus level."""
        recommendations = []
        
        if signal.level.value == "strong_consensus":
            recommendations.append("Consider moving forward with the proposal")
            recommendations.append("Document the consensus in meeting notes")
        
        elif signal.level.value == "consensus":
            recommendations.append("Consensus appears to be forming")
            recommendations.append("Consider a final call for objections")
        
        elif signal.level.value == "weak_consensus":
            recommendations.append("Limited engagement - consider soliciting more feedback")
            recommendations.append("Clarify the proposal to encourage participation")
        
        elif signal.level.value == "dissent":
            recommendations.append("Address concerns raised by participants")
            recommendations.append("Consider alternative proposals")
            recommendations.append("Schedule a discussion to resolve differences")
        
        elif signal.level.value == "stagnation":
            recommendations.append("Thread appears stagnant")
            recommendations.append("Consider sending a reminder or update")
            recommendations.append("Evaluate if the topic still requires discussion")
        
        else:  # no_consensus
            recommendations.append("No clear consensus detected")
            recommendations.append("Encourage more participation")
        
        return recommendations


def example_usage():
    """Example demonstrating consensus detection usage."""
    from datetime import datetime, timezone, timedelta
    
    logging.basicConfig(level=logging.INFO)
    
    # Create a sample thread with consensus
    base_time = datetime.now(timezone.utc)
    messages = [
        Message(
            message_id="msg-1",
            author="alice@example.com",
            subject="Proposal: Update authentication flow",
            content="I propose we update our authentication to use OAuth 2.0",
            timestamp=base_time,
        ),
        Message(
            message_id="msg-2",
            author="bob@example.com",
            subject="Re: Proposal: Update authentication flow",
            content="+1 I agree with this approach. OAuth 2.0 is more secure.",
            timestamp=base_time + timedelta(hours=1),
            in_reply_to="msg-1",
        ),
        Message(
            message_id="msg-3",
            author="charlie@example.com",
            subject="Re: Proposal: Update authentication flow",
            content="LGTM, this makes sense for our use case.",
            timestamp=base_time + timedelta(hours=2),
            in_reply_to="msg-1",
        ),
        Message(
            message_id="msg-4",
            author="diana@example.com",
            subject="Re: Proposal: Update authentication flow",
            content="I support this proposal. When can we start implementation?",
            timestamp=base_time + timedelta(hours=3),
            in_reply_to="msg-1",
        ),
    ]
    
    thread = Thread(
        thread_id="thread-auth-2025",
        subject="Proposal: Update authentication flow",
        messages=messages,
    )
    
    # Analyze with heuristic detector
    print("\n=== Heuristic Consensus Detection ===")
    service = ConsensusAnalysisService()
    result = service.analyze_thread(thread)
    
    print(f"\n{result['summary']}")
    print("\nRecommendations:")
    for rec in result['recommendations']:
        print(f"  - {rec}")
    
    # Demonstrate factory pattern with different detectors
    print("\n\n=== Mock Consensus Detection (for testing) ===")
    service_mock = ConsensusAnalysisService(detector=create_consensus_detector("mock"))
    result_mock = service_mock.analyze_thread(thread)
    print(f"\n{result_mock['summary']}")


if __name__ == "__main__":
    example_usage()
