# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import time
import logging
import sys
import os

# Add SDK to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'sdk'))

from copilot_events import create_consensus_detector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SummarizationService:
    """Summarization service with consensus detection integration."""
    
    def __init__(self):
        """Initialize the summarization service."""
        self.consensus_detector = create_consensus_detector()
        logger.info(f"Initialized with consensus detector: {type(self.consensus_detector).__name__}")
    
    def analyze_thread(self, thread):
        """Analyze a thread and generate summary with consensus information.
        
        Args:
            thread: Thread object to analyze
            
        Returns:
            Dictionary containing summary and consensus information
        """
        logger.info(f"Analyzing thread: {thread.thread_id}")
        
        # Detect consensus
        consensus_signal = self.consensus_detector.detect(thread)
        
        # Generate summary (placeholder for actual LLM-based summarization)
        summary = self._generate_summary(thread, consensus_signal)
        
        return {
            "thread_id": thread.thread_id,
            "summary": summary,
            "consensus": {
                "level": consensus_signal.level.value,
                "confidence": consensus_signal.confidence,
                "explanation": consensus_signal.explanation,
                "signals": consensus_signal.signals,
                "metadata": consensus_signal.metadata,
            }
        }
    
    def _generate_summary(self, thread, consensus_signal):
        """Generate thread summary.
        
        This is a placeholder for actual LLM-based summarization.
        In the future, this would call an LLM to generate the summary.
        """
        return {
            "subject": thread.subject,
            "message_count": thread.message_count,
            "participant_count": thread.participant_count,
            "consensus_detected": consensus_signal.level.value,
            # Future: Add actual LLM-generated summary here
        }


def main():
    """Summarization service: Generate weekly summaries and insights."""
    logger.info("Starting Summarization Service with Consensus Detection")
    
    # Initialize service with consensus detection
    service = SummarizationService()
    
    # Keep service running
    while True:
        logger.info("Summarization service running...")
        logger.info("Ready to process threads with consensus detection")
        time.sleep(30)


if __name__ == "__main__":
    main()
