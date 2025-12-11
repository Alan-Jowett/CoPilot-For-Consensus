# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Copilot-for-Consensus contributors

import time
import logging
from adapters import SummarizerFactory

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Summarization service: Generate weekly summaries and insights."""
    logger.info("Starting Summarization Service")
    
    # Initialize summarizer using factory
    summarizer = SummarizerFactory.create_summarizer()
    logger.info(f"Initialized summarizer: {type(summarizer).__name__}")
    
    # Example usage (placeholder for actual event-driven logic)
    # In production, this would listen for SummarizationRequestedEvent
    # and publish SummaryCompleteEvent
    
    # Keep service running
    while True:
        logger.info("Summarization service running...")
        time.sleep(30)

if __name__ == "__main__":
    main()
